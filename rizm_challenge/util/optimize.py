import pandas as pd
import casadi as cas


def solve_problem(time_series: pd.DataFrame):
    """Setup problem and solve.
    
    Return solution time series to analyse / plot somewhere else    
    """
