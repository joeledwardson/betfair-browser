import pandas as pd
import plotly.graph_objs as go


def plotly_table_kwargs(df: pd.DataFrame, index_name=None) -> dict:
    """
    create 'header' and 'cells' kwargs for constructing a plotly graph_objects.table
    if `index_name` is passed then is used for column header and dataframe index values for rest of table,
    otherwise index ignored
    """
    headers = list(df.columns)
    data = [df[c].to_list() for c in df.columns]

    if index_name:
        headers = [index_name] + headers
        data = [df.index.to_list()] + data

    return dict(
        header=dict(values=headers),
        cells=dict(values=data)
    )


def create_plotly_table(df: pd.DataFrame, title: str, index_name=None, table_kwargs=None) -> go.Figure:
    """create plotly.Figure object for table with dataframe data and title"""
    return go.Figure(
        data=go.Table(**plotly_table_kwargs(df, index_name=index_name), **(table_kwargs or {})),
        layout=dict(title=title),
    )

