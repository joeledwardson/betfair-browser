from typing import Dict, List
import itertools
import json


def _sort_labels(sort_options: Dict) -> List[Dict]:
    return list(itertools.chain(*[
        [
            {
                'label': f'▲ {v}',
                'value': json.dumps({
                    'db_col': k,
                    'asc': True
                })
            },
            {
                'label': f'▼ {v}',
                'value': json.dumps({
                    'db_col': k,
                    'asc': False
                })
            }
        ]
        for k, v in sort_options.items()
    ]))


def session_loading_spec():
    return {
        'type': 'element-loading',
        'id': 'loading-out-session'
    }


def progress_loading_spec():
    return {
        'type': 'element-div',
        'id': 'progress-container-div',
        'children_spec': [
            {
                'type': 'element-progress',
                'id': 'header-progress-bar',
                'element_kwargs': {
                    'striped': True,
                    'animated': True,
                }
            }
        ]
    }


def market_display_spec(config):
    sort_options = dict(config['MARKET_SORT_OPTIONS'])
    n_mkt_rows = int(config['TABLE']['market_rows'])
    full_tbl_cols = dict(config['MARKET_TABLE_COLS'])
    options_labels = _sort_labels(sort_options)
    return {
        'container-id': 'container-market',
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Market Browser',
                }, {
                    'type': 'element-button',
                    'id': 'btn-session-filter',
                    'btn_icon': 'fas fa-filter',
                }, {
                    'type': 'element-button',
                    'id': 'btn-db-reconnect',
                    'btn_icon': 'fas fa-database',
                }, {
                    'type': 'element-navigation-button',
                    'id': 'nav-runners',
                    'href': '/runners',
                    'btn_id': 'button-runners',
                    'btn_icon': 'fas fa-download'
                }
            ],
            [
                {
                    'type': 'element-button',
                    'id': 'btn-db-refresh',
                    'btn_icon': 'fas fa-sync-alt',
                    'btn_text': 'Reload'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-db-upload',
                    'btn_icon': 'fas fa-arrow-circle-up',
                    'btn_text': 'Upload Cache'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-cache-clear',
                    'btn_icon': 'fas fa-trash',
                    'btn_text': 'Clear Cache',
                    'color': 'warning'
                }
            ],
            [
                {
                    'type': 'element-stylish-select',
                    'id': 'market-sorter',
                    'placeholder': 'Market Sort...',
                    'select_options': options_labels,
                    'clear_id': 'btn-sort-clear'
                },
                {
                    'type': 'element-button',
                    'id': 'input-strategy-clear',
                    'btn_icon': 'fas fa-times-circle',
                    'btn_text': 'Clear Strategy',
                    'color': 'info'
                }
            ],
            [
                {
                    'type': 'element-div',
                    'id': 'market-query-status'
                }
            ],
            {
                'type': 'element-table',
                'id': 'table-market-session',
                'columns': full_tbl_cols,
                'n_rows': n_mkt_rows
            }
        ],
    }


def market_sidebar_spec():
    return {
        'sidebar_id': 'container-filters-market',
        'sidebar_title': 'Market Filters',
        'close_id': 'btn-right-close',
        'content': [
            {
                'type': 'element-select',
                'id': 'input-sport-type',
                'placeholder': 'Sport...'
            },
            {
                'type': 'element-select',
                'id': 'input-mkt-type',
                'placeholder': 'Market type...',
            },
            {
                'type': 'element-select',
                'id': 'input-bet-type',
                'placeholder': 'Betting type...',
            },
            {
                'type': 'element-select',
                'id': 'input-format',
                'placeholder': 'Format...'
            },
            {
                'type': 'element-select',
                'id': 'input-country-code',
                'placeholder': 'Country...'
            },
            {
                'type': 'element-select',
                'id': 'input-venue',
                'placeholder': 'Venue...'
            },
            {
                'type': 'element-select',
                'id': 'input-date',
                'placeholder': 'Market date...'
            },
            {
                'type': 'element-input',
                'id': 'input-mkt-id',
                'element_kwargs': {
                    'placeholder': 'Market ID filter...',
                }
            },
            {
                'type': 'element-button',
                'id': 'input-mkt-clear',
                'btn_icon': 'fas fa-times-circle',
                'btn_text': 'Clear Filters'
            }
        ]
    }

