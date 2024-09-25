import dataclasses
import datetime
import pandas as pd
import numpy as np
import casadi as cas

from matplotlib import dates as mdates
from matplotlib import pyplot as plt


SOLVER_NAME = "qpoases"


@dataclasses.dataclass
class OptVariables:
    """Container to store optimization variables."""

    p_el_gt: cas.MX  # electric (output) power of gas turbines
    p_el_boiler_el: cas.MX  # electric power of electric boiler
    p_th_boiler_gas: cas.MX  # thermal (output) power of gas boiler
    p_el_pv: cas.MX  # electric (output) power of PV generator
    slack_th: cas.MX  # slack variable to assert feasibility


@dataclasses.dataclass
class OptData:
    """Container to store parameters of optimization problem."""

    load_el: cas.MX  # electric load to e satisfied
    load_th: cas.MX  # thermal load to be satisfied
    pv_avail: cas.MX  # availability of PV


def solve_problem(
    time_series: pd.DataFrame,
    system_parameters: dict[str, pd.Series],
    plot_on_fail=True,
):
    """Setup problem and solve.

    Return solution time series to analyse / plot somewhere else
    """

    horizon = 24
    window = (horizon - 1) * datetime.timedelta(hours=1)

    col_names_opt_vars = list(OptVariables.__dataclass_fields__.keys())
    schedules_ts = pd.DataFrame(
        index=time_series.index, columns=col_names_opt_vars + ["success"]
    )
    objective = 0

    ocp, opt_vars, opt_pars = _formulate_ocp(system_parameters, horizon)

    for start in time_series.index[::horizon]:
        current_ts = time_series.loc[start : start + window, :]
        _schedules, success = _solve(ocp, opt_vars, opt_pars, current_ts)

        objective += _objective_expression(
            _schedules, system_parameters["eff"], slack_penalty=0.0
        )

        for col_name in col_names_opt_vars:
            schedules_ts.loc[start : start + window, col_name] = getattr(
                _schedules, col_name
            )

        schedules_ts.loc[start : start + window, "success"] = success

        if not success and plot_on_fail:
            _plot_and_show(
                schedules_ts.loc[start : start + window],
                time_series.loc[start : start + window],
                system_parameters["eff"],
            )

    ind_slack = schedules_ts.index[schedules_ts["slack_th"] > 0.0]
    print(
        f"Heat load could not be satisfied in these time instances: {list(ind_slack)}."
        f" Overall {schedules_ts['slack_th'][ind_slack].sum():0.04f} MWh where not supplied."
    )

    print(f"Costs of operation of the system: {objective} Euro")


def _objective_expression(
    x: OptVariables,
    effs: pd.Series,
    price_gas: float | np.ndarray = 35,
    dt_h: float = 1,
    slack_penalty: float = 1000.0,
):

    if isinstance(price_gas, np.ndarray):
        assert len(x.p_el_gt) == len(
            price_gas
        ), "If time variant gas price is given, it must have the same length as the variables."

    return cas.sum1(x.p_el_gt / effs["gasturbine"] * dt_h * price_gas) + cas.sum1(
        x.p_th_boiler_gas / effs["gasboiler"] * dt_h * price_gas
        + cas.sum1(x.slack_th * slack_penalty)
    )


def _formulate_ocp(system_parameters: dict[str, pd.Series], horizon: int):
    """Return formulated ocp."""

    caps = system_parameters["cap"]
    effs = system_parameters["eff"]

    ocp = cas.Opti("conic")
    ocp.solver(SOLVER_NAME)

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
        slack_th=ocp.variable(horizon),
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

    ocp.subject_to(x.slack_th >= 0)
    ocp.subject_to(x.slack_th <= ext_data.load_th)

    # Define both energy conservation constraints
    # ... electrical
    ocp.subject_to(x.p_el_gt + x.p_el_pv == ext_data.load_el + x.p_el_boiler_el)
    # ... and thermal
    ocp.subject_to(
        x.p_el_boiler_el * effs["electricboiler"] + x.p_th_boiler_gas
        == ext_data.load_th - x.slack_th
    )

    ocp.minimize(_objective_expression(x, effs))

    return ocp, x, ext_data


def _solve(
    ocp: cas.Opti, opt_vars: OptVariables, opt_pars: OptData, ts_in
) -> tuple[OptVariables, bool]:

    ocp.set_value(opt_pars.load_el, ts_in["load_el"])
    ocp.set_value(opt_pars.load_th, ts_in["load_th"])
    ocp.set_value(opt_pars.pv_avail, ts_in["pv_avail"])

    try:
        solution = ocp.solve()
        result = OptVariables(
            p_el_gt=solution.value(opt_vars.p_el_gt),
            p_el_boiler_el=solution.value(opt_vars.p_el_boiler_el),
            p_th_boiler_gas=solution.value(opt_vars.p_th_boiler_gas),
            p_el_pv=solution.value(opt_vars.p_el_pv),
            slack_th=solution.value(opt_vars.slack_th),
        )

        return result, (result.slack_th == 0).all()
    except RuntimeError:
        # Infeasible problem
        ts_in.plot()
        plt.show()
        result = OptVariables(
            p_el_gt=ocp.debug.value(opt_vars.p_el_gt),
            p_el_boiler_el=ocp.debug.value(opt_vars.p_el_boiler_el),
            p_th_boiler_gas=ocp.debug.value(opt_vars.p_th_boiler_gas),
            p_el_pv=ocp.debug.value(opt_vars.p_el_pv),
            slack_th=ocp.debug.value(opt_vars.slack_th),
        )
        return result, False


def _plot_and_show(x: OptVariables, ext_data: pd.DataFrame, effs: pd.Series):
    index = ext_data.index

    fig, ax_elec = _styled_plot(
        date_axis=True, ylabel="Electric Power / MW", figsize="landscape"
    )

    ax_elec.plot(index, x.p_el_gt, label="P_el gas turbine")
    ax_elec.plot(index, x.p_el_pv, label="P_pv generator")
    ax_elec.plot(index, -ext_data["load_el"], label="Ext Load")
    ax_elec.plot(index, -x.p_el_boiler_el, label="P_el boiler elec.")

    # Check if those two overlap
    ax_elec.plot(index, x.p_el_gt + x.p_el_pv, label="Generation")
    ax_elec.plot(index, x.p_el_boiler_el + ext_data["load_el"], label="Consumption")

    ax_elec.legend()

    fig, ax_thermal = _styled_plot(
        date_axis=True, ylabel="Thermal Power / MW", figsize="landscape"
    )

    ax_thermal.plot(
        index,
        x["p_el_boiler_el"] * effs["electricboiler"],
        label="El. Boiler",
        drawstyle="steps-post",
    )
    ax_thermal.plot(
        index, x["p_th_boiler_gas"], label="Gas Boiler", drawstyle="steps-post"
    )
    ax_thermal.plot(
        index, -ext_data["load_th"], label="Thermal Load", drawstyle="steps-post"
    )
    ax_thermal.plot(
        index, x["slack_th"], label="unsatisfiable heat load", drawstyle="steps-post"
    )
    ax_thermal.legend()

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
    figsize_defaults = dict(
        landscape=(8, 4), policies=(8, 5), portrait=(4, 4), slim=(3, 4)
    )

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
        ax.xaxis.set_major_formatter(mdates.DateFormatter(specs["major_formatter"]))
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
