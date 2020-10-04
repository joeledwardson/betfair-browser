"""generic library for visualisation and plotting functions"""
import pandas as pd


def plotly_table_kwargs(df: pd.DataFrame) -> dict:
    """create 'header' and 'cells' kwargs for constructing a plotly table"""
    return dict(
        header=dict(values=list(df.columns)),
        cells=dict(values=[df[c].to_list() for c in df.columns])
    )