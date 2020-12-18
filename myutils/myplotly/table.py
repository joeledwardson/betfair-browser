import pandas as pd
import plotly.graph_objs as go


def plotly_table_kwargs(df: pd.DataFrame) -> dict:
    """create 'header' and 'cells' kwargs for constructing a plotly graph_objects.table"""
    return dict(
        header=dict(values=list(df.columns)),
        cells=dict(values=[df[c].to_list() for c in df.columns])
    )


def plotly_table(df: pd.DataFrame, title: str) -> go.Figure:
    """create plotly.Figure object for table with dataframe data and title"""
    return go.Figure(
        data=go.Table(**plotly_table_kwargs(df)),
        layout=dict(title=title),
    )

