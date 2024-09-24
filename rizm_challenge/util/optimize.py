import dataclasses

import pandas as pd
import numpy as np
import casadi as cas

from matplotlib import dates as mdates
from matplotlib import pyplot as plt

SOLVER_NAME = "ipopt"


@dataclasses.dataclass
class OptVariables:
    """Container to store optimization variables."""

    p_el_gt: cas.MX  # electric (output) power of gas turbines
    p_el_boiler_el: cas.MX  # electric power of electric boiler
    p_th_boiler_gas: cas.MX  # thermal (output) power of gas boiler
    p_el_pv: cas.MX  # electric (output) power of PV generator


@dataclasses.dataclass
class OptData:
    """Container to store parameters of optimization problem."""

    load_el: cas.MX  # electric load to e satisfied
    load_th: cas.MX  # thermal load to be satisfied
    pv_avail: cas.MX  # availability of PV


def solve_problem(time_series: pd.DataFrame, system_parameters: dict[str, pd.Series]):
    """Setup problem and solve.

    Return solution time series to analyse / plot somewhere else
    """
    horizon = 24 * 180

    ocp, opt_vars, opt_pars = _formulate_ocp(system_parameters, horizon=horizon)
    dispatch_schedules = _solve(ocp, opt_vars, opt_pars, time_series.iloc[:horizon])

    objective = _objective_expression(dispatch_schedules, system_parameters["eff"])



    _plot_and_show(dispatch_schedules, time_series[:horizon])

    print(objective)
    print(dispatch_schedules)





def _objective_expression(x: OptVariables, effs: pd.Series, price_gas: float | np.ndarray = 35, dt_h: float=1):

    if isinstance(price_gas, np.ndarray):
        assert len(x.p_el_gt) == len(price_gas), "If time variant gas price is given, it must have the same length as the variables."

    return cas.sum1(x.p_el_gt * dt_h * price_gas) + cas.sum1(x.p_th_boiler_gas * dt_h / effs["gasboiler"] * price_gas)


def _formulate_ocp(system_parameters: dict[str, pd.Series], horizon: int = 24):
    """Return formulated ocp."""

    caps = system_parameters["cap"]
    effs = system_parameters["eff"]

    ocp = cas.Opti()

    # Define external data
    ext_data = OptData(
        load_el=ocp.parameter(horizon),
        load_th=ocp.parameter(horizon),
        pv_avail=ocp.parameter(horizon),
    )

    # Define optimization variables
    x = OptVariables(
        p_el_gt=ocp.variable(horizon),
        p_el_boiler_el=ocp.variable(horizon),
        p_th_boiler_gas=ocp.variable(horizon),
        p_el_pv=ocp.variable(horizon),
    )

    # Define bounds for optimization variables
    ocp.subject_to(x.p_el_gt >= 0.0)
    ocp.subject_to(x.p_el_gt <= caps["gasturbine"])

    ocp.subject_to(x.p_el_boiler_el >= 0.0)
    ocp.subject_to(x.p_el_boiler_el <= caps["electricboiler"])

    ocp.subject_to(x.p_th_boiler_gas >= 0.0)
    ocp.subject_to(x.p_th_boiler_gas <= caps["gasboiler"])

    ocp.subject_to(x.p_el_pv >= 0)
    ocp.subject_to(x.p_el_pv <= ext_data.pv_avail * caps["photovoltaic"])


    # Define both energy conservation constraints
    # ... electrical
    ocp.subject_to(x.p_el_gt + x.p_el_pv == ext_data.load_el + x.p_el_boiler_el)
    # ... and thermal
    ocp.subject_to(x.p_el_boiler_el * effs["electricboiler"] + x.p_th_boiler_gas == ext_data.load_th)

    ocp.minimize(_objective_expression(x, effs))

    return ocp, x, ext_data


def _solve(ocp: cas.Opti, opt_vars: OptVariables, opt_pars: OptData, ts_in) -> OptVariables:

    ocp.set_value(opt_pars.load_el, ts_in["load_el"])
    ocp.set_value(opt_pars.load_th, ts_in["load_th"])
    ocp.set_value(opt_pars.pv_avail, ts_in["pv_avail"])

    ocp.solver("ipopt")
    solution = ocp.solve()

    result = OptVariables(
        p_el_gt=solution.value(opt_vars.p_el_gt),
        p_el_boiler_el=solution.value(opt_vars.p_el_boiler_el),
        p_th_boiler_gas=solution.value(opt_vars.p_th_boiler_gas),
        p_el_pv=solution.value(opt_vars.p_el_pv)
    )

    return result

def _plot_and_show(x: OptVariables, ext_data: pd.DataFrame):
    index = ext_data.index

    fig, ax = _styled_plot(date_axis=True, ylabel="Electric Power / MW", figsize="landscape")

    ax.plot(index, x.p_el_gt, label="P_el gas turbine")
    ax.plot(index, x.p_el_pv, label="P_pv generator")
    ax.plot(index, -ext_data["load_el"], label="Ext Load")
    ax.plot(index, -x.p_el_boiler_el, label="P_el boiler elec.")

    ax.legend()

    plt.show()




def _styled_plot(**kwargs):
    """Copied this from my university project."""
    plot_defaults = dict(
    major_formatter="%H:%M",
    figsize=(10, 10),
    date_axis=False,
    title="",
    xlabel="",
    ylabel="",
    ylim=None,
    xlim=None,
)
    figsize_defaults = dict(landscape=(8, 4), policies=(8, 5), portrait=(4, 4), slim=(3, 4))

    specs = {}
    specs.update(plot_defaults)
    specs.update(kwargs)

    if specs["figsize"] is not None:
        if specs["figsize"] in figsize_defaults:
            fig, ax = plt.subplots(figsize=figsize_defaults[specs["figsize"]])
        else:
            fig, ax = plt.subplots(figsize=specs["figsize"])
    else:
        fig, ax = plt.subplots()

    if specs["date_axis"]:
        ax.xaxis.set_major_formatter(
            mdates.DateFormatter(specs["major_formatter"])
        )
        ax.set_xlabel("Time")
    else:
        ax.set_xlabel(specs["xlabel"])

    ax.set_ylabel(specs["ylabel"])

    if specs["xlim"] is not None:
        ax.set_xlim(specs["xlim"])

    if specs["ylim"] is not None:
        ax.set_ylim(specs["ylim"])

    ax.set_title(specs["title"])

    ax.set_axisbelow(True)

    return fig, ax