from plotly import graph_objects as go


def get_default_plot_config() -> dict:
    """
    get default plotly chart configurations dict for plotting features
    configuration includes keys:
    - 'chart': plotly chart function
    - 'chart_args': dictionary of plotly chart arguments
    - 'trace_args': dictionary of arguments used when plotly trace added to figure
    - 'y_axis': name of y-axis, used as a set to distinguish different y-axes on subplots (just used to
    differentiate between subplots, name doesn't actually appear on axis)
    """
    return {
        'chart': go.Scatter,
        'chart_args': {
            'mode': 'lines'
        },
        'trace_args': {},
        'y_axis': 'odds',
    }