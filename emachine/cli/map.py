"""
Torque, speed and efficiency map of one design.

    emachine map --run runs/opt1                      # best compromise of a run
    emachine map --run runs/opt1 --pick highest_torque
    emachine map --spec spec.json --design design.json --out runs/map1

The field is solved at a few load levels (--levels) and every speed is derived from them.
Written to the output folder (default <run>/post/<pick>/map):

    efficiency_map.csv   one row per point of the speed and torque grid
    envelope.csv         highest torque per speed: drive limit and continuous limit
    efficiency_map.vtu   the grid as a surface for ParaView (x speed in 1000 rpm, y torque in N m)
    efficiency_limits.vtu  drive and continuous limit as lines for ParaView
    load_levels.csv      torque and iron-loss coefficients of each field solution
    efficiency_map.svg   picture of the map
    map.md               summary and assumptions
    load_levels.json     field results; reused when the command runs again

--turns sets another number of turns than the optimizer chose (fewer turns: more speed, more current).
--dry-run replaces the field solver by a crude analytic estimate, to test the workflow in seconds.
"""

import argparse
import csv
import json
import math
import os
import sys
import time

import numpy as np

from emachine.analysis import effmap
from emachine.cli import describe
from emachine.io import paraview_files as paraviewfiles
from emachine.io import svg as svgplot
from emachine.physics import losses
from emachine.physics import winding as winding_model
from emachine.pipeline import design_space as design
from emachine.pipeline import evaluate, picks

BANDS = [0.0, 0.3, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.975, 1.0]
BAND_COLORS = ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58",
               "#b5de2b", "#fde725", "#ffb000", "#ff7a00"]

COLUMNS = ["speed_rpm", "torque_Nm", "efficiency", "output_power_W", "input_power_W", "loss_W", "copper_loss_W",
           "iron_loss_W", "peak_current_A", "rms_current_A", "current_density_A_mm2", "bus_voltage_needed_V",
           "ampere_turns_peak", "winding_C", "magnet_C", "within_drive_limits", "continuous"]


def cell_text(value):
    if isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return "" if not math.isfinite(value) else f"{value:.6g}"
    return "" if value is None else value


