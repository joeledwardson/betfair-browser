from ._intermeds import INTERMEDIARIES
from . import market
from . import runners
from . import logger
from . import orders
from . import strategy
from . import timings


def _libs_loading_spec():
    return {
        'type': 'element-loading',
        'id': 'loading-out-libs'
    }


def _nav_spec():
    return [
        {
            'type': 'element-navigation-item',
            'href': '/',
            'nav_icon': 'fas fa-horse',
        },
        {
            'type': 'element-navigation-item',
            'href': '/strategy',
            'nav_icon': 'fas fa-chess-king'
        },
        {
            'type': 'element-navigation-item',
            'href': '/runners',
            'nav_icon': 'fas fa-running',
        },
        {
            'type': 'element-navigation-item',
            'href': '/timings',
            'nav_icon': 'fas fa-clock'
        },
        {
            'type': 'element-navigation-item',
            'href': '/orders',
            'nav_icon': 'fas fa-file-invoice-dollar'
        },
        # {
        #     'type': 'element-navigation-item',
        #     'href': '/logs',
        #     'nav_icon': 'fas fa-envelope-open-text',
        #     'css_classes': 'position-relative',
        #     'nav_children_spec': [
        #         {
        #             'type': 'element-div',
        #             'id': 'msg-alert-box',
        #             'css_classes': 'right-corner-box',
        #             'hidden': True,
        #             'children_spec': [
        #                 {
        #                     'type': 'element-badge',
        #                     'id': 'log-warns',
        #                     'color': 'danger',
        #                     'css_classes': 'p-2'
        #                 }
        #             ]
        #         }
        #     ]
        # }
    ]


def _reload_button_spec():
    return {
        'type': 'element-button',
        'id': 'button-libs',
        'btn_icon': 'fas fa-book-open',
        'color': 'info'
    }


def get_bf_layout(config):
    hidden_divs = [
        {
            'type': 'element-div',
            'id': x,
            'hidden': True
        }
        for x in INTERMEDIARIES
    ] + [
        {
            'type': 'element-periodic',
            'id': 'interval-component',
            'interval_milliseconds': int(config['CALLBACK_CONFIG']['interval_ms'])
        }
    ]
    return {
        'header_title': 'Betfair Browser',
        'header_left': market.progress_loading_spec(),
        'header_right': {
            'type': 'element-div',
            'css_classes': 'd-flex',
            'children_spec': [
                market.session_loading_spec(),
                runners.runner_loading_spec(),
                runners.figure_loading_spec(),
                _libs_loading_spec(),
                {
                    'type': 'element-div',
                    'css_classes': 'flex-grow-1'
                },
                _reload_button_spec()
            ]
        },
        'navigation': _nav_spec(),
        'hidden_elements': hidden_divs + [
            strategy.strategy_modal_spec()
        ],
        'containers': [
            market.market_display_spec(config),
            runners.runners_config_spec(config),
            # logger.log_config_spec(config),
            orders.orders_config_spec(config),
            strategy.strategy_config_spec(config),
            timings.timings_config_spec(config)
        ],
        'sidebars': [
            market.market_sidebar_spec(),
            runners.runners_sidebar_spec(config),
            strategy.strategy_sidebar_spec()
        ],
        'stores': [
            {
                'id': 'selected-market',
                'data': {}
            },
            {
                'id': 'selected-strategy',
            },
            {
                'id': 'notifications-runners',
            },
            {
                'id': 'notifications-market',
            },
            {
                'id': 'notifications-strategy-reload',
            },
            {
                'id': 'notifications-configs',
            },
            {
                'id': 'notifications-libs',
            },
            {
                'id': 'notifications-strategy',
            },
            {
                'id': 'notifications-figure'
            }
        ]
    }