from dash.development import base_component as dbase
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
import dash_table
from typing import Dict, List, Any, Optional, TypedDict, Union
from myutils import registrar
import uuid
from ..exceptions import LayoutException

dash_generators = registrar.Registrar()

HEADER_PY = 2  # header top/bottom padding
HEADER_PX = 4  # header left/right padding
NAV_BTN_P = 0  # padding for navigation links
LOAD_TYPE = 'dot'  # loading type
NAV_P = 0  # padding around each nav object
NAV_PT = 2  # top padding of nav bar
BTN_ML = 2  # left margin for button icons
BTN_COLOR = 'primary'  # default button color
COL_PAD = 1  # column padding
CONT_M = 4  # container margins
CONT_P = 4  # container padding
SIDE_EACH_MB = 2  # bottom margin for each sidebar element
SIDE_EACH_MX = 1  # left/right margin for each sidebar element
SIDE_CONTENT_P = 3  # sidebar content padding
SIDE_PR = 2  # sidebar padding right of elements

EL_MAP = {
    'element-header': {
        'dash_cls': html.H2,
    },
    'element-div': {
        'dash_cls': html.Div
    },
    'element-input': {
        'dash_cls': dbc.Input
    },
    'element-progress': {
        'dash_cls': dbc.Progress
    },
    'element-input-group': {
        'dash_cls': dbc.InputGroup
    },
    'element-input-group-addon': {
        'dash_cls': dbc.InputGroupAddon
    },
    'element-paragraph': {
        'dash_cls': html.P
    }
}


def _validate_id(spec):
    if spec.get('id') is None:
        raise LayoutException(f'spec "{spec}" has no ID')


