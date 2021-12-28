import itertools
import uuid
from configparser import ConfigParser
from typing import Optional, Dict, List
from dash import html
import json
from dash import dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Output, Input, State
from dash import dash_table

from mybrowser.session import Session
from .core import triggered_id, CSSClassHandler
from .layout import StoreSpec, ContentSpec, BTN_COLOR
from . import layout

def right_panel_callback(app, panel_id: str, open_id: str, close_id: str):
    """
    toggle "right-not-collapsed" css class to open and close a side panel based on open/close buttons
    """
    @app.callback(
        Output(panel_id, "className"),
        [
            Input(open_id, "n_clicks"),
            Input(close_id, "n_clicks")
        ],
        State(panel_id, "className")
    )
    def toggle_classname(n1, n2, class_names: str):
        # CSS class toggles sidebar
        classes = CSSClassHandler(class_names)
        if triggered_id() == open_id:
            return str(classes + "right-not-collapsed")
        else:
            return str(classes - "right-not-collapsed")


def notification_clear(app, nav_notification_id: str, button_id: str):
    @app.callback(Output(nav_notification_id, 'children'), Input(button_id, 'n_clicks'))
    def _(n_clicks):
        return None


def tooltip(popup: str, target: str, placement="top"):
    return dbc.Tooltip(
        children=popup,
        target=target,
        placement=placement,
    )


def modal(id: str, header_spec: any, footer_spec: any):
    return dbc.Modal([
        dbc.ModalHeader(header_spec),
        dbc.ModalFooter(footer_spec)
    ], id=id)


def nav_tooltip(popup: str, target: str):
    return tooltip(popup, target, placement='right')


def wrapper(wrapper_id, content):
    return html.Div(id=wrapper_id, children=content)


def header(title: str):
    return html.H2(title)


def container_element(container_id: str, content: Optional[List]):
    return html.Div(
        html.Div(
            content or [],
            className='d-flex flex-column h-100'
        ),
        className=f'flex-grow-1 shadow m-{layout.CONT_M} p-{layout.CONT_P}',
        id=container_id,
        hidden=True  # default hidden so don't show at startup
    )


def sidebar_container(sidebar_id: str, sidebar_title: str, close_id: str, content: List):
    return html.Div(
        html.Div([
            dbc.Row([
                dbc.Col(html.H2(sidebar_title)),
                dbc.Col(dbc.Button('Close', id=close_id), width='auto')],
                align='center'
            ),
            html.Hr(className='ms-0 me-0'),
            html.Div(
                content,
                className=f'd-flex flex-column pe-{layout.SIDE_PR} overflow-auto'  # allow space for scroll bar with padding right
            )],
            className=f'd-flex flex-column h-100 p-{layout.SIDE_CONTENT_P}'
        ),
        className='right-side-bar',
        hidden=True,  # default hidden so don't show at startup
        id=sidebar_id
    )


def container_row(row_spec: List):
    row_children = list()

    for i, col_children in enumerate(row_spec):
        row_children.append(dbc.Col(
            children=col_children,
            width='auto',
            className=f'pe-{layout.COL_PAD}' if i == 0 else f'p-{layout.COL_PAD}'
        ))
    return dbc.Row(row_children, align='center')


def markdown(text: str, css_classes: Optional[str] = None):
    return dcc.Markdown(
        children=text,
        className=css_classes or '',
    )


def element_tabs(id: str):
    return dbc.Tabs(
        id=id,
    )


def loading_container(id: str, content):
    return dcc.Loading(
        id=id,
        type=layout.LOAD_TYPE,
        children=content
    )


def element_div(id: str, css_classes: Optional[str] = None, content: Optional[any] = None):
    return html.Div(id=id, className=css_classes or '', children=content)


def element_table(id: str, columns, n_rows, no_fixed_widths=None):
    style_cell = {
        'textAlign': 'left',
        'whiteSpace': 'normal',
        'height': 'auto',
        'verticalAlign': 'middle',
        'padding': '0.5rem',
        'border': '1px solid RGBA(255,255,255,0)'
    }
    if no_fixed_widths is None:
        style_cell |= {
            'maxWidth': 0  # fix column widths
        }
    return html.Div(
        dash_table.DataTable(
            id=id,
            columns=[
                dict(name=v, id=k)
                for k, v in columns.items()
            ],
            style_cell=style_cell,
            style_header={
                'fontWeight': 'bold',
                'border': 'none'
            },
            style_table={
                'overflowY': 'auto',
            },
            page_size=n_rows,
        ),
        className='table-container flex-grow-1 overflow-hidden pe-1'
    )


def button(
        button_id,
        color: Optional[str] = BTN_COLOR,
        btn_icon: Optional[str] = None,
        btn_text: Optional[str] = None,
        css_classes: Optional[str] = None):
    children = []
    if btn_text is not None:
        children.append(btn_text)
    if btn_icon is not None:
        btn_cls = btn_icon
        if btn_text is not None:
            btn_cls += f' ms-{layout.BTN_ML}'  # add margin left to icon if text is specified
        children.append(html.I(className=btn_cls))
    return dbc.Button(
        children,
        id=button_id,
        n_clicks=0,
        color=color,
        className=css_classes or ''
    )


