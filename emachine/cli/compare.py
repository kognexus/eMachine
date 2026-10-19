"""
Grid of the best designs of several optimization runs, one run per stator type.

    emachine compare --runs runs/types --out runs/types/grid.md --verify

Every sub-folder of --runs that holds an optimization run (spec.json and state.json) becomes one
row block of the grid. For each run the three picks are listed: highest torque, lowest loss and
best compromise. With --verify every pick is solved again directly (no interpolation between
load levels, all rotor positions), and the grid shows those numbers.

--note TYPE=TEXT adds a row for a stator type that was not run, with the reason.
"""

import argparse
import csv
import json
import os
import sys
import time

from emachine.cli import describe
from emachine.pipeline import design_space as design
from emachine.pipeline import evaluate
from emachine.spec import load_spec
from emachine.spec import names

TYPE_NAMES = {"u_core": "U-core", "ui_core": "U-core with I-bridge", "claw_pole": "Claw pole", "e_core": "E-core",
              "c_core": "C-core", "z_core": "Z-core", "toothed_ring": "Toothed ring"}
PICKS = ("highest_torque", "best_compromise", "lowest_loss")


def read_run(rundir):
    """Specification, counts and picks of one run, or None when the folder is not a finished run."""
    spec_file = os.path.join(rundir, "spec.json")
    if not os.path.isfile(spec_file) or not os.path.isfile(os.path.join(rundir, "all_designs.csv")):
        return None
    spec = load_spec(spec_file)
    with open(os.path.join(rundir, "all_designs.csv")) as f:
        rows = list(csv.DictReader(f))
    with open(os.path.join(rundir, "pareto.csv")) as f:
        front = list(csv.DictReader(f))
    picks = {}
    for name in PICKS:
        path = os.path.join(rundir, "designs", name + ".json")
        if os.path.isfile(path):
            with open(path) as f:
                picks[name] = json.load(f)
            picks[name]["design"] = names.standard_values(spec, picks[name]["design"])
    analysed = [r for r in rows if r["analysed"] == "True"]
    closest = None
    if not front and analysed:
        closest = min(analysed, key=lambda r: float(r["violation"]))
    return {"dir": rundir, "spec": spec, "type": spec["machine"].get("stator", describe.label(spec)), "designs": len(rows),
            "analysed": len(analysed), "feasible": sum(r["feasible"] == "True" for r in rows),
            "front": len(front), "picks": picks, "closest": closest,
            "stopped": sum(r.get("stopped_early") == "True" for r in rows)}


MEDIUM = {"gap_cell_factor": 1.0, "size_max_mm": 4.0}       # between the levels "fast" (1.5) and "fine" (0.6)


def verify(run, name, log=print, level=None, positions=None):
    """Direct field solution of a pick: its own ampere-turns, all rotor positions, no staging."""
    spec = json.loads(json.dumps(run["spec"]))
    spec["fidelity"]["load_levels"] = 0
    spec["fidelity"]["staged"] = False
    if level:
        if level == "medium":
            spec["fidelity"]["levels"].setdefault("medium", dict(MEDIUM))
        spec["fidelity"]["level"] = level
    if positions:
        spec["fidelity"]["positions"] = int(positions)
    values = design.clip(spec, run["picks"][name]["design"])
    began = time.time()
    record = evaluate.evaluate(spec, values, os.path.join(run["dir"], "verify"))
    if log:
        if record["analysed"]:
            o = record["objectives"]
            log(f"  {run['type']} {name}: {o['torque_Nm']:.3f} Nm, ripple {100 * o['ripple']:.1f} %, "
                f"loss {o['loss_W']:.2f} W ({time.time() - began:.0f} s)")
        else:
            log(f"  {run['type']} {name}: {record.get('reason')}")
    return record if record["analysed"] else None


def numbers(run, name, record):
    """The numbers of one cell: from the direct solution when there is one, else from the run."""
    summary = run["picks"][name]["summary"]
    values = run["picks"][name]["design"]
    if record:
        out = {"torque_Nm": record["objectives"]["torque_Nm"], "ripple_percent": 100 * record["objectives"]["ripple"],
               "loss_W": record["objectives"]["loss_W"], "efficiency": record["efficiency"],
               "turns": record["winding"]["turns"], "peak_current_A": record["winding"]["peak_current_A"],
               "bus_V": record["winding"]["required_bus_voltage_V"], "winding_C": record["thermal"]["winding_C"],
               "within_limits": record["violation"] == 0, "verified": True,
               "violated": [k for k, v in record["constraints"].items() if v > 0]}
    else:
        out = {"torque_Nm": summary["torque_Nm"], "ripple_percent": 100 * summary["ripple"], "loss_W": summary["loss_W"],
               "efficiency": summary["efficiency"], "turns": summary["turns"], "peak_current_A": summary["peak_current_A"],
               "bus_V": summary["required_bus_voltage_V"], "winding_C": summary["winding_C"], "within_limits": True,
               "verified": False, "violated": []}
    out["run_torque_Nm"] = summary["torque_Nm"]
    out["run_ripple_percent"] = 100 * summary["ripple"]
    out["values"] = values
    return out


