"""
Validation of the field solver against a published TFM prototype.

    emachine validate examples/validation/guo2006/case.json --jobs 6
    emachine validate examples/validation/guo2006/case.json --variant tooth_6mm   # one variant only

The case file gives the machine exactly (stator and rotor parameters of the mesher, materials of
the solver), the operating point of the measurement, and the published values with their source.
The steps follow the tests of the paper:

    no load     flux per turn and cogging torque of one phase over one electrical period;
                back-EMF constant, cogging torque of all phases (phase k shifted k/phases of a period)
    inductance  magnets switched off (remanence 0), rated current: self-inductance of one phase
    load        sinusoidal current in phase with the induced voltage at the rated rms current:
                torque of one phase and of all phases
    resistance  of the coil from its mean turn length (round wire, turns and wire diameter)
    losses      stator core (alternating and rotational, per harmonic) and rotor eddy currents
                (iron, housing, magnets), from the no-load field and from the loaded field (T31),
                with the materials of the case

Written to the case folder (or --out): results.json, waveforms.csv and report.md, which compares
every computed value with the published one. Variants ("variants" in the case file) change
parameters for a sensitivity study; each is written under variants/<name>/.
"""

import argparse
import copy
import csv
import json
import math
import os
import sys
import time

import numpy as np

from emachine.physics import losses
from emachine.pipeline import sweep as pipeline_sweep
from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS

MU0 = 4e-7 * math.pi


