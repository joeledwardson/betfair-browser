import dash
import dash_bootstrap_components as dbc
from .data import DashData


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
dash_data = DashData()
