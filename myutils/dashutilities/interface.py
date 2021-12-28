import uuid
from typing import Optional, Dict, List
from dash import html
from dash import dcc
import dash_bootstrap_components as dbc
from dash import dash_table
from .layout import BTN_COLOR
from . import layout


def tooltip(popup: str, target: str, placement="top"):
    return dbc.Tooltip(
        children=popup,
        target=target,
        placement=placement,
    )


def modal(modal_id: str, header_spec: any, footer_spec: any):
    return dbc.Modal([
        dbc.ModalHeader(header_spec),
        dbc.ModalFooter(footer_spec)
    ], id=modal_id)


def nav_tooltip(popup: str, target: str):
    return tooltip(popup, target, placement='right')


def wrapper(wrapper_id: str, content: any):
    return html.Div(id=wrapper_id, children=content)


def header(title: str):
    return html.H2(title)


def container(container_id: str, content: Optional[List]):
    return html.Div(
        html.Div(
            content or [],
            className='d-flex flex-column h-100'
        ),
        className=f'flex-grow-1 shadow m-{layout.CONT_M} p-{layout.CONT_P}',
        id=container_id,
        hidden=True  # default hidden so don't show at startup
    )


def sidebar(sidebar_id: str, sidebar_title: str, close_id: str, content: List):
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


def row(row_spec: List):
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


def tabs(tabs_id: str):
    return dbc.Tabs(
        id=tabs_id,
    )


def loading(loading_id: str, content: any):
    return dcc.Loading(
        id=loading_id,
        type=layout.LOAD_TYPE,
        children=content
    )


def div(div_id: str, css_classes: Optional[str] = None, content: Optional[any] = None):
    return html.Div(id=div_id, className=css_classes or '', children=content)


def table(table_id: str, columns: Dict[str, str], n_rows: int, no_fixed_widths=None):
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
            id=table_id,
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
        button_id: str,
        color: Optional[str] = BTN_COLOR,
        btn_icon: Optional[str] = None,
        btn_text: Optional[str] = None,
        css_classes: Optional[str] = None
):
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


def store(store_id: str, data: Optional[any] = None, storage_type='session'):
    return dcc.Store(id=store_id, storage_type=storage_type, data=data)


def select(select_id: str, placeholder: str):
    return dcc.Dropdown(
        id=select_id,
        placeholder=placeholder
    )


def input_component(input_id: str, type=None, step=None, value=None, placeholder=None):
    return dbc.Input(id=input_id, type=type, step=step, value=value, placeholder=placeholder)


def input_group(children_spec: any):
    return dbc.InputGroup(children_spec)


def input_group_addon(children_spec: any):
    return dbc.InputGroupText(children_spec)


def bootstrap_select(
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


def nav(
        path: str, icon: str, header_title: str, nav_id: Optional[str] = None, notifications_id: Optional[str] = None
):
    return dbc.NavItem(
        dbc.NavLink(
            id=nav_id or str(uuid.uuid4()),
            children=[
                html.I(className=f'{icon} me-2'),
                html.Div([
                    header_title,
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


