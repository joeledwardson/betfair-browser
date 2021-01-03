import dash
from dash.dependencies import Output, Input

from ..data import DashData
from ..tables.files import get_files_table
from ..text import html_lines
from myutils.mydash.context import triggered_id


def file_table_callback(app: dash.Dash, dd: DashData, input_dir: str):
    """
    update active cell indicator, active path indicator, and table for files display based on active cell and if
    return button is pressed
    """
    @app.callback(
        output=[
            Output('infobox-files', 'children'),
            Output('table-files-container', 'children')
        ],
        inputs=[
            Input('button-return', 'n_clicks'),
            Input('button-profit', 'n_clicks'),
            Input('table-files', 'active_cell'),
        ],
    )
    def update_files_table(return_n_clicks, profit_n_clicks, active_cell):

        profit_pressed = triggered_id() == 'button-profit'
        return_pressed = triggered_id() == 'button-return'

        # get active directory
        old_root = dd.file_tracker.root

        if return_pressed:

            # if return button pressed then navigate to parent directory
            dd.file_tracker.navigate_up()

        elif active_cell is not None:

            # if a cell is pressed, use its row index to navigate to directory (if is directory)
            if 'row' in active_cell:
                dd.file_tracker.navigate_to(active_cell['row'])

        # if directory has changed, then clear the active cell when creating new table
        if dd.file_tracker.root != old_root:
            active_cell = None

        info_box = html_lines([
            f'Files active cell: {active_cell}',
            f'Path: {dd.file_tracker.root}'
        ])

        return [
            info_box,
            get_files_table(
                ft=dd.file_tracker,
                base_dir=input_dir,
                do_profits=profit_pressed,
                active_cell=active_cell
            )
        ]