from typing import List
import pandas as pd
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
from mytrading.visual import bf_visualisation as bfv
from mytrading.feature import window as bfw
from mytrading.feature import feature as bff


def generate_feature_plot(
        hist_records: List[List[MarketBook]],
        selection_id: int,
        display_seconds: int,
        title: str,
        orders_df: pd.DataFrame
):
    if not hist_records:
        return

    # create runner feature instances (use defaults)
    windows = bfw.Windows()
    features = bff.generate_features(
        selection_id=selection_id,
        book=hist_records[0][0],
        windows=windows,
        features_config=bff.get_default_features_config()
    )

    # create feature plotting configurations (use defaults)
    feature_plot_configs = bfv.get_plot_configs(features)

    # create runner feature figure and append to html output path
    fig = bfv.fig_historical(
        records=hist_records,
        features=features,
        windows=windows,
        feature_plot_configs=feature_plot_configs,
        selection_id=selection_id,
        title=title,
        display_s=display_seconds,
        orders_df=orders_df
    )

    return fig