def store(id: str, data: Optional[any] = None, storage_type='session'):
    return dcc.Store(id=id, storage_type=storage_type, data=data)


def normal_select(id: str, placeholder: str):
    return dcc.Dropdown(
        id=id,
        placeholder=placeholder
    )


def component_input(id: str, type=None, step=None, value=None, placeholder=None):
    return dbc.Input(id=id, type=type, step=step, value=value, placeholder=placeholder)


def input_group(children_spec):
    return dbc.InputGroup(children_spec)


def input_group_addon(children_spec):
    return dbc.InputGroupText(children_spec)


def stylish_select(
        placeholder: str,
        select_options: List,
        clear_id: str,
        select_id: str,
        css_classes: str = None
):
    return dbc.ButtonGroup(
        [
            dbc.Select(
                id=select_id,
                placeholder=placeholder,
                options=select_options,
            ),
            dbc.Button(
                [html.I(className="fas fa-times-circle")],
                id=clear_id,
                color='secondary'
            ),
        ],
        className=css_classes
    )


def nav_element(
        path: str, icon: str, header: str, nav_id: Optional[str] = None, notifications_id: Optional[str] = None
):
    return dbc.NavItem(
        dbc.NavLink(
            id=nav_id or str(uuid.uuid4()),
            children=[
                html.I(className=f'{icon} me-2'),
                html.Div([
                    header,
                    html.Div(
                        dbc.Badge(
                            id=notifications_id or str(uuid.uuid4()),
                            color='primary',
                            className='p-2',
                        ),
                        className='right-corner-box'
                    )
                ], className='position-relative pe-3')
            ],
            href=path,
            active='exact',
            className='position-relative d-flex align-items-center mb-2'
        ),
        className='ms-3'
    )


class Component:
    NOTIFICATION_ID = None
    PATHNAME = None
    CONTAINER_ID = None
    SIDEBAR_ID = None

    def nav_items(self, config: ConfigParser) -> Optional[Dict]:
        return None

    def modal_specs(self, config: ConfigParser) -> List[Dict]:
        return []

    def display_spec(self, config: ConfigParser) -> Optional[Dict]:
        return None

    def callbacks(self, app, shn: Session, config: ConfigParser) -> None:
        pass

    def sidebar(self, config: ConfigParser) -> Optional[Dict]:
        return None

    def loading_ids(self) -> List[str]:
        return []

    def header_right(self, config: ConfigParser) -> Optional[Dict]:
        return None

    def additional_stores(self) -> List[StoreSpec]:
        return []

    def tooltips(self, config: ConfigParser) -> List[Dict]:
        return []


def components_layout(components: List[Component], title: str, config: ConfigParser) -> ContentSpec:
    not_none = lambda lst: [x for x in lst if x is not None]
    return ContentSpec(**{
        'header_title': title,
        'header_left': {},
        'header_right': {
            'type': 'element-div',
            'css_classes': 'd-flex',
            'children_spec': [
                {
                    'type': 'element-loading',
                    'id': 'loading-container',
                    'children_spec': [
                        {
                            'type': 'element-div',
                            'id': c.LOADING_ID
                        } for c in components if c.LOADING_ID
                    ]
                },
                {
                    'type': 'element-div',
                    'css_classes': 'flex-grow-1'
                },
                *not_none([c.header_right(config) for c in components])
            ]
        },
        'navigation': not_none([c.nav_items(config) for c in components]),
        'hidden_elements': list(itertools.chain(*[c.modal_specs(config) for c in components])),
        'containers': not_none([c.display_spec(config) for c in components]),
        'sidebars': not_none([c.sidebar(config) for c in components]),
        'stores': list(itertools.chain(*[
            c.additional_stores() for c in components
        ])) + [{
            'id': c.NOTIFICATION_ID
        } for c in components if c.NOTIFICATION_ID],
        'tooltips': list(itertools.chain.from_iterable(c.tooltips(config) for c in components))
    })


def components_callback(app, components: List[Component]):
    output_ids = [c.CONTAINER_ID for c in components if c.CONTAINER_ID]
    output_ids += [c.SIDEBAR_ID for c in components if c.SIDEBAR_ID]
    outputs = [Output(o, "hidden") for o in output_ids]

    @app.callback(outputs, Input("url", "pathname"))
    def render_page_content(pathname):
        displays = []
        for c in components:
            if pathname == c.PATHNAME:
                if c.CONTAINER_ID:
                    displays.append(c.CONTAINER_ID)
                if c.SIDEBAR_ID:
                    displays.append(c.SIDEBAR_ID)
        return [not(o in displays) for o in output_ids]

