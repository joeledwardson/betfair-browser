from __future__ import annotations
import re
import traceback
import itertools
from dash import html
import json
from dash import dcc
import dash_bootstrap_components as dbc
from configparser import ConfigParser
from dash.dependencies import Output, Input, State
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union, Any
import importlib.resources as pkg_resources
import dataclasses

from .session.config import MarketFilter, DisplayConfig
from myutils import general
from myutils.dashutilities.triggered import triggered_id, all_triggered_ids
from myutils.dashutilities.csshandler import CSSClassHandler
from myutils.dashutilities.callbacks import TDict, dict_callback
from myutils import timing

from mytrading.strategy.feature.features import RFBase
from mytrading.strategy import tradetracker as tt
from .session import Session, post_notification, LoadedMarket, Notification, NotificationType
from .error_catcher import handle_errors, exceptions
from myutils.dashutilities import interface as intf


def notification_clear(app, nav_notification_id: str, button_id: str):
    @app.callback(Output(nav_notification_id, 'children'), Input(button_id, 'n_clicks'))
    def _(n_clicks):
        return None


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


@dataclasses.dataclass(kw_only=True)
class Component:
    pathname: Optional[str] = None
    container_id: Optional[str] = None
    notification_id: Optional[str] = None
    sidebar_id: Optional[str] = None
    loading_id: Optional[str] = None

    def nav_item(self) -> Optional[dbc.NavItem]:
        return None

    def modals(self) -> List[dbc.Modal]:
        return []

    def display_spec(self) -> Optional[html.Div]:
        return None

    def callbacks(self, app, shn: Session) -> None:
        pass

    def sidebar(self) -> Optional[html.Div]:
        return None

    def loading_ids(self) -> List[str]:
        return []

    def header_right(self) -> Optional[Any]:
        return None

    def additional_stores(self) -> List[dcc.Store]:
        return []

    def tooltips(self) -> List[Dict]:
        return []


@dataclasses.dataclass(kw_only=True)
class TableComponent:
    n_table_rows: int
    table_columns: Dict[str, str]


def components_callback(app, components: List[Component]):
    output_ids = [c.container_id for c in components if c.container_id]
    output_ids += [c.sidebar_id for c in components if c.sidebar_id]
    outputs = [Output(o, "hidden") for o in output_ids]

    @app.callback(outputs, Input("url", "pathname"))
    def render_page_content(pathname):
        displays = []
        for c in components:
            if pathname == c.pathname:
                if c.container_id:
                    displays.append(c.container_id)
                if c.sidebar_id:
                    displays.append(c.sidebar_id)
        return [not(o in displays) for o in output_ids]


@dataclasses.dataclass(kw_only=True)
class OverviewComponent(Component):
    def display_spec(self) -> Optional[html.Div]:
        md = pkg_resources.read_text('mybrowser', 'guide.md')
        return intf.container(self.container_id, [intf.markdown(
            md,
            'overflow-auto markdown-body' # use to get the github markdown styles form
        )])

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(
            self.pathname, 'fas fa-info-circle', 'Guide'
        )


