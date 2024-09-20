

import pathlib

from rizm_challenge.util import io


def execute_optimization():
    data_path = pathlib.Path(__file__).parent.parent / "data"

    df, pars = io.get_input(data_path)

    print(df)

    

if __name__ == "__main__":
    execute_optimization()


