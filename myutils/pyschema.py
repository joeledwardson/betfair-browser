import dataclasses
from typing import Dict, Any, List, TypedDict, Optional
import inspect
import pydantic
from pydantic import BaseModel, create_model

OBJ_CLASS_KEY = "_obj_class_key"


class SchemaException(Exception):
    pass


class Config:
    underscore_attrs_are_private = True
    extra = 'forbid'
    arbitrary_types_allowed = True
    validate_all = False
    orm_mode = True
    validate_assignment = False


def dc(cls: type):
    """Pydantic dataclass decorator with custom configuration and auto update forward references"""
    cls = pydantic.dataclasses.dataclass(config=Config)(cls)
    cls.__pydantic_model__.update_forward_refs()
    return cls


def get_inheritance_args(c: type) -> Dict[str, inspect.Parameter]:
    """get dictionary of arguments from class' initialisation function"""
    args = {}
    # loop class type and all inherited classes
    for x in c.__mro__:
        if '__init__' in x.__dict__:
            spec = inspect.getfullargspec(x)
            sig = inspect.signature(x)
            # put parameters into dictionary only if they are not *args or **kwargs
            args.update({k: v for k, v in sig.parameters.items() if k != spec.varargs and k != spec.varkw})
            # check if *args or **kwargs parameter exists - if not, infer no inheritance class processing is needed
            if not spec.varargs and not spec.varkw:
                break
    return args


class TypeOverride(TypedDict):
    annotation: Any
    default: Any


class ClassModelSpec(TypedDict):
    cls: type
    ignore_args: Optional[List[str]]
    type_overrides: Optional[Dict[str, TypeOverride]]


def create_dataclass_model(cls: type):
    return pydantic.dataclasses.dataclass(cls, config=Config).__pydantic_model__


def create_cls_model(
        cls: type,
        ignore_args: Optional[List[str]] = None,
        type_overrides: Optional[Dict[str, TypeOverride]] = None
):
    ignore_args = ignore_args or list()
    type_overrides = type_overrides or dict()
    class _BaseModel(BaseModel):
        __doc__ = cls.__doc__
        Config = Config
    spec = get_inheritance_args(cls)
    replace_empty = lambda p, v: v if p == inspect.Parameter.empty else p
    args = {
        k: (
            type_overrides[k]["annotation"],
            type_overrides[k]["default"]
        ) if k in type_overrides else (
            replace_empty(p.annotation, Any),
            replace_empty(p.default, ...)
        )  # parameters without defaults are "required" and ellipsis means required in Pydantic
        for k, p in spec.items()
        if k not in ignore_args
    }
    return create_model(cls.__name__, **args, __base__=_BaseModel)



def create_pyd_model(spec: ClassModelSpec):
    if dataclasses.is_dataclass(spec['cls']):
        return create_dataclass_model(spec['cls'])
    else:
        return create_cls_model(**spec)


def override_schema_type(var_name, new_type, defs, schema: Dict):
    class T(pydantic.BaseModel):
        var: new_type
    updated = T.schema()["properties"]["var"]
    def u(s: Dict):
        p = s.get("properties", dict())
        if var_name in p:
            p[var_name].update(updated)
    for k, d in schema.get("definitions", dict()).items():
        if k in defs:
            u(d)

    # if schema["title"] in defs:
    #


def mdl_schema(
        topSpec: ClassModelSpec,
        classes: List[ClassModelSpec]
):
    topModel = create_pyd_model(topSpec)
    cls_models = dict()
    for c in classes:
        cls_models[c['cls'].__name__] = create_pyd_model(c)
    locals().update(cls_models)
    for m in cls_models.values():
        m.update_forward_refs()
    topModel.update_forward_refs()
    return topModel.schema()


def class_to_schema(
        cls: type,
        ignore_args: Optional[List[str]] = None,
        type_overrides: Optional[Dict[str, TypeOverride]] = None) -> Dict[str, any]:
    """get schema from class using pydantic"""
    ignore_args = ignore_args or list()
    type_overrides = type_overrides or dict()

    class _BaseModel(BaseModel):
        __doc__ = cls.__doc__
        Config = Config

    spec = get_inheritance_args(cls)
    replace_empty = lambda p, v: v if p == inspect.Parameter.empty else p
    args = {
        k: (
            type_overrides[k]["annotation"],
            type_overrides[k]["default"]
        ) if k in type_overrides else (
            replace_empty(p.annotation, Any),
            replace_empty(p.default, ...)
        )  # parameters without defaults are "required" and ellipsis means required in Pydantic
        for k, p in spec.items()
        if k not in ignore_args
    }
    mdl = create_model(cls.__name__, **args, __base__=_BaseModel)
    mdl.update_forward_refs()
    s = mdl.schema()
    return s


def is_class(cls_def: Dict) -> bool:
    """
    determine if JSON schema definition is for a class

    - JSON schema object can be differentiated as a python class object and not Dict using "additionalProperties"
    - "additionalProperties" is False for classes but is {type: <dictionary type here>} for dicts
    """
    return cls_def.get("type") == "object" and cls_def.get("additionalProperties", None) == False


def class_process(cls_def: Dict, cls_name: str):
    """
    modify json schema definition for a "class" object by adding constant with class name
    - if class definition already uses the key OBJ_CLASS_KEY for something else then an error will be raised,
    as the key is hardcoded for class definition purposes
    """
    properties = cls_def.get("properties", dict())
    if OBJ_CLASS_KEY in properties:
        raise SchemaException(f'property "{cls_name}" already has object key "{OBJ_CLASS_KEY}"')
    properties = {
         OBJ_CLASS_KEY: {
             "const": cls_name
         }
     } | properties
    cls_def["properties"] = properties
    # add class definition key to required properties
    cls_def["required"] = [OBJ_CLASS_KEY] + cls_def.get("required", list())


def class_model_schema(schema: Dict[str, Any]):
    """modify schema definition to include constants of class definition names"""

    # if schema definition root is class definition then add class const
    if is_class(schema):
        class_process(schema, schema["title"])

    # loop definitions and add class const if needed
    for k, clsDef in schema.get("definitions", dict()).items():
        if isinstance(clsDef, dict) and is_class(clsDef):
            class_process(clsDef, k)

    return schema