@dataclasses.dataclass(kw_only=True)
class MarketComponent(Component, TableComponent):
    market_filters: List[MarketFilter]
    sort_options: Dict[str, str]
    runner_button_id: str
    enable_cache: bool

    def _sort_labels(self, sort_options: Dict) -> List[Dict]:
        return general.flatten([
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
        ])

    def display_spec(self):
        children = [
            intf.row([
                intf.header('Market Browser'),
                intf.wrapper(
                    'market-filter-wrapper',
                    intf.button('btn-session-filter', btn_icon='fas fa-filter')
                ),
                intf.wrapper(
                    'db-reconnect-wrapper',
                    intf.button('btn-db-reconnect', btn_icon='fas fa-database')
                ),
                intf.wrapper(
                    'market-download-wrapper',
                    intf.button(self.runner_button_id, btn_icon='fas fa-download', color='info')
                )
            ])
        ]

        if self.enable_cache:
            children.append(intf.row([
                intf.button('btn-db-upload', btn_icon='fas fa-arrow-circle-up', btn_text='Upload Cache'),
                intf.button('btn-cache-clear', btn_icon='fas fa-trash', btn_text='Clear Cache', color='warning'),
                intf.button('btn-db-refresh', btn_icon='fas fa-sync-alt', btn_text='Reload')
            ]))

        options_labels = self._sort_labels(self.sort_options)
        children += [
            intf.row([
                intf.bootstrap_select(
                    select_id='market-sorter',
                    placeholder='Market Sort...',
                    select_options=options_labels,
                    clear_id='btn-sort-clear'
                ),
                intf.button(
                    button_id='input-strategy-clear',
                    btn_icon='fas fa-times-circle',
                    btn_text='Clear Strategy',
                    color='info'
                )
            ]),
            intf.div('market-query-status'),
            intf.table('table-market-session', self.table_columns, self.n_table_rows)
        ]

        return intf.container(self.container_id, children)

    def sidebar(self):
        filters = [flt.component for flt in self.market_filters]
        filters.append(intf.button('input-mkt-clear', btn_icon='fas fa-times-circle', btn_text='Clear Filters'))
        return intf.sidebar(
            self.sidebar_id,
            sidebar_title='Market Filters',
            close_id='btn-market-filters-close',
            content=filters
        )

    def callbacks(self, app, shn: Session):
        right_panel_callback(app, "container-filters-market", "btn-session-filter", "btn-market-filters-close")
        notification_clear(app, 'nav-notifications-market', 'nav-markets')

        @app.callback(
            output=Output('market-sorter', 'value'),
            inputs=Input('btn-sort-clear', 'n_clicks'),
        )
        def market_sort_clear(n_clicks):
            return None

        buttons = [
            'input-mkt-clear',
            'input-strategy-clear',
            'btn-db-reconnect',
            # 'btn-strategy-run',
            'btn-strategy-download'
        ]
        if self.enable_cache:
            buttons += [
                'btn-db-upload',
                'btn-cache-clear',
                'btn-db-refresh'
            ]

        @dict_callback(
            app=app,
            outputs_config={
                'query-status': Output('market-query-status', 'children'),
                'table-data': Output('table-market-session', 'data'),
                'table-selected-cells': Output('table-market-session', "selected_cells"),
                'table-active-cell': Output('table-market-session', 'active_cell'),
                'table-current-page': Output('table-market-session', 'page_current'),
                'loading': Output(self.loading_id, 'children'),
                'notifications': Output(self.notification_id, 'data'),
                'strategy-id': Output('selected-strategy', 'data'),
                'filter-values': [
                    Output(flt.component_id, 'value')
                    for flt in self.market_filters
                ],
                'filter-options': [
                    Output(flt.component_id, 'options')
                    for flt in self.market_filters if flt.filter and flt.filter.HAS_OPTIONS
                ],
                'market-notifications': Output('nav-notifications-market', 'children')
            },
            inputs_config={
                'buttons': [
                    Input(x, 'n_clicks')
                    for x in buttons
                ],
                'sorter': Input('market-sorter', 'value'),
                'filter-inputs': {
                    flt.filter.db_col: Input(flt.component_id, 'value')
                    for flt in self.market_filters
                }
            },
            states_config={
                # 'strategy-run': State('input-strategy-run', 'value'),
                'strategy-cell': State('table-strategies', 'active_cell'),
                'strategy-id': State('selected-strategy', 'data'),
            },
        )
        def market_callback(outputs: TDict, inputs: TDict, states: TDict):
            notifs = outputs['notifications'] = []
            outputs['filter-options'] = [list() for _ in outputs['filter-options']]  # set options empty in case of error
            outputs['table-data'] = []  # set table empty in case of error
            outputs['strategy-id'] = states['strategy-id']

            @handle_errors(notifs, 'Market')
            def process():
                btn_id = triggered_id()
                strategy_id = states['strategy-id']
                filter_inputs = inputs['filter-inputs']

                # wipe cache if requested
                if btn_id == 'btn-cache-clear':
                    n_files, n_dirs = shn.betting_db.wipe_cache()
                    post_notification(notifs, 'info', 'Cache', f'Cleared {n_files} files and {n_dirs} dirs from cache')

                # TODO - move all strategy functions from here to strategy page
                # reconnect to database if button pressed
                if btn_id == 'btn-db-reconnect':
                    shn.reload_database()
                    post_notification(notifs, 'info', 'Database', 'reconnected to database')

                # upload market & strategy cache if "upload" button clicked
                if btn_id == 'btn-db-upload':
                    n_mkt = len(shn.betting_db.scan_mkt_cache())
                    n_strat = len(shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits))
                    post_notification(notifs, 'info', 'Cache', f'found {n_mkt} new markets in cache')
                    post_notification(notifs, 'info', 'Cache', f'found {n_strat} new strategies in cache')

                # update strategy filters and selectable options
                if btn_id == 'btn-strategy-download':
                    strategy_cell = states['strategy-cell']
                    outputs['market-notifications'] = '1'
                    if isinstance(strategy_cell, dict) and 'row_id' in strategy_cell:
                        strategy_id = strategy_cell['row_id']
                    else:
                        post_notification(notifs, 'danger', 'Strategy', 'no row ID found in strategy cell')
                        strategy_id = None

                # clear strategy ID variable used in market filtering if "clear strategy" button clicked
                if btn_id in ['input-strategy-clear', 'btn-db-reconnect', 'btn-strategy-delete']:
                    post_notification(notifs, 'info', 'Strategy', 'strategy cleared')
                    strategy_id = None

                # update market filters and selectable options
                clear = btn_id in ['input-mkt-clear', 'btn-db-reconnect']
                filter_inputs = {k: None if clear else v for k, v in filter_inputs.items()}
                column_filters = shn.market_filter_conditions(list(filter_inputs.values()))
                cte = shn.betting_db.filters_mkt_cte(strategy_id, column_filters)

                market_sorter = inputs['sorter']
                if btn_id == 'btn-sort-clear':
                    market_sorter = None
                if market_sorter:
                    dropdown_dict = json.loads(market_sorter)
                    order_col = dropdown_dict.get('db_col')
                    order_asc = dropdown_dict.get('asc')
                else:
                    order_col, order_asc = None, None

                # query db with filtered CTE to generate table rows for display
                tbl_rows = shn.mkt_tbl_rows(cte, order_col, order_asc)

                # assign 'id' so market ID set in row ID read in callbacks
                for r in tbl_rows:
                    r['id'] = r['market_id']

                # generate status string of markets/strategies available and strategy selected
                n = shn.betting_db.cte_count(cte)
                ns = shn.betting_db.strategy_count()
                active_filters = [nm for nm in filter_inputs if filter_inputs[nm] != None]
                filter_msg = 'Filters: ' + ', '.join(nm for nm in active_filters)
                msg = f'Showing {n} markets, ' + (filter_msg if active_filters else 'no filters')
                post_notification(notifs, 'info', 'Market Database', msg)

                outputs['query-status'] = [
                    html.Div(f'Showing {len(tbl_rows)} of {n} available, {ns} strategies available'),
                    html.Div(
                        f'strategy ID: {strategy_id}'
                        if strategy_id is not None else 'No strategy selected'
                    )
                ]  # table query status
                outputs['filter-options'] = shn.betting_db.filters_labels(shn.filters_mkt, cte)
                outputs['table-data'] = tbl_rows  # set market table row data
                outputs['filter-values'] = list(filter_inputs.values())
                outputs['strategy-id'] = strategy_id

            process()
            outputs['table-selected-cells'] = []  # clear selected cell(s)
            outputs['table-active-cell'] = None  # clear selected cell(s)
            outputs['table-current-page'] = 0  # reset current page back to first page
            outputs['loading'] = ''  # blank loading output

    def loading_ids(self) -> List[str]:
        return [self.loading_id]

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(
            self.pathname, 'fas fa-horse', 'Markets',
            nav_id='nav-markets',
            notifications_id='nav-notifications-market'
        )

    def additional_stores(self) -> List[dcc.Store]:
        return [intf.store('selected-market')]

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('Navigate historic betfair markets', 'nav-markets'),
            intf.tooltip('Filter market table', 'market-filter-wrapper'),
            intf.tooltip('Reconnect to database', 'db-reconnect-wrapper'),
            intf.tooltip('Load runners from selected market in table', 'market-download-wrapper'),
        ]


