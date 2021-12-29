import uuid
from typing import Optional, Dict, List
from dash import html
from dash import dcc
import dash_bootstrap_components as dbc
from dash import dash_table


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


def container(container_id: str, content: Optional[List]=None, margin=4, padding=4):
    return html.Div(
        html.Div(
            content or [],
            className='d-flex flex-column h-100'
        ),
        className=f'flex-grow-1 shadow m-{margin} p-{padding}',
        id=container_id,
        hidden=True  # default hidden so don't show at startup
    )


def sidebar(sidebar_id: str, sidebar_title: str, close_id: str, content: List, content_padding=2, right_padding=3):
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
                className=f'd-flex flex-column pe-{content_padding} overflow-auto'
                # allow space for scroll bar with padding right
            )],
            className=f'd-flex flex-column h-100 p-{right_padding}'
        ),
        className='right-side-bar',
        hidden=True,  # default hidden so don't show at startup
        id=sidebar_id
    )


def row(row_spec: List, padding=1):
    row_children = list()

    for i, col_children in enumerate(row_spec):
        row_children.append(dbc.Col(
            children=col_children,
            width='auto',
            className=f'pe-{padding}' if i == 0 else f'p-{padding}'
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


def loading(loading_id: str, content: any, load_type='dot'):
    return dcc.Loading(
        id=loading_id,
        type=load_type,
        children=content
    )


def div(div_id: str, css_classes: Optional[str] = None, content: Optional[any] = None):
    return html.Div(id=div_id, className=css_classes or '', children=content)


def table(
        table_id: str,
        columns: Dict[str, str],
        n_rows: int,
        no_fixed_widths=None,
        style_cell=None,
        style_header=None,
        padding_right=1
):
    style_cell = style_cell or {
        'textAlign': 'left',
        'whiteSpace': 'normal',
        'height': 'auto',
        'verticalAlign': 'middle',
        'padding': '0.5rem',
        'border': '1px solid RGBA(255,255,255,0)'
    }
    style_header = style_header or {
        'fontWeight': 'bold',
        'border': 'none'
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
            style_header=style_header,
            style_table={
                'overflowY': 'auto',
            },
            page_size=n_rows,
        ),
        className=f'table-container flex-grow-1 overflow-hidden pe-{padding_right}'
    )


def button(
        button_id: str,
        color: Optional[str] = 'primary',
        btn_icon: Optional[str] = None,
        btn_text: Optional[str] = None,
        css_classes: Optional[str] = None,
        margin_left=2
):
    children = []
    if btn_text is not None:
        children.append(btn_text)
    if btn_icon is not None:
        btn_cls = btn_icon
        if btn_text is not None:
            btn_cls += f' ms-{margin_left}'  # add margin left to icon if text is specified
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
        path: str,
        icon: str,
        header_title: str,
        nav_id: Optional[str] = None,
        notifications_id: Optional[str] = None,
        icon_margin=2,
        badge_padding=2,
        div_padding=3,
        link_margin=2,
        nav_margin=3
):
    return dbc.NavItem(
        dbc.NavLink(
            id=nav_id or str(uuid.uuid4()),
            children=[
                html.I(className=f'{icon} me-{icon_margin}'),
                html.Div([
                    header_title,
                    html.Div(
                        dbc.Badge(
                            id=notifications_id or str(uuid.uuid4()),
                            color='primary',
                            className=f'p-{badge_padding}',
                        ),
                        className='right-corner-box'
                    )
                ], className=f'position-relative pe-{div_padding}')
            ],
            href=path,
            active='exact',
            className=f'position-relative d-flex align-items-center mb-{link_margin}'
        ),
        className=f'ms-{nav_margin}'
    )


