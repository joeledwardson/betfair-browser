import dash
import dash_bootstrap_components as dbc
from mybrowser.session.session import Session

# TODO - move callbacks to function where app and dash_data are passed as args
FA = "https://use.fontawesome.com/releases/v5.15.1/css/all.css"
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, FA])
dash_data = Session()
