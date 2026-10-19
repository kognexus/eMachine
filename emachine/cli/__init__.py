"""
The command line of emachine:

    emachine <command> [options]          emachine <command> --help

Commands
    optimize     multi-objective optimization of a specification (optimizer from optimizer.algorithm)
    map          torque, speed and efficiency map of one design
    export       field export of one design for ParaView (with the five standard views)
    validate     validation against a published machine (case file)
    compare      grid of the best designs of several runs
    onshape      parameter sheet of a TFM design for the Onshape features
    mesh         sector mesh of a TFM parameter file (Gmsh)
    check-mesh   checks of a sector mesh
    solve        field solution of a parameter file at several rotor positions (Elmer)
    ui32         regenerates the combined Onshape studio "TFM UI32 machine"
    featurescript  regenerates the Onshape studio of the "eMachine" feature (every machine)
    list         machines, geometry builders, field solvers and optimizers that are registered
    study        multi-topology study on one drive and envelope (T58 to T66): optimization, picks, verification

Start with docs/usage.md: inputs, options and outputs of an optimization.
"""

import importlib
import sys

from emachine.pipeline.picks import PickError
from emachine.spec.errors import SpecError

#: command -> (module, function)
COMMANDS = {
    "optimize": ("emachine.cli.optimize", "main"),
    "map": ("emachine.cli.map", "main"),
    "export": ("emachine.cli.export", "main"),
    "validate": ("emachine.analysis.validation", "main"),
    "compare": ("emachine.cli.compare", "main"),
    "onshape": ("emachine.cli.onshape", "main"),
    "mesh": ("emachine.machines.tfm.geometry.sector", "main"),
    "check-mesh": ("emachine.cli.check_mesh", "main"),
    "solve": ("emachine.cli.solve", "main"),
    "ui32": ("emachine.machines.tfm.cad.ui32_build", "main"),
    "featurescript": ("emachine.cad.build", "main"),
    "list": ("emachine.cli.listing", "main"),
    "study": ("emachine.cli.study", "main"),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    name, rest = argv[0], argv[1:]
    if name not in COMMANDS:
        print(f"Unknown command {name!r}.\n{__doc__}", file=sys.stderr)
        return 2
    module, function = COMMANDS[name]
    command = getattr(importlib.import_module(module), function)
    saved = sys.argv
    sys.argv = [f"emachine {name}"] + rest           # commands that read sys.argv see their own options
    try:
        result = command(rest) if _takes_argv(command) else command()
    except (SpecError, PickError) as error:          # an invalid input file: its message names the key
        print(f"emachine {name}: {error}", file=sys.stderr)
        return 2
    finally:
        sys.argv = saved
    return result or 0


def _takes_argv(function):
    import inspect
    try:
        return len(inspect.signature(function).parameters) > 0
    except (TypeError, ValueError):
        return False
