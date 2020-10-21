import pandas as pd


def datatable_data(df: pd.DataFrame, table_id: str) -> dict:
    """create data kwargs constructing a plotly graph_objects.table"""
    return {
        'id': table_id,
        'columns': [{
            'name': x,
            'id': x
        } for x in df.columns],
        'data': df.to_dict('records')
    }