def write_csv(path, columns, rows):
    with open(path, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(columns)
        for row in rows:
            out.writerow([cell_text(v) for v in row])


def wire_rows(spec, machine):
    """The round wire of the turns at the fill factor of the specification (AWG), for map.md."""
    if spec["winding"]["conductor"] == "strip":
        return []
    w = design.machine_of(spec).winding(spec, machine.values)
    gauge = winding_model.wire_gauge(w.coil_area_mm2 * w.fill_factor / machine.turns)
    if gauge["awg"] is None:
        return ["| Wire | thinner than AWG 40 at this fill factor |"]
    share = gauge["area_mm2"] * machine.turns / (w.coil_area_mm2 * w.fill_factor)
    return [f"| Wire | AWG {gauge['awg']}, {gauge['diameter_mm']:.3f} mm bare copper; copper fill "
            f"{w.fill_factor * share:.2f} of the coil section (target {w.fill_factor:g}) |"]


def rated_turns(spec, values, level):
    """Number of turns as the optimizer chooses it, from the field solution at rated load."""
    machine = design.machine_of(spec)
    d = machine.derive(spec, values)
    f = d["electrical_frequency_Hz"]
    stator, rotor = losses.loss_at(level, f, spec["materials"])
    heat = evaluate.temperatures(spec, machine, values, d, float(stator), float(rotor))
    return winding_model.turns_for(machine.winding(spec, values), spec["materials"]["copper"], spec["limits"],
                                   np.asarray(level["flux_per_turn_Wb"]), f, d["ampere_turns_peak"],
                                   heat["winding_C"], spec["winding"]["strip_min_thickness_mm"])


def draw(path, machine, result, info, title):
    g, env = result["grid"], result["envelope"]
    speeds, torques = result["speeds_rpm"], result["torques_Nm"]
    chart = svgplot.Chart((0.0, float(speeds[-1])), (0.0, float(torques[-1]) * 1.03), "Speed (rpm)", "Torque (Nm)",
                          title, width=760, height=470, margin=(64, 210, 44, 52))
    ds = (speeds[1] - speeds[0]) / 2 if len(speeds) > 1 else 1.0
    dt = (torques[1] - torques[0]) / 2 if len(torques) > 1 else 1.0
    used = set()
    for i, speed in enumerate(speeds):
        for j, t in enumerate(torques):
            if not g["within_drive_limits"][i, j] or g["output_power_W"][i, j] <= 0:
                continue
            band = min(int(np.searchsorted(BANDS, g["efficiency"][i, j], side="right")) - 1, len(BAND_COLORS) - 1)
            used.add(band)
            chart.cell(max(speed - ds, 0.0), speed + ds, max(t - dt, 0.0), t + dt, BAND_COLORS[band])
    for band in sorted(used, reverse=True):
        chart.band(BAND_COLORS[band], f"efficiency {100 * BANDS[band]:g} to {100 * BANDS[band + 1]:g} %")
    chart.line(env["speed_rpm"], env["drive_torque_Nm"], "#000000", "drive limit (voltage, current)", dash="6,4")
    chart.line(env["speed_rpm"], env["continuous_torque_Nm"], "#d62728", "continuous limit (temperature)", width=2.2)
    rated = info["rated"]
    chart.marker(rated["speed_rpm"], rated["torque_Nm"], "#000000", "optimizer operating point")
    if "best" in info:
        chart.marker(info["best"]["speed_rpm"], info["best"]["torque_Nm"], "#ffffff", "highest efficiency")
    svgplot.save(path, [chart])


def write_summary(path, spec, machine, result, info, levels, table, notes, dry_run):
    lim, m = spec["limits"], spec["machine"]
    rated = info["rated"]
    out = ["# Torque, speed and efficiency map", ""]
    if dry_run:
        out += ["**Dry run.** The field solver was replaced by a crude analytic estimate. "
                "The numbers test the workflow only.", ""]
    out += ["![Efficiency map](efficiency_map.svg)", "",
            "## Machine", "",
            "| Quantity | Value |", "|---|---|",
            f"| Configuration | {describe.summary(spec)} |",
            f"| Winding | {describe.winding_text(spec, machine.values)} |",
            f"| Pole pairs | {machine.pole_pairs} |",
            f"| Turns per phase coil | {machine.turns} |",
            *wire_rows(spec, machine),
            f"| Bus voltage limit | {lim['bus_voltage_V'][1]:g} V |",
            f"| Current cut-off (peak) | {lim['max_current_A']:g} A |",
            f"| Winding, magnet temperature limits | {lim['max_winding_temp_C']:g} C, {lim['max_magnet_temp_C']:g} C |",
            f"| Fidelity | {spec['fidelity']['level']}, {machine.samples} rotor positions per half period |", "",
            "## Key numbers", "",
            "| Quantity | Value |", "|---|---|",
            f"| Optimizer operating point | {rated['speed_rpm']:.0f} rpm, {rated['torque_Nm']:.3f} Nm, "
            f"{rated['output_power_W']:.1f} W, efficiency {100 * rated['efficiency']:.1f} %, "
            f"loss {rated['loss_W']:.2f} W, {rated['peak_current_A']:.2f} A peak, {rated['bus_voltage_needed_V']:.1f} V |"]
    if "best" in info:
        b = info["best"]
        out.append(f"| Highest efficiency | {100 * b['efficiency']:.1f} % at {b['speed_rpm']:.0f} rpm and "
                   f"{b['torque_Nm']:.3f} Nm ({b['output_power_W']:.1f} W) |")
    out += [f"| Continuous torque at standstill | {info['standstill_continuous_torque_Nm']:.3f} Nm |",
            f"| Peak torque at standstill (short time) | {info['standstill_peak_torque_Nm']:.3f} Nm |",
            f"| Corner speed (peak torque available up to) | {info['corner_speed_rpm']:.0f} rpm |",
            f"| No-load speed at {lim['bus_voltage_V'][1]:g} V | {info['no_load_speed_rpm']:.0f} rpm |",
            f"| Highest continuous output power | {info['max_continuous_power']['output_power_W']:.1f} W at "
            f"{info['max_continuous_power']['speed_rpm']:.0f} rpm and {info['max_continuous_power']['torque_Nm']:.3f} Nm |",
            f"| Highest short-time output power | {info['max_drive_power']['output_power_W']:.1f} W at "
            f"{info['max_drive_power']['speed_rpm']:.0f} rpm and {info['max_drive_power']['torque_Nm']:.3f} Nm |", ""]
    out += [f"- {note}" for note in notes] + [""]

    # Efficiency at a coarse grid, for reading without the picture.
    g = result["grid"]
    speeds, torques = result["speeds_rpm"], result["torques_Nm"]
    si = [int(round(k)) for k in np.linspace(len(speeds) / 6, len(speeds) - 1, 6)]
    ti = [int(round(k)) for k in np.linspace(len(torques) / 6, len(torques) - 1, 6)]
    out += ["## Efficiency in percent", "",
            "Rows: torque. Columns: speed. `s` marks short-time operation (beyond the continuous limit), "
            "`-` is outside the drive limits.", "",
            "| Torque (Nm) | " + " | ".join(f"{speeds[i]:.0f} rpm" for i in si) + " |",
            "|---|" + "---|" * len(si)]
    for j in reversed(ti):
        cells = []
        for i in si:
            if not g["within_drive_limits"][i, j]:
                cells.append("-")
            else:
                cells.append(f"{100 * g['efficiency'][i, j]:.1f}" + ("" if g["continuous"][i, j] else " s"))
        out.append(f"| {torques[j]:.3f} | " + " | ".join(cells) + " |")
    out += ["", "## Load levels (field solutions)", "",
            "| Ampere-turns (peak) | Phase current (A peak) | Torque (Nm) | Torque per 1000 A-turns (Nm) | "
            "Torque peak to peak (Nm) | Core flux density, 95 % of volume (T) |", "|---|---|---|---|---|---|"]
    for row in table:
        per = "n/a" if row["torque_per_kAt"] is None else f"{row['torque_per_kAt']:.3f}"
        b = "n/a" if row["core_b_p95_T"] is None else f"{row['core_b_p95_T']:.2f}"
        out.append(f"| {row['ampere_turns_peak']:.1f} | {row['peak_current_A']:.2f} | {row['torque_Nm']:.4f} | {per} | "
                   f"{row['peak_to_peak_Nm']:.4f} | {b} |")
    out += ["", "## Assumptions", "",
            "- Sinusoidal current in phase with the induced voltage. Field weakening is not modelled, so the "
            "real drive can reach somewhat higher speeds than the map shows.",
            "- Losses are copper loss, stator core loss (alternating and rotational, per harmonic of the flux "
            "density) and eddy-current loss in the rotor iron, housing and magnets (thin-plate estimate, no "
            "skin effect). Bearing, windage and inverter losses are not included, so real efficiency is lower. "
            "Validation against two SMC prototypes: ticket T31.",
            "- Inside the continuous limit the copper loss is taken at the steady-state winding temperature of "
            "the thermal network. Beyond it the winding is taken at its temperature limit.",
            "- The continuous limit is where the winding or magnet temperature limit or the current-density "
            "limit is reached. The thermal network uses assumed heat-transfer coefficients.",
            "- Between the load levels all quantities are interpolated in ampere-turns.",
            "- Phases are treated as magnetically independent.", ""]
    with open(path, "w") as f:
        f.write("\n".join(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    picks.add_arguments(ap)
    ap.add_argument("--levels", type=int, default=6, help="load levels between zero and the highest load (default 6)")
    ap.add_argument("--overload", type=float, default=2.0,
                    help="highest load as a multiple of the current-density limit (default 2); "
                         "the current cut-off applies as well")
    ap.add_argument("--turns", type=int, help="turns per phase coil (default: as chosen by the optimizer)")
    ap.add_argument("--max-speed", type=float, help="highest speed in rpm (default: 1.1 x no-load speed)")
    ap.add_argument("--speeds", type=int, default=61, help="speed steps of the grid")
    ap.add_argument("--torques", type=int, default=61, help="torque steps of the grid")
    ap.add_argument("--dry-run", action="store_true", help="use the analytic estimate instead of the field solver")
    args = ap.parse_args(argv)
    try:
        spec, values, parameters, outdir = picks.load(args, "map")
    except (picks.PickError, ValueError) as error:
        sys.exit(str(error))
    os.makedirs(outdir, exist_ok=True)
    began = time.time()
    analyse = evaluate.analytic_stand_in if args.dry_run else None
    d = design.derived(spec, values)
    rated = d["ampere_turns_peak"]
    notes = []

    turns = args.turns or picks.turns_of(parameters)
    if turns is None:
        levels, _ = effmap.solve_levels(spec, values, [rated], outdir, analyse)
        chosen = rated_turns(spec, values, levels[0])
        turns = chosen["turns"]
        speed = spec["operating_point"]["speed_rpm"]
        if chosen["turns_max"] >= chosen["turns_min"]:
            notes.append(f"The number of turns ({turns}) was chosen as the optimizer does: the most turns that the "
                         f"bus voltage allows at {speed:g} rpm.")
        else:
            notes.append(f"No number of turns meets both drive limits at {speed:g} rpm and the rated load: the current "
                         f"cut-off needs at least {chosen['turns_min']} turns, the bus voltage allows at most "
                         f"{chosen['turns_max']}. The map uses {turns} (the fewest the current allows), so the rated "
                         f"point lies beyond the bus voltage; --turns sets another number.")
    elif args.turns:
        notes.append(f"The number of turns was set to {turns} on the command line.")
    ceiling, by_cutoff = effmap.ampere_turn_ceiling(spec, values, turns, args.overload)
    notes.append(f"The highest load of the map is {ceiling:.0f} ampere-turns ({ceiling / turns:.2f} A peak): "
                 + ("the current cut-off." if by_cutoff else
                    f"{args.overload:g} times the current-density limit. The current cut-off of "
                    f"{spec['limits']['max_current_A']:g} A is not reached."))
    wanted = effmap.choose_levels(rated, ceiling, args.levels)
    print(f"{turns} turns, {len(wanted)} load levels up to {ceiling:.0f} ampere-turns "
          f"({ceiling / turns:.2f} A peak){', dry run' if args.dry_run else ''}", flush=True)
    levels, solved = effmap.solve_levels(spec, values, wanted, outdir, analyse)
    print(f"{solved} load levels solved, {len(levels) - solved} reused", flush=True)

    machine = effmap.Machine(spec, values, levels, turns)
    top = args.max_speed or 1.1 * machine.no_load_speed()
    result = effmap.compute(machine, np.linspace(0.0, top, max(args.speeds, 2)), max(args.torques, 2))
    rated_speed = spec["operating_point"]["speed_rpm"]
    info = effmap.summary(machine, result, rated_speed, min(rated, ceiling))
    table = effmap.level_table(machine, levels)

    g = result["grid"]
    write_csv(os.path.join(outdir, "efficiency_map.csv"), COLUMNS,
              ([g[c][i, j] for c in COLUMNS] for i in range(g["efficiency"].shape[0])
               for j in range(g["efficiency"].shape[1])))
    env = result["envelope"]
    names = ["speed_rpm", "drive_torque_Nm", "continuous_torque_Nm", "drive_ampere_turns", "continuous_ampere_turns"]
    write_csv(os.path.join(outdir, "envelope.csv"), names, zip(*(env[n] for n in names)))
    paraviewfiles.efficiency_map(outdir)
    names = ["ampere_turns_peak", "peak_current_A", "torque_Nm", "torque_per_kAt", "ripple", "peak_to_peak_Nm",
             *losses.COEFFICIENTS, "rotor_loss_W_at_rated_speed", "core_b_p95_T"]
    write_csv(os.path.join(outdir, "load_levels.csv"), names, ([row[n] for n in names] for row in table))
    with open(os.path.join(outdir, "summary.json"), "w") as f:
        json.dump({"turns": turns, "ampere_turn_ceiling": ceiling, **info}, f, indent=2)
    title = f"Efficiency map: {machine.turns} turns, {spec['limits']['bus_voltage_V'][1]:g} V bus"
    draw(os.path.join(outdir, "efficiency_map.svg"), machine, result, info, title)
    write_summary(os.path.join(outdir, "map.md"), spec, machine, result, info, levels, table, notes, args.dry_run)

    r = info["rated"]
    print(f"Operating point of the optimizer: {r['speed_rpm']:.0f} rpm, {r['torque_Nm']:.3f} Nm, "
          f"efficiency {100 * r['efficiency']:.1f} %, loss {r['loss_W']:.2f} W")
    if "best" in info:
        b = info["best"]
        print(f"Highest efficiency: {100 * b['efficiency']:.1f} % at {b['speed_rpm']:.0f} rpm, {b['torque_Nm']:.3f} Nm")
    print(f"Continuous torque at standstill {info['standstill_continuous_torque_Nm']:.3f} Nm, peak "
          f"{info['standstill_peak_torque_Nm']:.3f} Nm, corner speed {info['corner_speed_rpm']:.0f} rpm, "
          f"no-load speed {info['no_load_speed_rpm']:.0f} rpm")
    print(f"Map -> {os.path.join(outdir, 'map.md')}   ({time.time() - began:.0f} s)")

