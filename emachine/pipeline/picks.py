"""
Locating one design for the post-processing commands (map, ParaView export).

A design is given either as a pick of an optimization run (`--run RUN --pick NAME`: the
specification is RUN/spec.json and the design RUN/designs/NAME.json) or as a specification file
and a parameter file (`--spec FILE --design FILE`).
"""

import copy
import json
import os

from emachine.spec import load_spec
from emachine.spec.names import standard_values

from . import design_space as design


class PickError(ValueError):
    pass


def add_arguments(ap):
    ap.add_argument("--run", help="optimization run folder")
    ap.add_argument("--pick", default="best_compromise",
                    help="pick of the run: best_compromise (default), highest_torque or lowest_loss")
    ap.add_argument("--spec", help="specification file (default: spec.json of the run)")
    ap.add_argument("--design", help="parameter file of the design (default: the pick of the run)")
    ap.add_argument("--out", help="output folder (default: <run>/post/<pick>/<name of the analysis>)")
    ap.add_argument("--fidelity", help="mesh fidelity level of the specification (default: its own level)")
    ap.add_argument("--positions", type=int, help="rotor positions per half electrical period")
    ap.add_argument("--jobs", type=int, help="rotor positions solved at the same time")


def load(args, analysis_name):
    """Returns (spec, design values, parameter file contents, output folder)."""
    spec_file, design_file, out = args.spec, args.design, args.out
    if args.run:
        spec_file = spec_file or os.path.join(args.run, "spec.json")
        design_file = design_file or os.path.join(args.run, "designs", args.pick + ".json")
        out = out or os.path.join(args.run, "post", args.pick, analysis_name)
    if not spec_file or not design_file or not out:
        raise PickError("Give --run (and optionally --pick), or --spec, --design and --out.")
    for path, what in ((spec_file, "specification"), (design_file, "design")):
        if not os.path.isfile(path):
            hint = " Runs made before spec.json existed need --spec." if what == "specification" and args.run else ""
            raise PickError(f"The {what} file {path} does not exist.{hint}")
    spec = load_spec(spec_file)
    if args.fidelity:
        if args.fidelity not in spec["fidelity"]["levels"]:
            raise PickError(f"Fidelity level {args.fidelity!r} is not defined. "
                            f"Available: {sorted(spec['fidelity']['levels'])}.")
        spec["fidelity"]["level"] = args.fidelity
    if args.positions:
        spec["fidelity"]["positions"] = args.positions
    if args.jobs:
        spec["optimizer"]["jobs"] = args.jobs
    with open(design_file) as f:
        parameters = json.load(f)
    if isinstance(parameters.get("design"), dict):
        raw = parameters["design"]
    elif "stator" in parameters:
        raise PickError(f"{design_file} has no 'design' section. Use a parameter file written by emachine optimize.")
    else:
        raw = parameters
        parameters = {}
    raw = standard_values(spec, raw)
    names = [v["name"] for v in design.variables(spec)]
    missing = [n for n in names if n not in raw]
    if missing:
        raise PickError(f"{design_file} lacks the design variables {missing} of this specification.")
    values = design.clip(spec, {n: raw[n] for n in names})
    changed = [n for n in names if abs(values[n] - raw[n]) > 1e-9]
    if changed:
        raise PickError(f"{design_file}: {changed} lie outside the ranges of the specification.")
    return spec, values, copy.deepcopy(parameters), os.path.abspath(out)


def turns_of(parameters):
    """Turns recorded with a pick, or None."""
    turns = (parameters.get("summary") or {}).get("turns") or (parameters.get("analysis") or {}).get("coil_turns")
    return int(turns) if turns and int(turns) > 1 else None