@dash_generators.register_named('element-select')
def gen_select(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    return dcc.Dropdown(
        id=spec.pop('id'),
        placeholder=spec.pop('placeholder', None),
        className=spec.pop('css_classes', '')
    )


@dash_generators.register_named('element-button')
def gen_button(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    children = list()
    btn_text = spec.pop('btn_text', None)
    if btn_text is not None:
        children.append(btn_text)
    btn_icon = spec.pop('btn_icon', None)
    btn_color = spec.pop('color', BTN_COLOR)
    if btn_icon is not None:
        btn_cls = btn_icon
        if btn_text is not None:
            btn_cls += f' ml-{BTN_ML}'  # add margin left to icon if text is specified
        children.append(html.I(className=btn_cls))
    return dbc.Button(
        children,
        id=spec.pop('id'),
        n_clicks=0,
        color=btn_color,
        className=spec.pop('css_classes', '')
    )


@dash_generators.register_named('element-table')
def gen_table(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    table_cols = spec.pop('columns')
    n_rows = spec.pop('n_rows')
    table_id = spec.pop('id')
    style_cell = {
        'textAlign': 'left',
        'whiteSpace': 'normal',
        'height': 'auto',
        'verticalAlign': 'middle',
        'padding': '0.5rem',
        'border': '1px solid RGBA(255,255,255,0)'
    }
    if not spec.pop('no_fixed_widths', None):
        style_cell |= {
            'maxWidth': 0  # fix column widths
        }
    return html.Div(
        dash_table.DataTable(
            id=table_id,
            columns=[
                dict(name=v, id=k)
                for k, v in table_cols.items()
            ],
            style_cell=style_cell,
            style_data={
                # 'border': 'none'
                # 'borderColor': 'white'
            },
            style_header={
                'fontWeight': 'bold',
                'border': 'none'
            },
            style_table={
                'overflowY': 'auto',
            },
            page_size=n_rows,
        ),
        className='table-container flex-grow-1 overflow-hidden pr-1'
    )


@dash_generators.register_named('element-stylish-select')
def gen_stylish_select(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    placeholder = spec.pop('placeholder')
    options = spec.pop('select_options', list())
    clear_id = spec.pop('clear_id')
    select_id = spec.pop('id')
    css_classes = spec.pop('css_classes', '')
    return dbc.ButtonGroup(
        [
            dbc.Select(
                id=select_id,
                placeholder=placeholder,
                options=options,
            ),
            dbc.Button(
                [html.I(className="fas fa-times-circle")],
                id=clear_id,
                color='secondary'
            ),
        ], 
        className=css_classes
    )


@dash_generators.register_named('element-navigation-button')
def gen_navigation_button(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    href = spec.pop('href')
    # btn_id = spec.pop('btn_id', None)
    # btn_icon = spec.pop('btn_icon')
    nav_id = spec.pop('id')
    css_classes = spec.pop('css_classes', '')
    return dbc.NavLink(
        [_gen_element(s) for s in spec.pop('children')],
        # [dbc.Button(
        #     html.I(className=btn_icon),
        #     id=btn_id,
        #     n_clicks=0,
        #     color=BTN_COLOR,
        # )],
        id=nav_id,
        href=href,
        active='exact',
        className=f'p-{NAV_BTN_P}' or css_classes
    )


@dash_generators.register_named('element-navigation-item')
def gen_navigation_item(spec: Dict) -> dbase.Component:
    nav_icon = spec.pop('nav_icon', None)
    css_classes = spec.pop('css_classes', '')
    children = list()
    if nav_icon:
        children.append(html.I(className=nav_icon))
    children += [_gen_element(x) for x in spec.pop('children_spec', list())]
    return dbc.NavItem(
        dbc.NavLink(
            id=spec.pop('id', None) or str(uuid.uuid4()),
            children=children,
            href=spec.pop('href'),
            active='exact',
            className=spec.pop('nav_css_classes', '')
        ),
        className=css_classes
    )


@dash_generators.register_named('element-loading')
def _(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    return dcc.Loading(
        id=spec.pop('id'),
        type=LOAD_TYPE,
        className=spec.pop('css_classes', ''),
        children=[_gen_element(s) for s in spec.pop('children_spec', [])]
    )


@dash_generators.register_named('element-badge')
def _(spec: Dict) -> dbase.Component:
    return dbc.Badge(
        id=spec.pop('id', None) or str(uuid.uuid4()),
        color=spec.pop('color', None),
        className=spec.pop('css_classes', ''),
        children=_gen_element(spec.pop('children_spec', []))
    )


@dash_generators.register_named('element-modal')
def gen_modal(spec: Dict) -> dbase.Component:
    modal_id = spec.pop('id')
    header_spec = spec.pop('header_spec')
    header_children = _gen_element(header_spec) if type(header_spec) == list else header_spec
    footer_spec = spec.pop('footer_spec')
    footer_children = list()
    for i, child_spec in enumerate(footer_spec):
        if i == 0:
            css_classes = child_spec.get('css_classes', '')
            css_classes += ' ml-auto'
            child_spec['css_classes'] = css_classes
        footer_children.append(_gen_element(child_spec))
    return dbc.Modal([
        dbc.ModalHeader(header_children),
        dbc.ModalFooter(footer_children)
    ], id=modal_id)


@dash_generators.register_named('element-periodic')
def gen_periodic(spec: Dict) -> dbase.Component:
    return dcc.Interval(
        id=spec.pop('id'),
        interval=spec.pop('interval_milliseconds')
    )


@dash_generators.register_named('element-tabs')
def _(spec: Dict) -> dbase.Component:
    return dbc.Tabs(
        id=spec.pop('id'),
        className=spec.pop('css_classes', ''),
        children=[_gen_element(s) for s in spec.pop('children_spec', [])]
    )


@dash_generators.register_named('element-tab')
def _(spec: Dict) -> dbase.Component:
    return dbc.Tab(
        tab_id=spec.pop('tab_id'),
        label=spec.pop('label', ''),
        className=spec.pop('css_classes', ''),
        children=[_gen_element(s) for s in spec.pop('children_spec', [])]
    )


@dash_generators.register_named('element-fontawesome')
def _(spec: Dict) -> dbase.Component:
    return html.I(className=spec.pop('css_classes'))


@dash_generators.register_named('element-tooltip')
def _(spec: Dict) -> dbase.Component:
    return dbc.Tooltip(
        children=spec.pop('children_spec', None),
        target=spec.pop('tooltip_target'),
        placement=spec.pop('placement'),
        autohide=False,
    )


@dash_generators.register_named('element-popover')
def _(spec: Dict) -> dbase.Component:
    return dbc.Popover(
        children=spec.pop('children_spec', None),
        target=spec.pop('tooltip_target'),
        placement=spec.pop('placement'),
        trigger="hover",

    )


@dash_generators.register_named('element-markdown')
def _(spec: Dict) -> dbase.Component:
    return dcc.Markdown(
        children=spec.pop('markdown_text'),
        className=spec.pop('css_classes', ''),
    )


def _gen_element(spec: Union[str, Dict]):

    if isinstance(spec, str):
        return spec
    if isinstance(spec, list):
        return [_gen_element(x) for x in spec]

    el_type = spec.pop('type')
    if el_type in dash_generators:
        element = dash_generators[el_type](spec)
    elif el_type in EL_MAP:
        dash_cls = EL_MAP[el_type]['dash_cls']
        children_spec = spec.pop('children_spec', None)
        user_kwargs = spec.pop('element_kwargs', dict())
        hidden = spec.pop('hidden', None)
        el_id = spec.pop('id', None)
        if children_spec is not None:
            children = _gen_element(children_spec)
        else:
            children = None
        el_kwargs = {'id': el_id} if el_id else {}
        el_kwargs |= {'hidden': hidden} if hidden else {}
        el_kwargs |= {'children': children, 'className': spec.pop('css_classes', '')}
        el_kwargs |= EL_MAP[el_type].get('default_kwargs', dict())
        el_kwargs |= user_kwargs
        element = dash_cls(**el_kwargs)
    else:
        raise LayoutException(f'type "{el_type}" unrecognised')

    if spec:
        raise LayoutException(f'spec "{spec}" has unrecognised elements')
    return element


class ElementSpec(TypedDict):
    id: str
    placeholder: Optional[str]
    css_classes: Optional[str]


class SidebarSpec(TypedDict):
    sidebar_title: str
    sidebar_id: str
    close_id: str
    content: List[ElementSpec]


class ContainerSpec(TypedDict):
    container_id: str
    content: Union[List[ElementSpec], Dict[str, ElementSpec]]


class StoreSpec(TypedDict):
    id: str
    storage_type: Optional[str]
    data: Optional[Any]


class ContentSpec(TypedDict):
    navigation: List[ElementSpec]
    header_title: str
    header_right: ElementSpec
    header_left: ElementSpec
    hidden_elements: List[ElementSpec]
    containers: List[ContainerSpec]
    sidebars: List[SidebarSpec]
    stores: List[StoreSpec]
    tooltips: List[ElementSpec]


def generate_sidebar(spec: SidebarSpec):
    title = spec.pop('sidebar_title')
    sidebar_id = spec.pop('sidebar_id')
    close_id = spec.pop('close_id')
    sidebar_content_spec = spec.pop('content')
    children = list()
    for row_spec in sidebar_content_spec:
        children.append(
            html.Div(
                _gen_element(row_spec),
                className=f'mb-{SIDE_EACH_MB} mx-{SIDE_EACH_MX}'
            )
        )
    return html.Div(
        html.Div([
            dbc.Row([
                dbc.Col(html.H2(title)),
                dbc.Col(dbc.Button('Close', id=close_id), width='auto')],
                align='center'
            ),
            html.Hr(className='ml-0 mr-0'),
            html.Div(
                children,
                className=f'd-flex flex-column pr-{SIDE_PR} overflow-auto'  # allow space for scroll bar with padding right
            )],
            className=f'd-flex flex-column h-100 p-{SIDE_CONTENT_P}'
        ),
        className='right-side-bar',
        hidden=True,  # default hidden so don't show at startup
        id=sidebar_id
    )


def generate_container(spec: Dict):
    cont_id = spec.pop('container-id')
    cont_children = []
    content_spec = spec.pop('content')
    if type(content_spec) != list:
        raise LayoutException(f'expected content to be list, instead got "{type(content_spec)}"')
    for row_spec in content_spec:
        if type(row_spec) == list:
            row_children = list()
            for i, col_spec in enumerate(row_spec):
                row_children.append(dbc.Col(
                    _gen_element(col_spec),
                    width='auto',
                    className=f'pr-{COL_PAD}' if i == 0 else f'p-{COL_PAD}'
                ))
            cont_children.append(dbc.Row(
                row_children,
                align='center'
            ))
        elif type(row_spec) == dict:
            cont_children.append(_gen_element(row_spec))
        else:
            raise LayoutException(f'expected row spec list/dict, got "{type(row_spec)}"')
    return html.Div(
        html.Div(
            cont_children,
            className='d-flex flex-column h-100'
        ),
        className=f'flex-grow-1 shadow m-{CONT_M} p-{CONT_P}',
        id=cont_id,
        hidden=True  # default hidden so don't show at startup
    )


def generate_header(title, left_spec, right_spec):
    return dbc.Row([
        dbc.Col(
            _gen_element(left_spec) if left_spec else None,
            width=3
        ),
        dbc.Col(
            dbc.Row(
                dbc.Col(html.H1(title), width='auto'),
                justify='center',
                align='center'
            ),
            width=6,
        ),
        dbc.Col(
            _gen_element(right_spec) if right_spec else None,
            width=3
        )],
        align='center',
        className=f'bg-light py-{HEADER_PY} px-{HEADER_PX}'
    )


def generate_nav(nav_spec):
    return html.Div(
        dbc.Nav(
            [html.Div(_gen_element(x), className=f'p-{NAV_P}') for x in nav_spec],
            vertical=True,
            # pills=True,
            className=f'h-100 pt-{NAV_PT}',
        ),
        id='nav-bar',
    )


def generate_layout(layout_spec: ContentSpec):
    nav_spec = layout_spec.pop('navigation')
    nav = generate_nav(nav_spec)

    left_spec = layout_spec.pop('header_left')
    right_spec = layout_spec.pop('header_right')
    title = layout_spec.pop('header_title')
    header = generate_header(title, left_spec, right_spec)

    hidden_specs = layout_spec.pop('hidden_elements')
    hiddens = [_gen_element(x) for x in hidden_specs]

    container_specs = layout_spec.pop('containers')
    containers = [generate_container(x) for x in container_specs]

    sidebar_specs = layout_spec.pop('sidebars')
    sidebars = [generate_sidebar(x) for x in sidebar_specs]

    store_specs = layout_spec.get('stores', [])

    return html.Div([
        dcc.Location(id="url"),
        html.Div(hiddens),
        html.Div([
            dcc.Store(s['id'], storage_type=s.get('storage_type', 'session'), data=s.get('data', None))
            for s in store_specs
        ]),
        html.Div(
            [
                header,
                html.Div(
                    [nav] + containers + sidebars,
                    className='d-flex flex-row flex-grow-1 overflow-hidden'
                ),
                html.Div(id='toast-holder'),
                html.Div(id='test-div')
            ],
            id='browser-container',
            className='d-flex flex-column'
        ),
        html.Div([_gen_element(s) for s in layout_spec['tooltips']])
    ])
