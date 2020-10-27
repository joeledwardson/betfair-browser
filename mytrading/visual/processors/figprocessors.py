from plotly import graph_objects as go
fig_processors = {}


def register_figure_processor(func):
    """
    register a plotly processor, add to dictionary of processors
    signature:

    def func(figure, **kwargs)
    """
    if func.__name__ in fig_processors:
        raise Exception(f'registering plotly figure processor "{func.__name__}", but already exists!')
    else:
        fig_processors[func.__name__] = func
        return func


def post_process_figure(fig, processors_config):
    """
    use plotly data processors to process data
    """
    for cfg in processors_config:
        func = fig_processors[cfg['name']]
        kwargs = cfg.get('kwargs', {})
        func(fig, **kwargs)


@register_figure_processor
def plotly_group(fig: go.Figure, name: str, group_name: str):
    """
    group a set of plotly traces with a unified name to a single legend
    """

    # filter to traces with name
    for i, trace in enumerate([t for t in fig.data if t['name']==name]):

        # show legend on first trace but ignore others
        if i == 0:
            trace['showlegend'] = True
        else:
            trace['showlegend'] = False

        # set all trace group names the same
        trace['legendgroup'] = group_name