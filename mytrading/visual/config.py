from typing import Dict


def get_plot_default_config() -> Dict:
    """
    get default plotly chart configurations dict for plotting features
    configuration includes keys:
    - 'chart': plotly chart function name within plotly.graph_objects
    - 'chart_args': dictionary of plotly chart arguments
    - 'trace_args': dictionary of arguments used when plotly trace added to figure
    - 'y_axis': name of y-axis, used as a set to distinguish different y-axes on subplots (just used to
    differentiate between subplots, name doesn't actually appear on axis)
    """
    return {
        'chart': 'Scatter',
        'chart_args': {
            'mode': 'lines'
        },
        'trace_args': {},
        'y_axis': 'odds',
    }