def merge(base, changes):
    """Deep merge of nested dicts: `changes` wins."""
    out = copy.deepcopy(base)
    for key, value in (changes or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def fundamental(values):
    """Amplitude and phase of the first harmonic of samples over one full period: v ~ A cos(x - phase)."""
    v = np.asarray(values, dtype=float)
    c = np.fft.rfft(v) / len(v)
    return 2 * abs(c[1]), -float(np.angle(c[1]))


def all_phases(waveform, phases):
    """Sum of the waveform shifted by k / phases of the period (samples over one full period)."""
    w = np.asarray(waveform, dtype=float)
    if phases == 1:
        return w.copy()
    if len(w) % phases:
        raise ValueError(f"{len(w)} samples per period cannot be split into {phases} phases.")
    return sum(np.roll(w, -k * len(w) // phases) for k in range(phases))


def solve(params, analysis, angles, rundir, jobs, currents=None, core_field=False):
    rows, failed = pipeline_sweep.run_rows(params, analysis, angles, rundir, jobs, currents, core_field,
                                              report=lambda a, r, e: print(
                                                  f"    {a:8.3f} deg: " + (f"torque {r['torque_Nm']:+.4f} Nm, "
                                                  f"flux {r['flux_linkage_Wb']:+.5f} Wb ({r['seconds']:.0f} s)"
                                                  if r else f"FAILED {e}"), flush=True))
    if failed:
        raise RuntimeError(f"{len(failed)} positions failed, first: {failed[0]}")
    return rows


def coil_resistance(params, op, temp_C):
    """Phase resistance of a round-wire ring coil: turns x mean turn length x resistivity / copper area.
    The coil sits at the far end of the coil window, as the mesher places it."""
    st = params["stator"]
    window_top = st["slot_height"] + (st.get("claw_root_height", 0.0) if st["core_type"] == "cp" else 0.0)
    depth = window_top - st["coil_clearance"] - st["coil_height"] / 2       # coil centre below the air gap
    sign = -1.0 if st["inner_stator"] else 1.0
    mean_radius_m = (st["air_gap_radius"] + sign * depth) / 1000.0
    area = op.get("strands", 1) * math.pi * (op["wire_diameter_mm"] / 2000.0) ** 2
    rho = 1.72e-8 * (1 + 0.00393 * (temp_C - 20.0))
    return op["turns"] * 2 * math.pi * mean_radius_m * rho / area, mean_radius_m


def analyse(case, outdir, jobs):
    params, op = case["params"], case["operating"]
    analysis = merge(ANALYSIS_DEFAULTS, case["analysis"])
    analysis["coil_turns"] = op["turns"]
    p = params["stator"]["pole_pairs"]
    phases = op["phases"]
    n = int(case.get("positions_per_period", 24))
    period_deg = 360.0 / p
    angles = np.arange(n) * period_deg / n
    began = time.time()

    print(f"  no load: {n} positions over {period_deg:g} deg", flush=True)
    rows0 = solve(params, dict(analysis, coil_current_A=0.0), angles, os.path.join(outdir, "raw", "no_load"), jobs,
                  core_field=True)
    flux0 = np.array([r["flux_linkage_Wb"] for r in rows0]) / op["turns"]       # per turn
    cogging = np.array([r["torque_Nm"] for r in rows0])
    flux_amp, flux_phase = fundamental(flux0)

    omega_r = op["speed_rpm"] * 2 * math.pi / 60.0
    # E1 (rms, line to neutral, fundamental) = k * omega_r with k = p * turns * flux amplitude / sqrt(2).
    k_emf = p * op["turns"] * flux_amp / math.sqrt(2)

    # Load: current in phase with the induced voltage, for flux ~ cos(theta_e - phase): the solver's
    # convention (tfm/electrical.py, current_shape) is i = -I_peak * sin(theta_e - phase), which gives
    # positive (motoring) torque.
    i_peak = op["phase_current_rms_A"] * math.sqrt(2)
    theta_e = np.radians(angles * p)
    currents = -i_peak * np.sin(theta_e - flux_phase)
    print(f"  load: {i_peak:.3f} A peak, {op['turns'] * i_peak:.1f} ampere-turns peak", flush=True)
    rows1 = solve(params, analysis, angles, os.path.join(outdir, "raw", "load"), jobs, currents, core_field=True)
    torque1 = np.array([r["torque_Nm"] for r in rows1])
    machine = all_phases(torque1, phases)

    print("  inductance: magnets off", flush=True)
    off = dict(analysis, magnet_remanence_T=0.0, coil_current_A=i_peak)
    l_angles = angles[: max(1, n // 4) + 1: max(1, n // 12)][:3]
    rows2 = solve(params, off, l_angles, os.path.join(outdir, "raw", "inductance"), jobs)
    inductance = np.array([r["flux_linkage_Wb"] for r in rows2]) / i_peak

    r20, mean_radius = coil_resistance(params, op, 20.0)
    r_hot, _ = coil_resistance(params, op, op.get("winding_temp_C", 20.0))
    result = {
        "seconds": round(time.time() - began),
        "elements": rows0[0]["elements"],
        "angles_deg": angles.tolist(),
        "flux_per_turn_Wb": flux0.tolist(),
        "flux_per_turn_peak_Wb": float(np.max(np.abs(flux0))),
        "flux_per_turn_fundamental_Wb": flux_amp,
        "emf_constant_Vs": k_emf,
        "emf_rms_at_speed_V": k_emf * omega_r,
        "cogging_one_phase_Nm": cogging.tolist(),
        "cogging_one_phase_peak_Nm": float(np.max(np.abs(cogging))),
        "cogging_all_phases_Nm": all_phases(cogging, phases).tolist(),
        "cogging_all_phases_peak_Nm": float(np.max(np.abs(all_phases(cogging, phases)))),
        "phase_current_A": currents.tolist(),
        "torque_one_phase_Nm": torque1.tolist(),
        "torque_all_phases_Nm": machine.tolist(),
        "torque_em_mean_Nm": float(machine.mean()),
        "torque_ripple_pp_Nm": float(machine.max() - machine.min()),
        "torque_em_from_emf_Nm": phases * k_emf * op["phase_current_rms_A"],
        "inductance_H": inductance.tolist(),
        "inductance_mean_H": float(inductance.mean()),
        "resistance_20C_ohm": r20,
        "resistance_hot_ohm": r_hot,
        "coil_mean_radius_mm": mean_radius * 1000,
    }
    result.update(loss_results(case, outdir, result))
    return result


def loss_results(case, outdir, result):
    """
    Core and rotor losses at the rated speed (T31) from the saved fields: from the no-load field
    (the papers' no-load test) and from the loaded field (rated point), then the rated output and
    efficiency. The earlier model, alternating loss on the peak flux density of the no-load field,
    is kept for comparison.
    """
    op, p = case["operating"], case["params"]["stator"]["pole_pairs"]
    phases = op["phases"]
    materials = case["materials"]
    material = materials["stator_core"]
    spec_like = {"materials": materials}
    f_e = op["speed_rpm"] / 60.0 * p
    omega_r = op["speed_rpm"] * 2 * math.pi / 60.0

    def files(sweep):
        folder = os.path.join(outdir, "raw", sweep)
        return [os.path.join(folder, d, "core_field.npz") for d in sorted(os.listdir(folder))
                if os.path.isfile(os.path.join(folder, d, "core_field.npz"))]

    no_load, load = files("no_load"), files("load")
    volume, peak = losses.core_peak_field(no_load)
    old_model = float(np.sum(volume * material["density_kg_m3"] * losses.iron_loss_density(
        dict(material, k_anomalous=material.get("k_anomalous", 0.0)), f_e, peak)))
    c0 = losses.iron_loss_coefficients(spec_like, no_load)
    c1 = losses.iron_loss_coefficients(spec_like, load) if load else c0
    stator0, rotor0 = (float(v) for v in losses.loss_at(c0, f_e, materials))
    stator1, rotor1 = (float(v) for v in losses.loss_at(c1, f_e, materials))
    parts1 = {name: float(v) for name, v in losses.rotor_loss(c1, f_e, materials).items()}
    copper = phases * op["phase_current_rms_A"] ** 2 * result["resistance_hot_ohm"]
    core = phases * (stator1 + rotor1)                 # rated point: loaded field
    mech = op.get("mechanical_loss_W", 0.0)
    p_out = result["torque_em_mean_Nm"] * omega_r - core - mech
    return {
        "core_loss_no_load_peak_model_W": phases * old_model,
        "stator_loss_no_load_W": phases * stator0,
        "rotor_loss_no_load_W": phases * rotor0,
        "core_loss_no_load_W": phases * (stator0 + rotor0),
        "stator_loss_load_W": phases * stator1,
        "rotor_loss_load_W": phases * rotor1,
        "rotor_loss_load_by_part_W": {k: phases * v for k, v in parts1.items()},
        "core_loss_load_W": core,
        "core_b_p95_T": float(np.percentile(peak, 95)),
        "core_mass_kg": float(np.sum(volume) * material["density_kg_m3"]),
        "copper_loss_W": copper,
        "output_power_W": p_out,
        "output_torque_Nm": p_out / omega_r,
        "efficiency_motor": p_out / (p_out + copper + core + mech),
    }


def compare_rows(result, published):
    rows = []
    for item in published:
        computed = result.get(item["key"])
        if computed is None:
            continue
        computed = computed * item.get("scale", 1.0)
        value = item["value"]
        error = (computed - value) / value if value else float("nan")
        rows.append({**item, "computed": computed, "error": error})
    return rows


def write_outputs(outdir, case, result, title):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(result, f, indent=1)
    columns = ["angles_deg", "flux_per_turn_Wb", "cogging_one_phase_Nm", "cogging_all_phases_Nm",
               "phase_current_A", "torque_one_phase_Nm", "torque_all_phases_Nm"]
    with open(os.path.join(outdir, "waveforms.csv"), "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["rotor_angle_deg", "flux_per_turn_Wb", "cogging_one_phase_Nm", "cogging_all_phases_Nm",
                      "phase_current_A", "torque_one_phase_Nm", "torque_all_phases_Nm"])
        for k in range(len(result["angles_deg"])):
            out.writerow([f"{result[c][k]:.7g}" for c in columns])
    rows = compare_rows(result, case["published"])
    lines = [f"# {title}", "", case.get("source", ""), "",
             f"{result['elements']} elements per sector, {len(result['angles_deg'])} positions per electrical period, "
             f"{result['seconds']} s.", "",
             "| Quantity | Published | Kind | Computed | Difference |", "|---|---|---|---|---|"]
    for r in rows:
        unit = r.get("unit", "")
        lines.append(f"| {r['label']} | {r['value']:g} {unit} | {r['kind']} | {r['computed']:.4g} {unit} | "
                     f"{100 * r['error']:+.1f} % |")
    lines += ["", "Kind: measured on the prototype, FEA of the authors, or derived from published values.", ""]
    with open(os.path.join(outdir, "report.md"), "w") as f:
        f.write("\n".join(lines))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case", help="case file (JSON)")
    ap.add_argument("--out", help="output folder (default: the folder of the case file)")
    ap.add_argument("--jobs", type=int, default=6, help="positions solved at the same time")
    ap.add_argument("--variant", action="append", help="run only these variants ('base' for the case itself)")
    ap.add_argument("--losses-only", action="store_true",
                    help="recompute the losses from the saved fields (raw/) and rewrite the reports, without solving")
    args = ap.parse_args()
    with open(args.case) as f:
        case = json.load(f)
    outdir = args.out or os.path.dirname(os.path.abspath(args.case))
    runs = [("base", {})] + list(case.get("variants", {}).items())
    if args.variant:
        runs = [(name, change) for name, change in runs if name in args.variant]
    for name, change in runs:
        variant = merge(case, change)
        target = outdir if name == "base" else os.path.join(outdir, "variants", name)
        print(f"{case['name']}, {name}", flush=True)
        if args.losses_only:
            with open(os.path.join(target, "results.json")) as f:
                result = json.load(f)
            result.update(loss_results(variant, target, result))
        else:
            result = analyse(variant, target, args.jobs)
        rows = write_outputs(target, variant, result, f"{case['name']}: {name}")
        for r in rows:
            print(f"  {r['label']:<45} published {r['value']:>9.4g}  computed {r['computed']:>9.4g}  "
                  f"{100 * r['error']:+6.1f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