@dataclasses.dataclass(kw_only=True)
class RunnersComponent(Component, TableComponent):
    default_offset: str
    runner_button_id: str
    enable_reloads: bool

    def loading_ids(self) -> List[str]:
        return [self.loading_id]

    def display_spec(self):
        return intf.container(self.container_id, [
            intf.row([
                intf.header('Runner Info'),
                intf.wrapper(
                    'runners-filter-wrapper',
                    intf.button('btn-runners-filter', btn_icon='fas fa-bars'),
                ),
                intf.wrapper(
                    'market-bin-wrapper',
                    intf.button('button-mkt-bin', btn_icon='fas fa-trash', color='warning')
                ),
            ]),
            intf.row([
                intf.wrapper(
                    'orders-button-wrapper',
                    intf.button('button-orders', btn_icon='fas fa-file-invoice-dollar', btn_text='Orders', color='info')
                ),
                intf.wrapper(
                    'figure-button-wrapper',
                    intf.button('button-figure', btn_icon='fas fa-chart-line', btn_text='Figure')
                ),
                intf.wrapper(
                    'all-figures-wrapper',
                    intf.button('button-all-figures', btn_icon='fas fa-chart-line', btn_text='All Figures')
                ),
            ]),
            intf.div('infobox-market'),
            intf.table('table-runners', self.table_columns, self.n_table_rows)
        ])

    def callbacks(self, app, shn: Session):
        right_panel_callback(app, "container-filters-plot", "btn-runners-filter", "btn-plot-close")
        notification_clear(app, 'nav-notification-runners', 'nav-runners')

        def get_config_options():
            feature_keys = list(shn.feature_configs.keys())
            config_keys = [k for k in shn.plot_configs.keys() if k in feature_keys]
            plot_options = [{
                'label': v,
                'value': v,
            } for v in config_keys]
            return plot_options

        if self.enable_reloads:
            @app.callback(
                Output('input-plot-config', 'options'),
                Input('btn-reload-configs', 'n_clicks')
            )
            def reload(_):
                shn.update_configs()
                return get_config_options()

        @app.callback(
            Output('input-plot-config', 'options'),
            Input('btn-runners-filter', 'n_clicks')
        )
        def configs(_):
            return get_config_options()

        @dict_callback(
            app=app,
            outputs_config={
                'table': Output('table-runners', 'data'),
                'info': Output('infobox-market', 'children'),
                'disable-bin': Output('button-mkt-bin', 'disabled'),
                'disable-figures': Output('button-all-figures', 'disabled'),
                'cell': Output('table-runners', 'active_cell'),
                'cells': Output('table-runners', 'selected_cells'),
                'loading': Output(self.loading_id, 'children'),
                'selected-market': Output('selected-market', 'data'),
                'notifications': Output(self.notification_id, 'data'),
                'nav-notifications': Output('nav-notification-runners', 'children'),
            },
            inputs_config={
                'buttons': [
                    Input(self.runner_button_id, 'n_clicks'),
                    Input('button-mkt-bin', 'n_clicks')
                ]
            },
            states_config={
                'cell': State('table-market-session', 'active_cell'),
                'strategy-id': State('selected-strategy', 'data')
            }
        )
        def runners_callback(outputs: TDict, inputs: TDict, states: TDict):
            """
            update runners table and market information table, based on when "get runners" button is clicked
            update data in runners table, and active file indicator when runners button pressed
            """
            outputs['table'] = []  # empty table
            outputs['info'] = html.P('no market selected'),  # market status
            outputs['disable-bin'] = True,  # by default assume market not loaded, bin market button disabled
            outputs['disable-figures'] = True  # by default assume market not loaded, figures button disabled
            outputs['cell'] = None  # reset active cell
            outputs['cells'] = []  # reset selected cells
            outputs['loading'] = ''  # blank loading output
            outputs['selected-market'] = {}  # blank selected market by default
            notifs = outputs['notifications'] = []

            # check for first callback call
            if triggered_id() not in [self.runner_button_id, 'button-mkt-bin']:
                return

            # market clear
            if triggered_id() == 'button-mkt-bin':
                post_notification(notifs, "info", 'Market', 'Cleared market')
                return

            cell = states['cell']
            if not cell:
                post_notification(notifs, "danger", 'Market', 'No active cell to get market')
                return

            market_id = cell['row_id']
            if not market_id:
                post_notification(notifs, "warning", 'Market', 'row ID from cell is blank')
                return

            strategy_id = states['strategy-id']
            try:
                loaded_market = shn.market_load(market_id, strategy_id)
                info_str = f'Loaded market "{market_id}" with strategy "{strategy_id}"'
                post_notification(notifs, "info", 'Market', info_str)
            except exceptions as e:
                post_notification(notifs, 'warning', 'Market', f'failed to load market: {e}\n{traceback.format_exc()}')
                return

            tbl = [d | {
                'id': d['runner_id'],  # set row to ID for easy access in callbacks
            } for d in loaded_market['runners'].values()]

            # serialise market info
            shn.serialise_loaded_market(loaded_market)

            outputs['table'] = sorted(tbl, key=lambda d: d['starting_odds'])
            outputs['info'] = f'loaded "{market_id}"'
            outputs['disable-bin'] = False  # enable bin market button
            outputs['disable-figures'] = False  # enable plot all figures button
            outputs['selected-market'] = loaded_market
            outputs['nav-notifications'] = '1'
            return

        @app.callback(
            [
                Output('button-figure', 'disabled'),
                Output('button-orders', 'disabled')
            ], [
                Input('table-runners', 'active_cell')
            ], [
                State('selected-market', 'data')
            ]
        )
        def fig_btn_disable(active_cell, loaded_market: LoadedMarket):
            disable_figure = True
            disable_orders = True

            if active_cell is not None and 'row_id' in active_cell:
                disable_figure = False
                if loaded_market['strategy_id'] is not None:
                    disable_orders = False

            return disable_figure, disable_orders

    def sidebar(self) -> Optional[html.Div]:
        reload_buttons = []
        if self.enable_reloads:
            reload_buttons.append(
                intf.button('btn-reload-configs', btn_text='Reload configurations')
            )

        return intf.sidebar(
            self.sidebar_id,
            sidebar_title='Plot Config',
            close_id='btn-plot-close',
            content=[
                intf.select('input-plot-config', placeholder='Plot config...'),
                intf.input_group([
                    intf.input_group_addon('Input offset: '),
                    intf.input_component(
                        input_id='input-chart-offset',
                        type='time',
                        step='1',  # forces HTML to use hours, minutes and seconds format
                        value=self.default_offset
                    )
                ])
            ] + reload_buttons
        )

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(
            self.pathname, 'fas fa-running', 'Runners',
            nav_id='nav-runners',
            notifications_id='nav-notification-runners'
        )

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('Navigate race runners from loaded market', 'nav-runners'),
            intf.tooltip('Select figure plot configuration', 'runners-filter-wrapper'),
            intf.tooltip('Clear loaded runners\n(market must be loaded first)', 'market-bin-wrapper'),
            intf.tooltip('Show runner orders\n(strategy must be downloaded to market)', 'orders-button-wrapper'),
            intf.tooltip('Plot figure for select runner\n(runner must be selected from table)', 'figure-button-wrapper'),
            intf.tooltip('Plot all figures\n(market must be loaded)', 'all-figures-wrapper')
        ]


