import itertools
from configparser import ConfigParser
from typing import Optional, Dict, List

from dash.dependencies import Output, Input, State

from mybrowser.session import Session
from .core import triggered_id, CSSClassHandler
from .layout import StoreSpec, ContentSpec, BTN_COLOR


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
    return {
        'type': 'element-tooltip',
        'children_spec': popup,
        'tooltip_target': target,
        'placement': placement
    }


def nav_tooltip(popup: str, target: str):
    return tooltip(popup, target, placement='right')


def wrapper(wrapper_id, content):
    return {
        'type': 'element-div',
        'id': wrapper_id,
        'children_spec': content
    }


def header(title: str):
    return {
        'type': 'element-header',
        'children_spec': title,
    }


def button(
        button_id,
        color: Optional[str] = BTN_COLOR,
        btn_icon: Optional[str] = None,
        btn_text: Optional[str] = None,
        css_classes: Optional[str] = None):
    return {
        'type': 'element-button',
        'id': button_id,
        'btn_icon': btn_icon,
        'btn_text': btn_text,
        'color': color,
        'css_classes': css_classes
    }


def stylish_select(
        placeholder: str,
        select_options: List,
        clear_id: str,
        select_id: str,
        css_classes: str = None
):
    return {
        'type': 'element-stylish-select',
        'placeholder': placeholder,
        'select_options': select_options,
        'clear_id': clear_id,
        'id': select_id,
        'css_classes': css_classes or ''
    }


def nav_element(
        path: str, icon: str, header: str, nav_id: Optional[str] = None, notifications_id: Optional[str] = None
) -> Dict:
    return {
        'type': 'element-navigation-item',
        'css_classes': 'ml-3',
        'nav_css_classes': 'position-relative d-flex align-items-center mb-2',
        'href': path,
        'id': nav_id,
        'children_spec': [
            {
                'type': 'element-fontawesome',
                'css_classes': icon + ' mr-2'
            },
            {
                'type': 'element-div',
                'css_classes': 'position-relative pr-3',
                'children_spec': [
                    header,
                    {
                        'type': 'element-div',
                        'css_classes': 'right-corner-box',
                        'children_spec': [
                            {
                                'type': 'element-badge',
                                'color': 'primary',
                                'css_classes': 'p-2',
                            } | (
                                {'id': notifications_id} if notifications_id else {}
                            )
                        ]
                    }
                ],
            }
        ]
    }


class Component:
    LOADING_ID = None
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