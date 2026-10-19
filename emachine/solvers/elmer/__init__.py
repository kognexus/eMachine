"""Elmer FEM: case files, runs and result reading; the 3D sector solver (sector3d.py)."""

import os
import shutil
import sys

from emachine.io.process import ROOT


def find_elmer_home():
    """
    The Elmer installation (the folder holding bin/ElmerSolver), first found of: $ELMER_HOME, the
    active Python environment (pixi or conda, where `pixi run install-elmer` puts it), ElmerSolver on
    the PATH, and .elmer/install in the project folder. Falls back to the environment, so that a
    missing Elmer is reported with that path.
    """
    if os.environ.get("ELMER_HOME"):
        return os.environ["ELMER_HOME"]
    on_path = shutil.which("ElmerSolver")
    candidates = [sys.prefix, os.environ.get("CONDA_PREFIX"),
                  os.path.dirname(os.path.dirname(on_path)) if on_path else None,
                  os.path.join(ROOT, ".elmer", "install")]
    for home in candidates:
        if home and os.path.isfile(os.path.join(home, "bin", "ElmerSolver")):
            return home
    return sys.prefix


ELMER_HOME = find_elmer_home()
ELMER_SOLVER = os.path.join(ELMER_HOME, "bin", "ElmerSolver")
ELMER_GRID = os.path.join(ELMER_HOME, "bin", "ElmerGrid")