@dataclasses.dataclass(kw_only=True)
class FigureComponent(Component):
    def _get_ids(self, cell: Union[None, Dict], id_list: List[int], notifs: List[Notification]) -> List[int]:
        """
        get a list of selection IDs for runners on which to plot charts
        if `do_all` is True, then simply return complete `id_list` - if not, take row ID from cell as single selection ID
        for list and validate
        """

        # determine if 'all feature plots' clicked as opposed to single plot
        do_all = triggered_id() == 'button-all-figures'

        # do all selection IDs if requested
        if do_all:
            return id_list

        # get selection ID of runner from active runner cell, or abort on fail
        if not cell:
            post_notification(notifs, 'warning', 'Figure', 'no cell selected')
            return []

        if 'row_id' not in cell:
            post_notification(notifs, 'warning', 'Figure', 'row ID not found in active cell info')
            return []

        sel_id = cell['row_id']
        if not sel_id:
            post_notification(notifs, 'warning', 'Figure', f'selection ID is blank')
            return []
        return [sel_id]

    def _get_chart_offset(self, offset: str, notifs: List[Notification]) -> Optional[timedelta]:
        """
        get chart offset based on HH:MM:SS form, return datetime on success, or None on fail
        """
        # if html trims off the seconds part of hh:mm:ss then add it back on
        if re.match(r'^\d{2}:\d{2}$', offset):
            offset = offset + ':00'

        if offset:
            if re.match(r'^\d{2}:\d{2}:\d{2}$', offset):
                try:
                    t = datetime.strptime(offset, "%H:%M:%S")
                    return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
                except ValueError:
                    post_notification(notifs, 'warning', 'Figure', f'cannot process chart offset "{offset}"')
        return None

    def callbacks(self, app, shn: Session):
        notification_clear(app, 'nav-notifications-figure', 'nav-figure')

        @dict_callback(
            app=app,
            inputs_config={
                'buttons': [
                    Input('button-figure', 'n_clicks'),
                    Input('button-all-figures', 'n_clicks'),
                    Input('btn-close-figure', 'n_clicks')
                ],
                'active': Input('figure-tabs', 'active_tab')
            },
            outputs_config={
                'table': Output('table-timings', 'data'),
                'loading': Output(self.loading_id, 'children'),
                'notifications': Output(self.notification_id, 'data'),
                'count': Output('figure-count', 'data'),
                'tabs': Output('figure-tabs', 'children'),
                'data': Output('figure-holder', 'data'),
                'figure': Output('figure-div', 'children'),
                'active': Output('figure-tabs', 'active_tab'),
                'delete-disabled': Output('btn-close-figure', 'disabled'),
                'figure-notifications': Output('nav-notifications-figure', 'children'),
                'timings-notifications': Output('nav-notifications-timings', 'children'),
            },
            states_config={
                'selected-market': State('selected-market', 'data'),
                'cell': State('table-runners', 'active_cell'),
                'offset': State('input-chart-offset', 'value'),
                'plot-config': State('input-plot-config', 'value'),
                'count': State('figure-count', 'data'),
                'tabs': State('figure-tabs', 'children'),
                'data': State('figure-holder', 'data'),
                'figure-notifications': State('nav-notifications-figure', 'children'),
            }
        )
        def figure_callback(outputs: TDict, inputs: TDict, states: TDict):
            """
            create a plotly figure based on selected runner when "figure" button is pressed
            """
            notifs = outputs['notifications'] = []
            outputs['table'] = []
            outputs['loading'] = ''

            tabs = states['tabs'] or []
            outputs['tabs'] = tabs
            outputs['count'] = states['count']
            figure_stores = states['data'] or {}
            outputs['data'] = figure_stores

            active_tab = inputs['active']
            outputs['figure'] = figure_stores.get(active_tab, None)
            outputs['active'] = active_tab

            outputs['delete-disabled'] = not active_tab

            outputs['figure-notifications'] = states['figure-notifications']

            if triggered_id() == 'btn-close-figure':
                tabs = [t for t in tabs if t['props']['tab_id'] != active_tab]
                outputs['tabs'] = tabs
                if active_tab in figure_stores:
                    del figure_stores[active_tab]
                    if figure_stores:
                        k = list(figure_stores.keys())[-1]
                        outputs['active'] = k
                        outputs['figure'] = figure_stores[k]
                    else:
                        outputs['active'] = None
                        outputs['figure'] = None
                        outputs['delete-disabled'] = True
                    return

            if triggered_id() != 'button-figure' and triggered_id() != 'button-all-figures':
                return

            if not states['selected-market']:
                return

            @handle_errors(notifs, 'Figure')
            def process():

                n_figures = states['count']  # get number of figures
                shn.deserialise_loaded_market(states['selected-market'])  # deserialise market info

                # get datetime/None chart offset from time input
                offset_dt = self._get_chart_offset(states['offset'], notifs)
                secs = offset_dt.total_seconds() if offset_dt else 0

                # get selected IDs and plot
                sel_ids = self._get_ids(states['cell'], list(states['selected-market'].keys()), notifs)
                reg = timing.TimingRegistrar()

                def update_reg(feature: RFBase, registrar: timing.TimingRegistrar):
                    for sub_feature in feature.sub_features.values():
                        registrar = update_reg(sub_feature, registrar)
                    return feature.timing_reg + registrar

                # shn.ftr_update()  # update feature & plot configs
                for selection_id in sel_ids:
                    features, fig = shn.fig_plot(
                        market_info=states['selected-market'],
                        selection_id=selection_id,
                        secs=secs,
                        ftr_key=states['plot-config'],
                        plt_key=states['plot-config']
                    )
                    for f in features.values():
                        reg = update_reg(f, reg)
                    n_figures += 1
                    tab_name = f'Figure {n_figures}'
                    tabs.append(dbc.Tab(label=tab_name, tab_id=tab_name))
                    graph = dcc.Graph(figure=fig, className='flex-grow-1')
                    figure_stores[tab_name] = graph
                    post_notification(notifs, 'success', 'Figure', f'produced {tab_name}')
                    outputs['figure'] = graph
                    outputs['active'] = tab_name
                    outputs['delete-disabled'] = False
                    try:
                        nav_count = int(states['figure-notifications'])
                    except (TypeError, ValueError):
                        nav_count = 0
                    nav_count += 1
                    outputs['figure-notifications'] = str(nav_count)
                    outputs['timings-notifications'] = '1'

                summary = reg.get_timings_summary()
                if not summary:
                    post_notification(notifs, 'warning', 'Figure', 'no timings on which to produce table')
                else:
                    for s in summary:
                        s['level'] = s['function'].count('.')
                    outputs['table'] = shn.format_timings(summary)
                    post_notification(notifs, 'info', 'Figure', f'{len(summary)} timings logged for figure generation')
                outputs['count'] = n_figures

            process()

    def loading_ids(self) -> List[str]:
        return [self.loading_id]

    def display_spec(self):
        return intf.container(self.container_id, [
            intf.row([
                intf.header('Figures'),
                intf.button('btn-close-figure', btn_text='Delete figure', btn_icon='fas fa-trash', color='warning')
            ]),
            intf.tabs('figure-tabs'),
            intf.div('figure-div', css_classes='d-flex flex-column flex-grow-1')
        ])

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(
            self.pathname, 'fas fa-chart-bar', 'Figures',
            nav_id='nav-figure',
            notifications_id='nav-notifications-figure'
        )

    def additional_stores(self) -> List[dcc.Store]:
        return [intf.store('figure-count', 0), intf.store('figure-holder')]

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('View plotted figures', 'nav-figure')
        ]