def write_grid(path, runs, cells, notes, verified, level=None):
    m = runs[0]["spec"]["machine"] if runs else {}
    lim = runs[0]["spec"]["limits"] if runs else {}
    out = ["# Stator types compared", ""]
    if runs:
        out += [f"All runs: {describe.summary(runs[0]['spec'])}, outer diameter "
                f"{m['outer_diameter_mm']:g} mm, stack {m['stack_length_mm']:g} mm, air gap {m['air_gap_mm']:g} mm, bore {m['bore_diameter_mm']:g} mm, "
                f"{runs[0]['spec']['operating_point']['speed_rpm']:g} rpm. Limits: torque ripple "
                f"{lim['max_torque_ripple_percent']:g} %, bus {lim['bus_voltage_V'][1]:g} V, current {lim['max_current_A']:g} A, "
                f"iron {lim['iron_thickness_mm'][0]:g} to {lim['iron_thickness_mm'][1]:g} mm, "
                f"{lim['pole_pairs'][0]} to {lim['pole_pairs'][1]} pole pairs.", ""]
    out += ["Numbers are " + (f"from a direct field solution of each pick (all rotor positions, its own current"
                              f"{', mesh level ' + level if level else ''})."
                              if verified else "as found by the optimization; picks were not solved again."), "",
            "Ripple below about 25 % is uncertain by roughly 10 percentage points at the optimization mesh: each phase "
            "pulsates with several times its mean torque, the three phases cancel these pulsations, and a mesh error "
            "of 1 % in one phase leaves a visible residue.", "",
            "## Grid", "",
            "Each cell: mean torque, torque ripple, total loss, efficiency.", "",
            "| Stator type | Highest torque | Best compromise | Lowest loss |", "|---|---|---|---|"]
    for run in runs:
        row = [TYPE_NAMES.get(run["type"], run["type"])]
        for name in PICKS:
            c = cells.get((run["type"], name))
            if c is None:
                row.append("no design within the limits")
            else:
                flag = "" if c["within_limits"] else " (outside limits: " + ", ".join(c["violated"]).replace("_", " ") + ")"
                row.append(f"{c['torque_Nm']:.3f} Nm, {c['ripple_percent']:.1f} %, {c['loss_W']:.2f} W, "
                           f"{100 * c['efficiency']:.1f} %{flag}")
        out.append("| " + " | ".join(row) + " |")
    for kind, text in notes:
        out.append(f"| {TYPE_NAMES.get(kind, kind)} | not run: {text} | | |")
    out += ["", "## Designs", "",
            "| Stator type | Pick | Torque (Nm) | Ripple (%) | Loss (W) | Efficiency (%) | Pole pairs | Tooth arc (el. deg) | "
            "Slot height (mm) | Yoke (mm) | Magnet (mm) | Rotor iron (mm) | Current density (A/mm2) | Turns | "
            "Peak current (A) | Bus (V) | Winding (C) |", "|" + "---|" * 17]
    for run in runs:
        for name in PICKS:
            c = cells.get((run["type"], name))
            if c is None:
                continue
            v = c["values"]
            out.append(f"| {TYPE_NAMES.get(run['type'], run['type'])} | {name.replace('_', ' ')} | {c['torque_Nm']:.3f} | "
                       f"{c['ripple_percent']:.1f} | {c['loss_W']:.2f} | {100 * c['efficiency']:.1f} | {v['pole_pairs']} | "
                       f"{v['tooth_arc_el_deg']:.1f} | {v['slot_height_mm']:.2f} | {v['yoke_height_mm']:.2f} | "
                       f"{v['magnet_thickness_mm']:.2f} | {v.get('rotor_iron_mm', float('nan')):.2f} | "
                       f"{v['current_density_A_mm2']:.2f} | {c['turns']} | {c['peak_current_A']:.2f} | {c['bus_V']:.1f} | "
                       f"{c['winding_C']:.0f} |")
    extra = sorted({k for run in runs for p in run["picks"].values() for k in p["design"]}
                   - {"pole_pairs", "tooth_arc_el_deg", "slot_height_mm", "yoke_height_mm", "magnet_thickness_mm",
                      "rotor_iron_mm", "current_density_A_mm2", "leg_width_mm"})
    if extra:
        out += ["", "Type-specific dimensions:", "", "| Stator type | Pick | " + " | ".join(extra) + " |",
                "|---|---|" + "---|" * len(extra)]
        for run in runs:
            for name in PICKS:
                c = cells.get((run["type"], name))
                if c:
                    out.append(f"| {TYPE_NAMES.get(run['type'], run['type'])} | {name.replace('_', ' ')} | "
                               + " | ".join(f"{c['values'][k]:.2f}" if k in c["values"] else "" for k in extra) + " |")
    if verified:
        out += ["", "## Optimization against direct solution", "",
                "The optimization interpolates between load levels and reads ripple from 12 rotor positions on a mesh "
                "that changes with every position. The direct solution of a pick can therefore differ.", "",
                "| Stator type | Pick | Torque in the run (Nm) | Direct (Nm) | Ripple in the run (%) | Direct (%) |",
                "|---|---|---|---|---|---|"]
        for run in runs:
            for name in PICKS:
                c = cells.get((run["type"], name))
                if c and c["verified"]:
                    out.append(f"| {TYPE_NAMES.get(run['type'], run['type'])} | {name.replace('_', ' ')} | "
                               f"{c['run_torque_Nm']:.3f} | {c['torque_Nm']:.3f} | {c['run_ripple_percent']:.1f} | "
                               f"{c['ripple_percent']:.1f} |")
    out += ["", "## Runs", "",
            "| Stator type | Designs | Analysed | Within all limits | Trade-off designs | Stopped after the first stage | Folder |",
            "|---|---|---|---|---|---|---|"]
    for run in runs:
        out.append(f"| {TYPE_NAMES.get(run['type'], run['type'])} | {run['designs']} | {run['analysed']} | {run['feasible']} | "
                   f"{run['front']} | {run['stopped']} | `{os.path.relpath(run['dir'])}` |")
    for run in runs:
        if not run["front"] and run["closest"]:
            c = run["closest"]
            out += ["", f"{TYPE_NAMES.get(run['type'], run['type'])}: no design met every limit. Closest: "
                    f"{float(c['torque_Nm']):.3f} Nm, ripple {float(c['ripple_percent']):.1f} %, loss {float(c['loss_W']):.2f} W "
                    f"({c['reason']})."]
    out += ["", "Onshape parameters of every pick: `<folder>/designs/<pick>.onshape.md`. Efficiency map and ParaView "
            "files of a pick: `emachine map --run <folder> --pick <pick>` and `emachine export --run <folder> --pick <pick>`.",
            ""]
    with open(path, "w") as f:
        f.write("\n".join(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="folder whose sub-folders are optimization runs")
    ap.add_argument("--out", help="grid file (default: <runs>/grid.md)")
    ap.add_argument("--verify", action="store_true", help="solve every pick again directly with the field solver")
    ap.add_argument("--fidelity", help="mesh level for --verify: fast, medium or fine (default: the level of the "
                                       "run). Finer meshes give steadier ripple values and take longer.")
    ap.add_argument("--positions", type=int, help="rotor positions per half electrical period for --verify")
    ap.add_argument("--note", action="append", default=[], metavar="TYPE=TEXT",
                    help="row for a stator type that was not run, with the reason")
    args = ap.parse_args(argv)
    runs = []
    for name in sorted(os.listdir(args.runs)):
        run = read_run(os.path.join(args.runs, name)) if os.path.isdir(os.path.join(args.runs, name)) else None
        if run:
            runs.append(run)
    if not runs and not args.note:
        sys.exit(f"No finished optimization run found under {args.runs}.")
    order = list(TYPE_NAMES)
    runs.sort(key=lambda r: order.index(r["type"]) if r["type"] in order else len(order))
    cells = {}
    for run in runs:
        for name in PICKS:
            if name in run["picks"]:
                record = verify(run, name, level=args.fidelity, positions=args.positions) if args.verify else None
                cells[(run["type"], name)] = numbers(run, name, record)
    notes = [tuple(text.split("=", 1)) for text in args.note if "=" in text]
    notes = [(names.VALUES["stator"].get(kind, kind), text) for kind, text in notes]     # old codes: u, cp, z, ...
    out = args.out or os.path.join(args.runs, "grid.md")
    write_grid(out, runs, cells, notes, args.verify,
               ", ".join(x for x in (args.fidelity, f"{args.positions} rotor positions" if args.positions else None) if x))
    print(f"Grid of {len(runs)} runs -> {out}")

