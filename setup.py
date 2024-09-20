#!/usr/bin/env python

from setuptools import setup, find_packages

requirements = ["pandas", "casadi", "numpy", "matplotlib"]

setup(
    author="Arne Gross",
    author_email="arne.gross@hotmail.com",
    python_requires=">=3.6",
    description="Code for Rizm take home challenge",
    install_requires=requirements,
    name="rizm_challenge",
    packages=find_packages(include=["rizm_challenge", "rizm_challenge.*"]),
    package_data={"grecco_sim": ["data/heat_pump_database/heat_pump_database_short_version.csv"],},
    url="https://github.com/ArneJGross/rizm_challenge",
    version="0.1.0",
)