from __future__ import annotations
import dash
import logging
import argparse
from mytrading.browser.data import DashData
from mytrading.browser.callbacks import market_callback, file_table_callback, figure_callback
from mytrading.browser.layout import get_layout


parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter  # show defaults in help
)
parser.add_argument(
    'input_dir',
    type=str,
    help='input directory of markets')

args = parser.parse_args()
input_dir = args.input_dir
gdd = DashData(input_dir)

app = dash.Dash(__name__)
logging.basicConfig(level=logging.INFO)
app.layout = get_layout(input_dir, gdd)

file_table_callback(app, gdd, input_dir)
market_callback(app, gdd, input_dir)
figure_callback(app, gdd, input_dir)


if __name__ == '__main__':
    app.run_server(debug=True)