@dataclasses.dataclass(kw_only=True)
class StrategyComponent(Component, TableComponent):
    enable_delete: bool

    def modals(self) -> List[dbc.Modal]:
        return [intf.modal('strategy-delete-modal', header_spec='Delete strategy?', footer_spec=[
            intf.button('strategy-delete-yes', btn_text='Yes', color='danger'),
            intf.button('strategy-delete-no', btn_text='No', color='success')
        ])]

    def display_spec(self) -> Optional[html.Div]:
        full_tbl_cols = dict(self.table_columns)
        n_rows = int(self.n_table_rows)
        strategy_delete_buttons = []
        if self.enable_delete:
            strategy_delete_buttons.append(
                intf.button('btn-strategy-delete', btn_text='Delete strategy', btn_icon='fas fa-trash', color='danger')
            )
        return intf.container(self.container_id, [
            intf.row([
                intf.header('Strategies'),
                intf.wrapper(
                    'strategy-filter-wrapper',
                    intf.button('btn-strategy-filter', btn_icon='fas fa-filter')
                ),
                intf.wrapper(
                    'strategy-download-wrapper',
                    intf.button('btn-strategy-download', btn_icon='fas fa-download')
                )
            ]),
            intf.row(
                [intf.button('btn-strategy-refresh', btn_text='Reload', btn_icon='fas fa-sync-alt')] +
                strategy_delete_buttons
            ),
            intf.table('table-strategies', full_tbl_cols, n_rows)
        ])

    def sidebar(self) -> Optional[html.Div]:
        return intf.sidebar(
            self.sidebar_id,
            sidebar_title='Strategy Filters',
            close_id='btn-strategy-close',
            content=[]
        )

    def callbacks(self, app, shn: Session):
        right_panel_callback(app, "container-filters-strategy", "btn-strategy-filter", "btn-strategy-close")

        if self.enable_delete:
            @app.callback(
                Output("strategy-delete-modal", "is_open"),
                [
                    Input("btn-strategy-delete", "n_clicks"),
                    Input("strategy-delete-yes", "n_clicks"),
                    Input("strategy-delete-no", "n_clicks")
                ], [
                    State("strategy-delete-modal", "is_open")
                ],
            )
            def toggle_modal(n1, n2, n3, is_open):
                if n1 or n2 or n3:
                    return not is_open
                return is_open

        @app.callback(
            output=[
                Output('table-strategies', 'data'),
                Output('table-strategies', "selected_cells"),
                Output('table-strategies', 'active_cell'),
                Output('table-strategies', 'page_current'),
                Output(self.notification_id, 'data')
            ],
            inputs=[
                Input('btn-strategy-refresh', 'n_clicks'),
                Input('strategy-delete-yes', 'n_clicks'),
            ],
            state=[
                State('table-strategies', 'active_cell')
            ]
        )
        def strat_intermediary(
                n_refresh,
                n_delete,
                active_cell,
        ):
            notifs = []
            btn_id = triggered_id()
            strategy_id = active_cell['row_id'] if active_cell and 'row_id' in active_cell else None

            # delete strategy if requested
            if btn_id == 'strategy-delete-yes':
                if not strategy_id:
                    post_notification(notifs, 'warning', 'Strategy', 'Must select a strategy to delete')
                else:
                    n0, n1, n2 = shn.betting_db.strategy_delete(strategy_id)
                    msg = f'removed {n0} strategy meta, {n1} markets, {n2} runners'
                    post_notification(notifs, 'info', 'Strategy', msg)

            post_notification(notifs, 'info', 'Strategy', 'Strategies reloaded')
            tbl_rows = shn.strats_tbl_rows()
            for r in tbl_rows:
                r['id'] = r['strategy_id']  # assign 'id' so market ID set in row ID read in callbacks
            return [
                tbl_rows,  # table rows data
                [],  # clear selected cell(s)
                None,  # clear selected cell
                0,  # reset current page back to first page
                notifs
            ]

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(self.pathname, 'fas fas fa-chess-king', 'Strategies', nav_id='nav-strategies')

    def additional_stores(self) -> List[dcc.Store]:
        return [intf.store('selected-strategy')]

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('Navigate historic strategies', 'nav-strategies'),
            intf.tooltip('Filter strategies (to-do)', 'strategy-filter-wrapper'),
            intf.tooltip('Download selected strategy to markets', 'strategy-download-wrapper')
        ]


