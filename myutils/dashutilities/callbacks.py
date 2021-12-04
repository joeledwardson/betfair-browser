from typing import Union, List, Dict, Any, Optional, Callable
import dash
import logging
from dash.dependencies import DashDependency, Input, Output, State
from myutils.exceptions import DashUtilsException

Config = Union[DashDependency, List['Config'], Dict[str, 'Config']]
ConfigDict = Dict[str, Config]
T = Union[Any, List['T'], Dict[str, 'T']]
TDict = Dict[str, T]


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def flatten_to_list(cfg: Config) -> List[Any]:
    """
    Flatten a recursive dictionary/list of values to a single-layer list

    Examples:
    flatten({'a': {'b': [1, 2, 3]}, 'c': [5]})
    [1, 2, 3, 5]
    flatten(1)
    [1]
    """
    _out = []

    def inner(v):
        if isinstance(v, list):
            [inner(x) for x in v]
        elif isinstance(v, dict):
            [inner(x) for x in v.values()]
        else:
            _out.append(v)

    inner(cfg)
    return _out


def assign_value(spec: Dict[str, T], args: List[Any]) -> Dict[str, T]:
    """
    Iterate through recursive specification format of dictionaries/lists and assign list of values from `args` in
    the same format

    Examples:
    assign_value(
        {
            'a': {
                'b': 'DUMMY',
                'c': 'DUMMY'
            },
            'd': ['DUMMY']
        },
        ['Arg X', 'Arg Y', 'Arg Z']
    )
    {'a': {'b': 'Arg X', 'c': 'Arg Y'}, 'd': ['Arg Z']}
    """
    if isinstance(spec, list):
        return [assign_value(v, args) for v in spec]
    elif isinstance(spec, dict):
        return {k: assign_value(v, args) for k, v in spec.items()}
    else:
        if not len(args):
            raise DashUtilsException(f'cannot assign value for spec: "{spec}", args empty')
        return args.pop(0)


def flatten_output(spec: Dict[str, T], values: Dict[str, T]) -> List[Any]:
    """
    Flatten as set of values in list/dictionary according to the specification designated by `spec`
    Only flatten as far as the nested lists/dictionaries are constructed in `spec` - any further layers in
    `values` will be left unchanged

    Examples:
    See below the example where keys 'a' and ('b', 'c' nested in 'x') are flattened but the list in 'c' is not
    flattened

    flatten_output(
        {
            'a': 'DUMMY',
            'x': {
                'b': 'DUMMY',
                'c': 'DUMMY'
            }
        },
        {
            'a': 1,
            'x':{
                'b': 2,
                'c': [3, 4]
            }
        }
    )
    [1, 2, [3, 4]]
    """
    _out = []

    def inner(_spec: T, _val: T):
        if type(_spec) is list:
            [inner(s, v) for s, v in zip(_spec, _val)]
        elif type(_spec) is dict:
            [inner(s, _val[k]) for k, s in _spec.items()]
        else:
            _out.append(_val)

    inner(spec, values)
    return _out


def dict_callback(
        app: dash.Dash,
        outputs_config: ConfigDict,
        inputs_config: ConfigDict,
        states_config: Optional[ConfigDict],
):
    def outer(process: Callable[[TDict, TDict, TDict], None]):
        inputs: List[Input] = flatten_to_list(inputs_config)
        outputs: List[Output] = flatten_to_list(outputs_config)
        states: List[State] = flatten_to_list(states_config)

        logger.info(f'generating callback using process "{process.__name__}"')
        get_info = lambda objs: '\n'.join([f'{x.__class__.__name__}: {repr(x)}' for x in objs])
        logger.info(f'inputs:\n{get_info(inputs)}')
        logger.info(f'outputs:\n{get_info(outputs)}')
        logger.info(f'states:\n{get_info(states)}')

        @app.callback(outputs, inputs, states)
        def callback(*args):
            args = list(args)
            input_vars = assign_value(inputs_config, args)
            state_vars = assign_value(states_config, args)
            if len(args):
                raise DashUtilsException(f'still have {len(args)} args remaining to process')
            output_vars = assign_value(outputs_config, [None] * len(outputs))
            process(output_vars, input_vars, state_vars)
            callback_output = flatten_output(outputs_config, output_vars)
            return callback_output
    return outer