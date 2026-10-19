#!/usr/bin/env python3
"""
T08: how the results of the reference design change with the mesh size in the air gap.

Runs the sinusoidally driven analysis at several cell-size factors (cell size on the sliding
surfaces = factor * air gap) and writes examples/mesh_fidelity/fidelity_results.csv.

    python examples/mesh_fidelity/fidelity_study.py
"""

import csv
import os
import tempfile

import numpy as np

from emachine.machines.tfm import design
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.physics import torque
from emachine.pipeline.sweep import field_analysis
from emachine.spec import load_spec

HERE = os.path.dirname(os.path.abspath(__file__))
analyse = field_analysis("tfm.sector3d", "elmer3d")

FACTORS = [0.6, 1.0, 1.5, 2.0, 3.0]
POSITIONS = 12


def main():
    rows = []
    with tempfile.TemporaryDirectory(prefix="tfm_fidelity_") as tmp:
        for factor in FACTORS:
            spec = load_spec({"fidelity": {"level": "study", "levels": {"study": {"gap_cell_factor": factor, "size_max_mm": 6.0}}}})
            params = design.to_parameters(spec, REFERENCE_DESIGN)
            result = analyse(params, POSITIONS, os.path.join(tmp, f"f{factor}"), jobs=6)
            one = torque.metrics(torque.machine_torque(result["torque_Nm"], 1, period="half"))
            three = torque.metrics(torque.machine_torque(result["torque_Nm"], 3, period="half"))
            b_rms = []
            for path in result["core_field_files"]:
                data = np.load(path)
                b = np.linalg.norm(data["b"], axis=1)
                b_rms.append(np.sqrt(np.sum(data["volume"] * b ** 2) / data["volume"].sum()))
            rows.append({
                "gap_cell_factor": factor,
                "gap_cell_mm": factor * spec["machine"]["air_gap_mm"],
                "elements": result["elements"],
                "mean_torque_Nm": one["mean"],
                "torque_peak_to_peak_1ph_Nm": one["peak_to_peak"],
                "torque_peak_to_peak_3ph_Nm": three["peak_to_peak"],
                "peak_flux_per_turn_uWb": 1e6 * float(np.max(np.abs(result["flux_per_turn_Wb"]))),
                "core_b_rms_T": float(np.max(b_rms)),
                "max_solver_iterations": max(result["solver_iterations"]),
                "seconds": round(result["seconds"], 1),
            })
            print(rows[-1], flush=True)
    path = os.path.join(HERE, "fidelity_results.csv")
    with open(path, "w", newline="") as f:
        out = csv.DictWriter(f, fieldnames=list(rows[0]))
        out.writeheader()
        for row in rows:
            out.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in row.items()})
    print("written", path)


if __name__ == "__main__":
    main()