@dataclasses.dataclass(kw_only=True)
class OrdersComponent(Component, TableComponent):
    runner_button_id: str

    def display_spec(self) -> Optional[Dict]:
        return intf.container(self.container_id, [
            intf.header('Order Profits'),
            intf.table('table-orders', columns=self.table_columns, n_rows=self.n_table_rows, no_fixed_widths=True)
        ])

    def callbacks(self, app, shn: Session) -> None:
        notification_clear(app, 'nav-notifications-orders', 'nav-orders')

        @dict_callback(
            app=app,
            outputs_config={
                'table': Output('table-orders', 'data'),
                'page': Output('table-orders', 'page_current'),
                'notifications': Output(self.notification_id, 'data'),
                'orders-notifications': Output('nav-notifications-orders', 'children')
            },
            inputs_config={
                'buttons': [
                    Input('button-orders', 'n_clicks'),
                    Input(self.runner_button_id, 'n_clicks'),
                ]
            },
            states_config={
                'cell': State('table-runners', 'active_cell'),
                'loaded-market': State('selected-market', 'data'),
                'strategy-id': State('selected-strategy', 'data'),
            }
        )
        def orders_callback(outputs: TDict, inputs: TDict, states: TDict):

            outputs['table'] = []
            # reset selected page on new table
            # n.b. if last page selected was page 2 and new table loaded is only 1 page then table breaks
            outputs['page'] = 0

            notifs = outputs['notifications'] = []
            orders_pressed = triggered_id() == 'button-orders'

            # if runners button pressed (new active market), clear table
            if not orders_pressed:
                return

            @handle_errors(notifs, 'Orders')
            def process():
                # if no active market selected then abort
                selected_market = states['loaded-market']
                if not selected_market:
                    post_notification(notifs, 'warning', 'Orders', 'no market information to get orders')
                    return

                # get selection ID of runner from active runner cell, on fail clear table
                if not states['cell']:
                    post_notification(notifs, 'warning', 'Orders', 'no cell selected to get runner orders')
                    return

                if 'row_id' not in states['cell']:
                    post_notification(notifs, 'warning', 'Orders', f'row ID not found in active cell info')
                    return

                selection_id = states['cell']['row_id']
                shn.deserialise_loaded_market(selected_market)
                if selection_id not in selected_market['runners']:
                    post_notification(notifs, 'warning', 'Orders',
                                      f'row ID "{selection_id}" not found in starting odds')
                    return

                strategy_id = states['strategy-id']
                if not strategy_id:
                    post_notification(notifs, 'warning', 'Orders', 'no strategy selected')
                    return

                df = shn.read_orders(
                    market_id=selected_market['market_id'],
                    strategy_id=strategy_id,
                    selection_id=selection_id,
                    start_time=selected_market['info']['market_time']
                )
                if not df.shape[0]:
                    post_notification(notifs, 'warning', 'Orders', f'no orders found for runner "{selection_id}"')
                    return

                post_notification(notifs, 'info', 'Orders', f'Got {df.shape[0]} orders for runner "{selection_id}"')
                outputs['table'] = df.to_dict('records')
                outputs['orders-notifications'] = '1'

            process()

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(
            self.pathname, 'fas fa-file-invoice-dollar', 'Orders',
            nav_id='nav-orders',
            notifications_id='nav-notifications-orders'
        )

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('Runner profits from strategy', 'nav-orders'),
        ]


