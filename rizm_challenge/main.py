

import pathlib

from rizm_challenge.util import io
from rizm_challenge.util import optimize


def execute_optimization():
    data_path = pathlib.Path(__file__).parent.parent / "data"

    df, pars = io.get_input(data_path)

    optimize.solve_problem(df, pars)


    

if __name__ == "__main__":
    execute_optimization()


