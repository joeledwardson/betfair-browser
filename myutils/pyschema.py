from typing import Dict, Any, List, TypedDict, Optional
import inspect
from pydantic import BaseModel, create_model



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


def class_to_schema(
        cls: type,
        ignore_args: Optional[List[str]] = None,
        type_overrides: Optional[Dict[str, TypeOverride]] = None) -> Dict[str, any]:
    """get schema from class using pydantic"""
    ignore_args = ignore_args or list()
    type_overrides = type_overrides or dict()

    class _BaseModel(BaseModel):
        __doc__ = cls.__doc__

        class Config:
            extra = 'allow'
            arbitrary_types_allowed = True

    spec = get_inheritance_args(cls)
    replace_empty = lambda p, v: v if p == inspect.Parameter.empty else p
    args = {
        k: (
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

