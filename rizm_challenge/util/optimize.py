import dataclasses

import pandas as pd
import casadi as cas

SOLVER_NAME = "ipopt"


@dataclasses.dataclass
class OptVariables:
    p_el_gt: cas.MX  # electric (output) power of gas turbines
    p_el_boiler_el: cas.MX  # electric power of electric boiler
    p_th_boiler_gas: cas.MX  # thermal (output) power of gas boiler


@dataclasses.dataclass
class OptData:
    load_el: cas.MX  # electric load to e satisfied
    load_th: cas.MX  # thermal load to be satisfied
    pv_avail: cas.MX  # availability of PV


def solve_problem(time_series: pd.DataFrame, system_parameters: pd.DataFrame):
    """Setup problem and solve.

    Return solution time series to analyse / plot somewhere else
    """
    horizon = 24

    ocp, vars, pars = _formulate_ocp(system_parameters, horizon=horizon)

    dispatch_schedules = _solve(ocp, vars, pars, time_series.iloc[:horizon])

    objective = _objective_expression(dispatch_schedules)

    print(objective)
    print(dispatch_schedules)


def _objective_expression(x: OptVariables, effs: pd.DataFrame):
    # const price for gas
    PRICE_GAS = 0.36

    return cas.sum1(x.p_el_gt * PRICE_GAS) + cas.sum1(x.p_th_boiler_gas / effs["gasboiler"] * PRICE_GAS)

def _formulate_ocp(parameters: pd.DataFrame, horizon: int = 24):
    """Return formulated ocp."""

    ocp = cas.Opti()

    # Define optimization variables
    x = OptVariables(
        p_el_gt=ocp.variable(horizon),
        p_el_boiler_el=ocp.variable(horizon),
        p_th_boiler_gas=ocp.variable(horizon),
    )

    # Define bounds for optimization variables
    ocp.subject_to(x.p_el_gt >= 0.0)
    ocp.subject_to(x.p_el_gt <= caps["gasturbine"])

    ocp.subject_to(x.p_el_boiler_el >= 0.0)
    ocp.subject_to(x.p_el_boiler_el <= caps["electricboiler"])

    ocp.subject_to(x.p_th_boiler_gas >= 0.0)
    ocp.subject_to(x.p_th_boiler_gas <= caps["gasboiler"])

    # Define external data
    ext_data = OptData(
        load_el=ocp.parameter(horizon),
        load_th=ocp.parameter(horizon),
        pv_avail=ocp.parameter(horizon),
    )

    # Define both energy conservation constraints

    ocp.subject_to(
        x.p_el_gt + ext_data.pv_avail * caps["photovoltaic"]
        == ext_data.load_el + x.p_el_boiler_el
    )

    ocp.subject_to(
        x.p_el_boiler_el * effs["electricboiler"] + x.p_th_boiler_gas
        == ext_data.load_th
    )

    ocp.minimize(_objective_expression(x)
    )

    return ocp, x, ext_data


def _solve(ocp, vars: OptVariables, pars: OptData, ts_in) -> OptVariables:

    ocp.set_value(pars.load_el, ts_in["load_el"])
    ocp.set_value(pars.load_th, ts_in["load_th"])
    ocp.set_value(pars.pv_avail, ts_in["pv_avail"])
    
    ocp.solver("ipopt")
    solution = ocp.solve()

    result = OptVariables(
        p_el_gt=solution.value(vars.p_el_gt),
        p_el_boiler_el=solution.value(vars.p_el_boiler_el),
        p_th_boiler_gas=solution.value(vars.p_th_boiler_gas),
    )

    return result