@dataclasses.dataclass(kw_only=True)
class LibraryComponent(Component):
    def header_right(self) -> Optional[Any]:
        return intf.button('button-libs', btn_icon='fas fa-book-open', color='info')

    def callbacks(self, app, shn: Session) -> None:
        @app.callback(
            output=[
                Output(self.loading_id, 'children'),
                Output(self.notification_id, 'data')
            ],
            inputs=[
                Input('button-libs', 'n_clicks')
            ]
        )
        def callback_libs(n1):
            """
            when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
            """
            notifs = []
            if triggered_id() == 'button-libs':
                n = shn.reload_modules()
                post_notification(notifs, 'info', 'Libraries', f'{n} modules reloaded')

            return [
                '',
                notifs
            ]

    def loading_ids(self) -> List[str]:
        return [self.loading_id]


@dataclasses.dataclass(kw_only=True)
class LoggerComponent(Component):
    stores: List[str]  # list of store IDs holding notification updates

    # mapping of log levels to bootstrap background colors
    level_colours: Dict[NotificationType, str] = dataclasses.field(default_factory= lambda: {
        'primary': 'bg-white',
        'secondary': 'bg-light',
        'success': 'bg-success',
        'warning': 'bg-warning',
        'danger': 'bg-danger',
        'info': 'bg-light'
    })

    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(self.pathname, 'fas fa-envelope-open-text', 'Logger', nav_id='nav-logger')

    def display_spec(self) -> Optional[html.Div]:
        return intf.container(self.container_id, [
            intf.row([
                intf.header('Python Log')
            ]),
            intf.div('logger-box', css_classes='d-flex flex-column-reverse overflow-auto bg-light')
        ])

    def callbacks(self, app, shn: Session):
        @app.callback(
            output=[
                Output('logger-box', 'children'),
                Output('toast-holder', 'children')
            ],
            inputs=[
               Input(s, 'data') for s in self.stores
            ] + [
               Input("url", "pathname")
            ],
            state=[
                State('logger-box', 'children'),
                State('toast-holder', 'children'),
            ]
        )
        def log_update(*args):
            toasts = args[-1] or []  # get existing toasts from toast holder
            logs = args[-2] or []  # get existing logs from log box

            # loop triggered components
            for e in all_triggered_ids():

                # check if component matches notification stores
                if e in self.stores:

                    # get list of new notification data from matching store
                    idx = self.stores.index(e)
                    new_notifications: List[Notification] = args[idx] or []
                    # add new toasts for new notifications
                    toasts += [
                        html.Div(dbc.Toast(
                            [html.P(p['msg_content'], className="mb-0")],
                            header=p['msg_header'],
                            icon=p['msg_type'],
                            duration=5000,
                            is_open=True,
                            dismissable=True,
                        ))
                        for p in new_notifications
                    ]
                    # add logs for new notifications
                    logs = [
                        html.P(
                            f'{p["timestamp"]}: {p["msg_header"]}: {p["msg_content"]}',
                            className='m-0 ' + self.level_colours.get(p['msg_type'], '')
                        )
                        for p in new_notifications
                    ] + logs

            return [
                logs,
                toasts
            ]

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('Notification log', 'nav-logger')
        ]


@dataclasses.dataclass(kw_only=True)
class TimingsComponent(Component, TableComponent):
    def nav_item(self) -> Optional[dbc.NavItem]:
        return intf.nav(
            self.pathname, 'fas fa-clock', 'Timings',
            nav_id='nav-timings',
            notifications_id='nav-notifications-timings'
        )

    def display_spec(self) -> Optional[html.Div]:
        tbl_cols = self.table_columns
        n_rows = self.n_table_rows
        return intf.container(self.container_id, [
            intf.row([
                intf.header('Function Timings')
            ]),
            intf.table('table-timings', columns=tbl_cols, n_rows=n_rows)
        ])

    def callbacks(self, app, shn: Session) -> None:
        notification_clear(app, 'nav-notifications-timings', 'nav-timings')

    def tooltips(self) -> List[Dict]:
        return [
            intf.nav_tooltip('Figure plot timings', 'nav-timings')
        ]
