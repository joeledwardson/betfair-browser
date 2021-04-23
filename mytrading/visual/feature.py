import logging

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


# TODO - why in its own file??


#
# def add_feature_parent(
#         feature_name: str,
#         all_features_data: Dict[str, List[Dict]],
#         fig: go.Figure,
#         conf: dict,
#         default_plot_config: Dict,
#         y_axes_names: List[str],
#         chart_start: datetime = None,
#         chart_end: datetime = None,
# ):
#     """
#     add a feature trace to a chart, including all its children features
#     """
#
#     # plot feature
#     add_feature_trace(
#         fig=fig,
#         feature_name=feature_name,
#         all_features_data=all_features_data,
#         def_conf=default_plot_config,
#         y_axes_names=y_axes_names,
#         ftr_conf=conf,
#         chart_start=chart_start,
#         chart_end=chart_end,
#     )
#
#     # get sub features config if exist
#     sub_configs = conf.get('sub_features', {})
#
#     # loop sub features
#     for sub_name, sub_feature in feature.sub_features.items():
#
#         # get sub-feature specific configuration
#         sub_conf = sub_configs.get(sub_name, {})
#
#         # create display name by using using a dot (.) between parent and sub feature names
#         sub_display_name = '.'.join([display_name, sub_name])
#
#         add_feature_parent(
#             display_name=sub_display_name,
#             feature=sub_feature,
#             features=features,
#             fig=fig,
#             conf=sub_conf,
#             default_plot_config=default_plot_config,
#             y_axes_names=y_axes_names,
#             chart_start=chart_start,
#             chart_end=chart_end
#         )


