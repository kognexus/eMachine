"""
TFM analysis pipeline: parameter file -> Gmsh sector mesh -> Elmer magnetostatics -> results table.

    emachine solve --params examples/params/motor_matched.json --run runs/first

For every rotor position the pipeline
    1. meshes one periodic sector with the rotor parts turned to that position (emachine mesh);
    2. converts the mesh for Elmer (millimetres -> metres) and joins the rotor and stator meshes
       node for node across the sliding surface in the air gap;
    3. writes an Elmer case from the region description and the "analysis" settings;
    4. solves the magnetostatic problem;
    5. extracts torque, field energy and the flux linked by the coil.
Positions are independent, so they run in parallel. The results of all positions are collected
in results.csv, scaled from the sector to the whole ring (one phase of the machine).

The "analysis" section of the parameter file controls the physics. Missing values fall back to
ANALYSIS_DEFAULTS (emachine/solvers/elmer/sector3d.py).

Since T35 the work is done by the geometry builder "tfm.sector3d"
(emachine/machines/tfm/geometry/builder.py) and the field solver "elmer3d"
(emachine/solvers/elmer/sector3d.py); this file keeps the command and the old names.
"""

import argparse
import copy
import csv
import json
import os
import shutil
import sys
import time

from emachine.pipeline.sweep import run_rows
from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS, ELMER_HOME


def load_settings(params_file):
    with open(params_file) as f:
        params = json.load(f)
    analysis = copy.deepcopy(ANALYSIS_DEFAULTS)
    for key, value in params.get("analysis", {}).items():
        if key not in analysis:
            sys.exit(f"Unknown parameter 'analysis.{key}'.")
        analysis[key] = value
    return params, analysis





def run_positions(params, analysis, angles, rundir, jobs=4, currents=None, core_field=False, report=None):
    return run_rows(params, analysis, angles, rundir, jobs, currents, core_field, report)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", required=True, help="parameter file with stator, rotor, mesh and analysis sections")
    ap.add_argument("--run", required=True, help="folder for this run (created if needed)")
    ap.add_argument("--jobs", type=int, default=4, help="rotor positions solved at the same time")
    args = ap.parse_args(argv)

    if not os.path.isfile(os.path.join(ELMER_HOME, "bin", "ElmerSolver")):
        sys.exit(f"ElmerSolver not found under {ELMER_HOME}. Set ELMER_HOME to the Elmer install folder.")
    params, analysis = load_settings(args.params)
    rundir = os.path.abspath(args.run)
    os.makedirs(rundir, exist_ok=True)
    shutil.copyfile(args.params, os.path.join(rundir, "parameters.json"))

    # The sweep defaults to one electrical period = two pole pitches of the stator.
    positions = int(analysis["positions"])
    period = 360.0 / int(params.get("stator", {}).get("pole_pairs", 16))
    sweep = analysis["sweep_deg"] if analysis["sweep_deg"] is not None else period
    angles = [float(analysis["sweep_start_deg"]) + sweep * k / positions for k in range(positions)]
    print(f"{positions} rotor positions from {angles[0]:g} deg in steps of {sweep / positions:g} deg, "
          f"{args.jobs} at a time; coil {analysis['coil_turns']} turns x {analysis['coil_current_A']:g} A")

    began = time.time()

    def report(angle, row, error):
        if error is not None:
            print(f"  {angle:8.3f} deg  FAILED: {str(error).splitlines()[0]}")
            return
        flux = row["flux_linkage_Wb"]
        print(f"  {angle:8.3f} deg  torque {row['torque_Nm']:+.5f} Nm  "
              f"flux {'n/a' if flux is None else format(flux, '+.6f')} Wb  "
              f"({row['solver_iterations']} iterations, {row['seconds']:.0f} s)")

    rows, failed = run_positions(params, analysis, angles, rundir, args.jobs, report=report)
    for warning in sorted({w for r in rows for w in r["warnings"]}):
        print("  " + warning)
    table = os.path.join(rundir, "results.csv")
    columns = ["rotor_angle_deg", "torque_Nm", "field_energy_J", "flux_linkage_Wb", "solver_iterations",
               "elements", "seconds"]
    with open(table, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(columns)
        for r in rows:
            out.writerow(["" if r[c] is None else (f"{r[c]:.8g}" if isinstance(r[c], float) else r[c]) for c in columns])
    if rows:
        torque = [r["torque_Nm"] for r in rows]
        print(f"Torque of the whole machine (one phase): mean {sum(torque) / len(torque):+.5f} Nm, "
              f"min {min(torque):+.5f}, max {max(torque):+.5f}")
        flux = [r["flux_linkage_Wb"] for r in rows if r["flux_linkage_Wb"] is not None]
        if flux:
            print(f"Coil flux linkage: min {min(flux):+.6f} Wb, max {max(flux):+.6f} Wb")
    print(f"Table -> {table}   ({time.time() - began:.0f} s in total)")
    if failed:
        sys.exit(f"{len(failed)} of {positions} positions failed. See the logs in {rundir}.")

