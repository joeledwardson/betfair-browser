import pandas as pd


def plotly_table_kwargs(df: pd.DataFrame) -> dict:
    """create 'header' and 'cells' kwargs for constructing a plotly graph_objects.table"""
    return dict(
        header=dict(values=list(df.columns)),
        cells=dict(values=[df[c].to_list() for c in df.columns])
    )