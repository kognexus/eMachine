"""
Multi-objective optimization of an electric machine (any machine of `emachine list`
that can be solved; the spec section "machine" names flux path, principle and rotor layout).

    emachine optimize --spec examples/tfm_single_phase.json --run runs/opt1
    emachine optimize --spec examples/rfm_spm_12s10p.json --run runs/rfm1

Reads the specification (macro inputs, limits, objectives), searches the design space with the
optimizer of the spec ("optimizer": {"algorithm": "nsga2"} by default) and writes to the run folder:

    pareto.csv        the trade-off designs (no design is better in every objective)
    all_designs.csv   every design that was evaluated
    report.md         summary, trade-off table and three picks
    designs/*.json    parameter file of each pick, for emachine solve, emachine map, emachine export
    designs/*.onshape.md  the same pick under the field names of the two Onshape features
    state.json        optimizer state; re-running the same command continues from it
    spec.json         the complete specification of the run, defaults included

--seed-from starts from known designs instead of random ones: run folders (their pareto.csv),
.csv tables or design .json files. On an existing run it adds the designs to the population.

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

from emachine.core import registry
from emachine.core.types import Objective, Problem, Variable
from emachine.cli import describe
from emachine.optimization import nsga2, pareto
from emachine.pipeline import design_space as design
from emachine.pipeline import evaluate, seeding
from emachine.spec import load_spec

from emachine.machines.tfm.cad import sheet as onshape


def _is_tfm(spec):
    """Onshape sheets and the axial phase width exist for transverse flux machines only."""
    return spec["machine"]["flux_path"] == "tfm"


def _phase_width(spec):
    from emachine.machines.tfm.design import phase_width
    return phase_width(spec) if _is_tfm(spec) else float("nan")

OBJECTIVE_LABELS = {"max_torque": "torque", "min_losses": "losses", "min_ripple": "ripple",
                    "max_efficiency": "efficiency"}


def feasible_start(spec, variables, count, seed):
    """Random designs that pass the geometry checks, so the first generation is not wasted."""
    rng = np.random.default_rng(seed + 7919)
    out = []
    for _ in range(400 * count):
        x = nsga2.random_design(variables, rng)
        if design.is_feasible(design.checks(spec, design.to_values(spec, x))):
            out.append(x)
            if len(out) == count:
                break
    return out


def single_phase_warning(spec):
    """Text when the ripple limit cannot be met because the machine has one phase, else None."""
    limit = spec["limits"]["max_torque_ripple_percent"]
    if spec["machine"]["phases"] == 1 and limit is not None and limit < 150.0:
        return (f"One phase: the torque of a single phase pulsates between about zero and twice its mean, a ripple "
                f"of about 200 % before cogging. The limit of {limit:g} % needs three phases "
                f"(machine.phases = 3), or switch the limit off (limits.max_torque_ripple_percent = null).")
    return None


def flat_row(spec, record):
    """One table row for a design record."""
    row = dict(record["values"])
    row["analysed"] = record["analysed"]
    row["feasible"] = record["violation"] == 0
    row["violation"] = record["violation"]
    row["reason"] = record.get("reason") or ""
    if record["violated_checks"]:
        row["reason"] = "geometry: " + ", ".join(c["name"] for c in record["violated_checks"])
    elif record["analysed"] and record["violation"] > 0:
        row["reason"] = "limits: " + ", ".join(k for k, v in record["constraints"].items() if v > 0)
    if record["analysed"]:
        row.update({
            "torque_Nm": record["objectives"]["torque_Nm"],
            "loss_W": record["objectives"]["loss_W"],
            "ripple": record["objectives"]["ripple"],
            "ripple_percent": 100.0 * record["objectives"]["ripple"],
            "efficiency": record["efficiency"],
            "output_power_W": record["output_power_W"],
            "turns": record["winding"]["turns"],
            "peak_current_A": record["winding"]["peak_current_A"],
            "bus_voltage_needed_V": record["winding"]["required_bus_voltage_V"],
            "copper_W_per_phase": record["losses"]["copper_W_per_phase"],
            "iron_W_per_phase": record["losses"]["iron_W_per_phase"],
            "rotor_W_per_phase": record["losses"].get("rotor_W_per_phase", 0.0),
            "winding_C": record["thermal"]["winding_C"],
            "magnet_C": record["thermal"]["magnet_C"],
            "core_b_p95_T": record["losses"].get("core_b_p95_T"),
            "slot_width_mm": record["geometry"].get("slot_width"),
            "core_thickness_mm": record["geometry"].get("core_thickness"),
            "rotor_iron_mm_actual": record["geometry"].get("rotor_iron"),
            "stator_radius_mm": record["geometry"].get("stator_radius"),
            "inner_diameter_mm": record["geometry"].get("inner_diameter"),
            "positions": record["analysis"]["positions"],
            "stopped_early": bool(record["analysis"].get("stopped_early")),
            "interpolated": bool(record["analysis"].get("interpolated")),
        })
    return row


def write_table(path, rows, columns):
    with open(path, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(columns)
        for row in rows:
            cells = []
            for c in columns:
                v = row.get(c, "")
                cells.append("" if v is None else (f"{v:.6g}" if isinstance(v, float) else v))
            out.writerow(cells)


def choose_picks(front):
    """Highest torque, lowest loss and the design closest to the ideal corner of the trade-off."""
    if not front:
        return {}
    picks = {
        "highest_torque": max(front, key=lambda r: r["objectives"]["torque_Nm"]),
        "lowest_loss": min(front, key=lambda r: r["objectives"]["loss_W"]),
    }
    if any("efficiency" in r["objectives"] for r in front):
        picks["highest_efficiency"] = max(front, key=lambda r: r["objectives"].get("efficiency", 0.0))
    f = np.array([r["f"] for r in front], dtype=float)
    low, span = f.min(axis=0), np.maximum(f.max(axis=0) - f.min(axis=0), 1e-12)
    picks["best_compromise"] = front[int(np.argmin(np.linalg.norm((f - low) / span, axis=1)))]
    return picks


def pick_parameters(spec, record):
    """Parameter file of a pick at fine fidelity, with the chosen turns and peak current."""
    params = design.parameters(spec, record["values"], level="fine")
    params["analysis"].update({
        "coil_turns": record["winding"]["turns"],
        "coil_current_A": record["winding"]["peak_current_A"],
        "positions": 2 * int(spec["fidelity"]["positions"]),
    })
    params["machine"] = dict(spec["machine"])
    w = record["winding"]
    params["summary"] = {
        "speed_rpm": spec["operating_point"]["speed_rpm"],
        "torque_Nm": record["objectives"]["torque_Nm"],
        "loss_W": record["objectives"]["loss_W"],
        "ripple": record["objectives"]["ripple"],
        "efficiency": record["efficiency"],
        "turns": w["turns"],
        "wire_area_mm2": w["wire_area_mm2"],
        "peak_current_A": w["peak_current_A"],
        "rms_current_A": w["rms_current_A"],
        "resistance_ohm": w["resistance_ohm"],
        "required_bus_voltage_V": w["required_bus_voltage_V"],
        "ampere_turns_peak": record["ampere_turns_peak"],
        "winding_C": record["thermal"]["winding_C"],
        "magnet_C": record["thermal"]["magnet_C"],
        "conductor": w.get("conductor", "round_wire"),
    }
    if "strip_thickness_mm" in w:
        params["summary"].update({"strip_width_mm": w["strip_width_mm"], "strip_thickness_mm": w["strip_thickness_mm"]})
    return params


def conductor_text(spec):
    w = spec["winding"]
    turns = "chosen per design" if w["turns"] is None else f"{w['turns']} per phase"
    if w["conductor"] == "strip":
        return (f"stacked flat copper rings (strip), copper fill {w['strip_fill_factor']:g}, "
                f"strip at least {w['strip_min_thickness_mm']:g} mm thick, layers {turns}")
    return f"round wire, copper fill {w['fill_factor']:g}, turns {turns}"


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}g}"


def write_report(path, spec, state, rows_all, front, picks, dry_run, seconds, seed_notes=(), positions_solved=0):
    m, lim, op = spec["machine"], spec["limits"], spec["operating_point"]
    variables = design.variables(spec)
    analysed = sum(r["analysed"] for r in rows_all)
    feasible = sum(r["feasible"] for r in rows_all)
    out = ["# Optimization report", ""]
    if dry_run:
        out += ["**Dry run.** The field solver was replaced by a crude analytic estimate. "
                "The numbers below test the workflow only and must not be used for design.", ""]
    out += ["## Problem", "",
            "| Input | Value |", "|---|---|",
            f"| Machine | {describe.label(spec)}, {m['rotor_placement']} rotor |",
            *[f"| {label} | {fmt(value) if isinstance(value, float) else value} |"
              for label, value in describe.option_rows(spec)],
            f"| Outer diameter | {fmt(float(m['outer_diameter_mm']))} mm |",
            f"| Bore diameter | {fmt(float(m['bore_diameter_mm']))} mm |",
            f"| Stack length, all phases | {fmt(float(m['stack_length_mm']))} mm |",
            f"| Phases | {m['phases']} |",
            *([f"| Axial width of one phase | {fmt(_phase_width(spec), 4)} mm |"] if _is_tfm(spec) else []),
            f"| Air gap | {fmt(float(m['air_gap_mm']))} mm |",
            f"| Coil | {conductor_text(spec)} |",
            f"| Speed | {fmt(float(op['speed_rpm']))} rpm |",
            f"| Objectives | {', '.join(OBJECTIVE_LABELS[o] for o in spec['objectives'])} |", "",
            "## Limits applied", "",
            "| Limit | Value |", "|---|---|",
            f"| Iron thickness | {lim['iron_thickness_mm'][0]} to {lim['iron_thickness_mm'][1]} mm |",
            f"| Pole pairs | {lim['pole_pairs'][0]} to {lim['pole_pairs'][1]} |",
            f"| Bus voltage | {lim['bus_voltage_V'][0]} to {lim['bus_voltage_V'][1]} V |",
            f"| Peak phase current | {lim['max_current_A']} A |",
            f"| Winding temperature | {lim['max_winding_temp_C']} C |",
            f"| Magnet temperature | {lim['max_magnet_temp_C']} C |",
            f"| Current density (RMS) | {lim['max_current_density_A_mm2']} A/mm2 |",
            f"| Torque ripple, (highest - lowest) / mean | "
            f"{'no limit' if lim['max_torque_ripple_percent'] is None else format(lim['max_torque_ripple_percent'], 'g') + ' %'} |",
            f"| Core flux density on 95 % of the core | "
            f"{'no limit' if lim['max_core_flux_density_T'] is None else str(lim['max_core_flux_density_T']) + ' T'} |",
            f"| Stator core material | "
            f"{'linear' if spec['materials']['stator_core']['saturation_T'] is None and spec['materials']['stator_core']['bh_curve'] is None else 'saturating (B-H curve)'} |", "",
            "## Design variables", "",
            "| Variable | Range |", "|---|---|"]
    out += [f"| {v['name']} | {fmt(v['low'])} to {fmt(v['high'])} |" for v in variables]
    out += ["", "## Run", "",
            f"- Generations: {state['generation']}, population {len(state['population'])}.",
            f"- Designs evaluated: {len(rows_all)}. Analysed with the field model: {analysed}. "
            f"Rejected by the geometry checks: {len(rows_all) - analysed}.",
            f"- Designs meeting every limit: {feasible}.",
            f"- Trade-off designs: {len(front)}.",
            f"- Time for this invocation: {seconds / 60:.1f} min.", ""]
    fid = spec["fidelity"]
    stopped = sum(1 for r in rows_all if r.get("stopped_early"))
    out += [f"- Rotor positions per design: {fid['positions']}"
            + (", in two stages: designs outside the limits after the first half are not refined."
               if evaluate.staging(spec) else ", solved in one stage.")]
    if evaluate.staging(spec):
        out += [f"- Designs stopped after the first stage: {stopped} of {analysed} analysed. "
                f"Their ripple is a lower bound."]
    if fid["load_levels"]:
        out += [f"- Each geometry is solved at {fid['load_levels']} current densities; other current densities "
                f"are interpolated. Designs obtained without a field solution: {state.get('free_designs', 0)}. "
                f"Interpolated designs should be re-checked with `emachine map`, which solves the rated point directly."]
    if positions_solved:
        out += [f"- Rotor positions solved in this invocation: {positions_solved}."]
    out += [""]
    if seed_notes:
        out += ["Started from known designs:", ""] + [f"- {note}" for note in seed_notes] + [""]
    if single_phase_warning(spec):
        out += [f"**{single_phase_warning(spec)}**", ""]
    rejected = sum(1 for r in rows_all if r["analysed"] and lim["max_torque_ripple_percent"] is not None
                   and r["ripple_percent"] > lim["max_torque_ripple_percent"])
    if lim["max_torque_ripple_percent"] is not None:
        out += [f"Analysed designs above the torque ripple limit: {rejected} of {analysed}.", ""]
    if not front:
        out += ["No design met every limit. Widen the limits or run more generations.", ""]
    else:
        out += ["## Trade-off designs", "",
                "Sorted by torque. No design in this table is better than another in every objective.", "",
                "| Torque (Nm) | Loss (W) | Ripple (%) | Efficiency | Pole pairs | Turns | Peak current (A) | Bus voltage (V) | Winding (C) |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(front, key=lambda r: -r["objectives"]["torque_Nm"]):
            out.append(f"| {fmt(r['objectives']['torque_Nm'])} | {fmt(r['objectives']['loss_W'])} | "
                       f"{100 * r['objectives']['ripple']:.1f} | {100 * r['efficiency']:.1f} % | {r['values']['pole_pairs']} | "
                       f"{r['winding']['turns']} | {fmt(r['winding']['peak_current_A'])} | "
                       f"{fmt(r['winding']['required_bus_voltage_V'])} | {fmt(r['thermal']['winding_C'])} |")
        out += ["", "## Picks", ""]
        for name, r in picks.items():
            out += [f"### {name.replace('_', ' ').capitalize()}", "",
                    f"Parameter file: `designs/{name}.json`", "",
                    "| Quantity | Value |", "|---|---|",
                    f"| Mean torque | {fmt(r['objectives']['torque_Nm'])} Nm |",
                    f"| Total loss | {fmt(r['objectives']['loss_W'])} W "
                    f"(copper {fmt(r['losses']['copper_W_per_phase'])} W, iron {fmt(r['losses']['iron_W_per_phase'])} W, "
                    f"rotor {fmt(r['losses'].get('rotor_W_per_phase', 0.0))} W per phase) |",
                    f"| Torque ripple | {100 * r['objectives']['ripple']:.1f} % |",
                    f"| Output power, efficiency | {fmt(r['output_power_W'])} W, {100 * r['efficiency']:.1f} % |",
                    f"| {'Layers' if r['winding'].get('conductor') == 'strip' else 'Turns'}, peak current | "
                    f"{r['winding']['turns']}, {fmt(r['winding']['peak_current_A'])} A |",
                    f"| Winding | {describe.winding_text(spec, r['values'])} |",
                    *([f"| Wire | AWG {r['winding']['awg']} ({fmt(r['winding']['wire_diameter_mm'], 3)} mm bare copper; "
                       f"{100 * r['winding']['awg_fill_share']:.0f} % of the copper area the fill factor allows) |"]
                      if r['winding'].get('awg') is not None and r['winding'].get('conductor') != 'strip' else []),
                    f"| Phase resistance | {onshape.resistance_text(r['winding']['resistance_ohm'])} |",
                    f"| Field solution | {'interpolated between load levels' if r['analysis'].get('interpolated') else 'direct'}, "
                    f"{r['analysis']['positions']} rotor positions |",
                    f"| Bus voltage needed | {fmt(r['winding']['required_bus_voltage_V'])} V |",
                    f"| Winding, magnet temperature | {fmt(r['thermal']['winding_C'])} C, {fmt(r['thermal']['magnet_C'])} C |"]
            out += [f"| {k} | {fmt(v, 4)} |" for k, v in r["values"].items()]
            out.append("")
        if _is_tfm(spec):
            out += ["## Onshape parameters", "",
                    "Values to type into the two Onshape features, under the field names of their dialogs. "
                    "The same tables are in `designs/<pick>.onshape.md`.", ""]
            for name, r in picks.items():
                sections = onshape.sheet(pick_parameters(spec, r))
                out += [onshape.to_markdown(sections, name.replace("_", " ").capitalize(), level=3)]
    out += ["## Model limits", "",
            "- Saturation is modelled with a B-H curve built from two numbers (initial permeability and "
            "saturation polarisation) unless a measured curve is given. Use the curve of the real material.",
            "- Torque ripple at the optimization fidelity is good for ranking, not for absolute values. "
            "Re-analyse picks at fine fidelity.",
            "- Losses cover copper, stator core (alternating and rotational) and rotor eddy currents (T31). "
            "Mechanical and inverter losses are not included.",
            "- The thermal model is a simplified network with assumed heat-transfer coefficients.",
            "- Phases are treated as magnetically independent.", "",
            "## Re-analyse a pick", "",
            "```bash", "emachine solve --params <run folder>/designs/best_compromise.json --run runs/check",
            "```", ""]
    with open(path, "w") as f:
        f.write("\n".join(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="specification file (see examples/tfm_single_phase.json)")
    ap.add_argument("--run", required=True, help="run folder; an existing run is continued")
    ap.add_argument("--dry-run", action="store_true", help="use the analytic estimate instead of the field solver")
    ap.add_argument("--population", type=int, help="override optimizer.population")
    ap.add_argument("--generations", type=int, help="override optimizer.generations")
    ap.add_argument("--seed", type=int, help="override optimizer.seed (random number seed)")
    ap.add_argument("--seed-from", nargs="+", default=[], metavar="PATH",
                    help="start from the designs of run folders, .csv tables or design .json files")
    ap.add_argument("--max-seeds", type=int, help="largest number of seed designs to evaluate "
                                                  "(default: twice the population)")
    args = ap.parse_args(argv)

    spec = load_spec(args.spec)
    for key in ("population", "generations", "seed"):
        if getattr(args, key) is not None:
            spec["optimizer"][key] = getattr(args, key)
    opt = spec["optimizer"]
    rundir = os.path.abspath(args.run)
    os.makedirs(os.path.join(rundir, "designs"), exist_ok=True)
    variables = design.variables(spec)
    began = time.time()

    def log(record):
        if record["analysed"]:
            o = record["objectives"]
            broken = [name.replace("_", " ") for name, value in record.get("constraints", {}).items() if value > 0]
            status = "ok" if record["violation"] == 0 else "violates: " + ", ".join(broken)
            a = record["analysis"]
            note = (" (cached)" if record["cache_hit"] else
                    " (field solution reused)" if a.get("field_solution_reused") else "")
            if a.get("stopped_early"):
                note += f", stopped after {a['positions']} of {spec['fidelity']['positions']} positions"
            print(f"  design: torque {o['torque_Nm']:.3f} Nm, loss {o['loss_W']:.2f} W, ripple "
                  f"{'at least ' if a.get('stopped_early') else ''}{100 * o['ripple']:.0f} %, "
                  f"{record['seconds']:.0f} s{note}, {status}", flush=True)
        elif record["failed"]:
            print(f"  design: {record['reason']}", flush=True)

    def progress(state):
        h = state["history"][-1]
        print(f"generation {h['generation']}: {h['evaluations']} designs evaluated, {h['feasible']} of "
              f"{len(state['population'])} in the population meet every limit, {h['front_size']} trade-off designs "
              f"({(time.time() - began) / 60:.1f} min)", flush=True)

    analyse = evaluate.analytic_stand_in if args.dry_run else None
    evaluator = evaluate.BatchEvaluator(spec, rundir, analyse, log)
    state_file = os.path.join(rundir, "state.json")
    resumed = os.path.isfile(state_file)
    with open(os.path.join(rundir, "spec.json"), "w") as f:
        json.dump(spec, f, indent=2)

    seeds, seed_notes = [], []
    if args.seed_from:
        try:
            seeds, summary = seeding.collect(spec, args.seed_from, args.max_seeds or 2 * opt["population"])
        except seeding.SeedError as error:
            sys.exit(f"Seed designs: {error}")
        cached = seeding.copy_cached(spec, seeds, rundir, evaluate.analytic_stand_in if args.dry_run else None)
        seed_notes = seeding.describe(summary) + [f"{len(seeds)} seed designs in total, "
                                                  f"{cached} with results already in the cache."]
        for line in seed_notes:
            print("seeds: " + line, flush=True)
        if not seeds:
            print("seeds: no usable design in the sources; starting from random designs.", flush=True)
    seed_file = os.path.join(rundir, "seeds.json")
    history = []
    if resumed and os.path.isfile(seed_file):
        with open(seed_file) as f:
            history = json.load(f)
    if seeds:
        history.append({"generation": "start" if not resumed else "resume", "notes": seed_notes,
                        "designs": [s["values"] for s in seeds]})
        with open(seed_file, "w") as f:
            json.dump(history, f, indent=2)

    seed_vectors = [design.to_vector(spec, s["values"]) for s in seeds]
    initial = inject = None
    if resumed:
        inject = seed_vectors or None
    else:
        fill = max(0, opt["population"] - len(seed_vectors))
        initial = seed_vectors + (feasible_start(spec, variables, fill, opt["seed"]) if fill else [])
    print(f"{len(variables)} design variables, population {opt['population']}, {opt['generations']} generations"
          f"{', dry run' if args.dry_run else ''}", flush=True)
    if single_phase_warning(spec):
        print("WARNING: " + single_phase_warning(spec), flush=True)
    optimizer = registry.create("optimizer", opt["algorithm"])
    problem = Problem(variables=tuple(Variable(v["name"], v["low"], v["high"], v["kind"]) for v in variables),
                      objectives=tuple(Objective(name) for name in spec["objectives"]))
    state = optimizer.run(problem, evaluator, {"population": opt["population"], "generations": opt["generations"],
                                               "seed": opt["seed"]},
                          state_file=state_file, initial=initial, on_generation=progress, inject=inject)

    # Records of every evaluated design. Designs from an earlier invocation come from the cache.
    records = {}
    for key, individual in state["archive"].items():
        record = evaluator.records.get(key)
        if record is None:
            if individual["violation"] >= evaluate.FAILED_PENALTY and not math.isfinite(individual["f"][0]):
                record = {"values": design.to_values(spec, individual["x"]), "analysed": False, "failed": True,
                          "reason": "analysis failed in an earlier run", "violated_checks": [],
                          "f": individual["f"], "violation": individual["violation"]}
            else:
                record = evaluate.evaluate(spec, design.to_values(spec, individual["x"]), rundir, analyse)
        records[key] = record

    front = [records[pareto.key_of(p["x"])] for p in pareto.pareto_front(state["population"])]
    front = [r for r in front if r["analysed"]]
    picks = choose_picks(front)
    rows_all = [flat_row(spec, r) for r in records.values()]
    rows_front = [flat_row(spec, r) for r in sorted(front, key=lambda r: -r["objectives"]["torque_Nm"])]
    names = [v["name"] for v in variables]
    results = ["torque_Nm", "loss_W", "ripple", "ripple_percent", "efficiency", "output_power_W", "turns", "peak_current_A",
               "bus_voltage_needed_V", "copper_W_per_phase", "iron_W_per_phase", "rotor_W_per_phase", "winding_C", "magnet_C",
               "core_b_p95_T", "slot_width_mm", "core_thickness_mm", "rotor_iron_mm_actual", "stator_radius_mm",
               "inner_diameter_mm", "positions", "stopped_early", "interpolated"]
    write_table(os.path.join(rundir, "pareto.csv"), rows_front, names + results)
    write_table(os.path.join(rundir, "all_designs.csv"), rows_all,
                names + ["analysed", "feasible", "violation", "reason"] + results)
    for name, record in picks.items():
        parameters = pick_parameters(spec, record)
        with open(os.path.join(rundir, "designs", name + ".json"), "w") as f:
            json.dump(parameters, f, indent=2)
        if _is_tfm(spec):
            with open(os.path.join(rundir, "designs", name + ".onshape.md"), "w") as f:
                f.write(onshape.to_markdown(onshape.sheet(parameters), f"Onshape parameters: {name.replace('_', ' ')}"))
    write_report(os.path.join(rundir, "report.md"), spec, state, rows_all, front, picks, args.dry_run,
                 time.time() - began, [note for entry in history for note in entry["notes"]],
                 evaluator.positions_solved)

    if evaluator.positions_solved:
        print(f"{evaluator.positions_solved} rotor positions solved in this invocation.")
    print(f"{len(rows_all)} designs evaluated, {len(front)} trade-off designs. Report -> {os.path.join(rundir, 'report.md')}")
    if "best_compromise" in picks and _is_tfm(spec):
        r = picks["best_compromise"]
        print()
        print(onshape.to_text(onshape.sheet(pick_parameters(spec, r)),
                              f"Best compromise: {r['objectives']['torque_Nm']:.3f} Nm, {r['objectives']['loss_W']:.2f} W, "
                              f"ripple {100 * r['objectives']['ripple']:.1f} %, efficiency {100 * r['efficiency']:.1f} %  "
                              f"(Onshape parameters)"))
        print("\nThe other picks: designs/highest_torque.onshape.md, designs/lowest_loss.onshape.md")
    if not front:
        sys.exit("No design met every limit.")

