import datetime
import pytz
import pathlib

import pandas as pd


def read_ts(file_name: pathlib.Path):
    # TODO checkout read with multi-columns names to get 
    # (and autmatically check) unit.
    # But everything is MW -> fine for now.
    df = pd.read_csv(file_name, index_col=0, skiprows=[1], parse_dates=True)

    return df


def get_input(data_path: pathlib.Path):

    df = pd.concat(
        [
            read_ts(data_path / ts_file)
            for ts_file in ["electricity_demand.csv", "heat_demand.csv", "photovoltaic_availability.csv"]
        ], axis=1
    )

    pars = pd.read_csv(data_path / "parameter.csv")

    return df, pars
