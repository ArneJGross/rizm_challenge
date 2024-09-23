import warnings
import pathlib

import pandas as pd


def _read_ts(file_name: pathlib.Path, col_name:str):
    # TODO checkout read with multi-columns names to get 
    # (and autmatically check) unit.
    # But everything is MW -> fine for now.
    df = pd.read_csv(file_name, index_col=0, skiprows=[1], parse_dates=True)
    df = df.rename(columns={"value": col_name})

    return df


def _repair_data(ts: pd.DataFrame):
    nan_indices = ts.index[ts.isna().any(axis=1)]

    if len(nan_indices) > 0:
        warnings.warn(f"Removing {len(nan_indices)} from input data because of inconsistent data")

    return ts[~ts.isna().any(axis=1)]


def get_input(data_path: pathlib.Path):

    ts = pd.concat(
        [
            _read_ts(data_path / ts_file, col_name)
            for ts_file, col_name in zip(
                ["electricity_demand.csv", "heat_demand.csv", "photovoltaic_availability.csv"],
                ["load_el", "load_th", "pv_avail"]
            )
        ], axis=1
    )

    ts = _repair_data(ts)

    pars = pd.read_csv(data_path / "parameter.csv").set_index("component")
    
    effs = parameters.loc[parameters["parameter_type"] == "efficiency", "value"]
    caps = parameters.loc[parameters["parameter_type"] == "capacity", "value"]

    caps.loc["photovoltaic"] /= 1000.0  # transform kW -> MW (in a hacky way for now)
    effs /= 100.0  # transform to fraction (in a hacky way)


    return ts, pars
