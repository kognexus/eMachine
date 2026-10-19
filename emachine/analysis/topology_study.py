"""
Multi-topology study (T63): every topology of the catalogue optimized on the same drive in the same
envelope, its picks verified, and the data the report needs.

    emachine study --config <study folder>/study.json [--only KEY ...] [--verify]

Per topology `<out>/runs/<key>/`: all_designs.jsonl (every evaluated design: variables, dimensions,
results or the reason it was rejected), state.json (NSGA-II, resumable), picks.json, and after
--verify `verify/<pick>.json` (more rotor positions, no-load sweep, cogging, EMF).

Objectives: rated torque (max), peak torque at the peak current (max), torque ripple at the rated
point (min). Constraints: efficiency at the rated point, the line voltage, the winding (fill in
range), current densities, the geometry.
"""

import argparse
import concurrent.futures
import copy
import json
import math
import os
import time
import traceback

from emachine.core import registry
from emachine.core.types import Objective, Problem
from emachine.machines.catalogue import TOPOLOGIES, GeometryError
from emachine.pipeline import drive as drive_eval
from emachine.spec.loader import load_spec

HERE = os.path.dirname(os.path.abspath(__file__))


def register_solvers():
    """Registers the geometry builders and field solvers of the study (also in worker processes)."""
    import emachine.machines.rafm.builder  # noqa: F401
    import emachine.machines.section2d.builder  # noqa: F401
    import emachine.solvers.elmer.quasi3d  # noqa: F401
    import emachine.solvers.elmer.sections  # noqa: F401


def envelope_for(cfg, key):
    """The envelope of a topology: the study's, with the bore of `bore_overrides` where one is given (T69)."""
    env = cfg["envelope"]
    bore = cfg.get("bore_overrides", {}).get(key)
    if bore is None:
        return env
    env = copy.deepcopy(env)
    env["bore_diameter_mm"] = float(bore)
    return env


def load_config(path):
    with open(path) as f:
        cfg = json.load(f)
    cfg["_dir"] = os.path.dirname(os.path.abspath(path))
    return cfg


def material_set(cfg, topology):
    """Materials of a topology: radial (laminations) or axial (SMC stator, steel discs), SRM rotor of SMC."""
    sets = cfg["materials"]
    chosen = copy.deepcopy(sets["axial" if topology.flux_path == "afm" else "radial"])
    if topology.flux_path == "afm" and topology.principle == "srm":
        chosen.update(copy.deepcopy(sets.get("axial_srm", {})))
    chosen.pop("note", None)
    return chosen


def settings_for(cfg, topology, positions=None, no_load=False, fine=False):
    mats = material_set(cfg, topology)
    spec = load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "rotor": "surface", "phases": 3,
                                  "outer_diameter_mm": cfg["envelope"]["outer_diameter_mm"],
                                  "bore_diameter_mm": cfg["envelope"]["bore_diameter_mm"],
                                  "stack_length_mm": cfg["envelope"]["stack_length_mm"]},
                      "materials": mats})
    m = spec["materials"]
    analysis = {"magnet_remanence_T": m["magnet"]["remanence_T"], "magnet_mu_r": m["magnet"]["mu_r"],
                "stator_core_mu_r": m["stator_core"]["mu_r"], "stator_core_saturation_T": m["stator_core"]["saturation_T"],
                "stator_core_bh_curve": m["stator_core"]["bh_curve"], "rotor_iron_mu_r": m["rotor_iron"]["mu_r"],
                "rotor_iron_saturation_T": m["rotor_iron"]["saturation_T"], "rotor_iron_bh_curve": m["rotor_iron"]["bh_curve"],
                "rotor_housing_mu_r": 1.0, "nonlinear_tolerance": 1e-5 if fine else 1e-4, "nonlinear_max_iterations": 40}
    lim = cfg["limits"]
    return {"analysis": analysis, "materials": m, "loss_spec": spec, "fill_range": lim["fill_range"],
            "positions": positions or cfg["optimizer"]["positions"], "min_efficiency": lim["min_efficiency"],
            "iron_loss_guess_W": 5.0, "no_load_sweep": no_load, "srm_positions": 9,
            "max_j_rated_rms_A_mm2": lim["max_j_rated_rms_A_mm2"]}


# ----------------------------------------------------------------------------- one design

def constraints_of(record, cfg):
    lim = cfg["limits"]
    out = {}
    if not record.get("analysed"):
        return out
    w = record["winding"]
    out["efficiency"] = max(0.0, (lim["min_efficiency"] - record["efficiency"]) / 0.05)
    out["voltage"] = record["voltage"]["violation"] * 10
    out["j_rated"] = max(0.0, w["j_rated_rms_A_mm2"] / lim["max_j_rated_rms_A_mm2"] - 1.0)
    out["j_peak"] = max(0.0, w["j_peak_rms_A_mm2"] / lim["max_j_peak_rms_A_mm2"] - 1.0)
    return out


def fine_envelope(env):
    """The envelope with the mesh of the verification (finer air-gap cells)."""
    env = copy.deepcopy(env)
    fid = env.setdefault("fidelity", {})
    fid.update(gap_cell_factor=fid.get("fine_gap_cell_factor", 0.4), axial_gap_cell_factor=fid.get("fine_axial_gap_cell_factor", 0.45),
               axial_gap_cell_min_mm=0.2, size_max_mm=2.0, axial_size_max_mm=2.5, axial_slices=fid.get("fine_axial_slices", 3))
    return env


def evaluate_values(key, values, cfg, workdir, positions=None, no_load=False, keep=False, fine=False):
    """Record of one design (runs in a worker process)."""
    register_solvers()
    topology = TOPOLOGIES[key]()
    record = {"machine": key, "values": values}
    env = fine_envelope(envelope_for(cfg, key)) if fine else envelope_for(cfg, key)
    try:
        design = topology.design(env, values)
    except GeometryError as error:
        record.update(analysed=False, reason="geometry", checks=error.checks, violation=1.0 + error.violation)
        return record
    settings = settings_for(cfg, topology, positions, no_load, fine)
    settings["keep_workdir"] = keep
    began = time.time()
    try:
        result = drive_eval.evaluate(design, cfg["drive"], settings, workdir)
    except Exception as error:          # never let one design stop the run
        result = {"analysed": False, "reason": f"error: {error}", "trace": traceback.format_exc()[-800:]}
    record.update(result)
    record["design"] = {k: design[k] for k in ("dims", "winding", "pe", "coils_per_phase", "side_area_mm2", "turn_length_mm",
                                               "end_overhang_mm", "axial_length_mm", "outer_diameter_mm", "skew_e_rad")
                        if k in design}
    record["seconds"] = time.time() - began
    if record.get("analysed"):
        cons = constraints_of(record, cfg)
        record["constraints"] = cons
        record["violation"] = float(sum(cons.values()))
    else:
        record.setdefault("violation", 5.0)
    return record


def objectives_of(record):
    if not record.get("analysed"):
        return [1e3, 1e3, 1e3]
    ripple = record["ripple"] if math.isfinite(record["ripple"]) else 1e3
    return [-record["torque_Nm"], -record["peak_torque_Nm"], min(ripple, 1e3)]


def light(record):
    """The record without the bulky waveforms (for all_designs.jsonl)."""
    out = {k: v for k, v in record.items() if k not in ("waveforms", "torque_waveform_Nm", "trace")}
    if "srm" in out:
        out["srm"] = {k: v for k, v in out["srm"].items() if not k.startswith("map_")}
    if record.get("analysed"):
        out["torque_waveform_Nm"] = record.get("torque_waveform_Nm")
    return out


# ----------------------------------------------------------------------------- optimization of one topology

class PoolEvaluator:
    def __init__(self, key, cfg, rundir, workers):
        self.key, self.cfg, self.rundir = key, cfg, rundir
        self.pool = concurrent.futures.ProcessPoolExecutor(max_workers=workers)
        self.count = 0
        self.log = open(os.path.join(rundir, "all_designs.jsonl"), "a")
        self.full_dir = os.path.join(rundir, "records")
        os.makedirs(self.full_dir, exist_ok=True)
        self.variables = [v.as_dict() for v in TOPOLOGIES[key]().variables(envelope_for(cfg, key))]

    def __call__(self, designs):
        jobs = []
        for x in designs:
            values = {v["name"]: (int(round(val)) if v["kind"] == "int" else float(val)) for v, val in zip(self.variables, x)}
            self.count += 1
            work = os.path.join(self.rundir, "work", f"d{self.count:05d}")
            jobs.append((self.count, values, self.pool.submit(evaluate_values, self.key, values, self.cfg, work)))
        out = []
        for n, values, job in jobs:
            try:
                record = job.result()
            except Exception as error:
                record = {"machine": self.key, "values": values, "analysed": False, "reason": f"worker: {error}", "violation": 5.0}
            record["id"] = n
            self.log.write(json.dumps(light(record)) + "\n")
            self.log.flush()
            if record.get("analysed"):
                drive_eval.save(os.path.join(self.full_dir, f"d{n:05d}.json"), record)
            out.append((objectives_of(record), record.get("violation", 5.0)))
        return out

    def close(self):
        self.pool.shutdown()
        self.log.close()


def run_topology(key, cfg, out, population=None, generations=None, log=print):
    rundir = os.path.join(out, "runs", key)
    os.makedirs(rundir, exist_ok=True)
    opt = cfg["optimizer"]
    budget = opt.get("budgets", {}).get(key)
    if budget and population is None and generations is None:
        population, generations = budget
    topology = TOPOLOGIES[key]()
    variables = [v.as_dict() for v in topology.variables(envelope_for(cfg, key))]
    with open(os.path.join(rundir, "variables.json"), "w") as f:
        json.dump({"machine": key, "title": topology.title, "variables": variables}, f, indent=1)
    evaluator = PoolEvaluator(key, cfg, rundir, opt["workers"])
    began = time.time()

    def progress(state):
        feasible = sum(p["violation"] == 0 for p in state["population"])
        best = min((p["f"][0] for p in state["population"] if p["violation"] == 0), default=float("nan"))
        log(f"[{key}] generation {state['generation']}: {state['evaluations']} designs, {feasible} feasible, "
            f"best rated torque {-best:.3f} Nm, {time.time() - began:.0f} s")

    problem = Problem(variables=tuple(topology.variables(envelope_for(cfg, key))),
                      objectives=(Objective("rated_torque", "max"), Objective("peak_torque", "max"), Objective("ripple", "min")))
    optimizer = registry.create("optimizer", opt.get("algorithm", "nsga2"))
    try:
        optimizer.run(problem, evaluator, {"population": population or opt["population"],
                                           "generations": generations or opt["generations"], "seed": opt["seed"]},
                      os.path.join(rundir, "state.json"), on_generation=progress)
    finally:
        evaluator.close()
    return rundir


# ----------------------------------------------------------------------------- picks

def read_designs(rundir):
    out = []
    path = os.path.join(rundir, "all_designs.jsonl")
    if not os.path.isfile(path):
        return out
    with open(path) as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def picks(designs, cfg):
    """optimal: the most rated torque with ripple at most the pick limit, all constraints met;
    highest_torque: the most rated torque with all constraints met (any ripple)."""
    ok = [d for d in designs if d.get("analysed") and d.get("violation", 1) == 0]
    out = {}
    if not ok:                       # nothing meets every limit: the solved design that comes closest
        solved = [d for d in designs if d.get("analysed")]
        if solved:
            out["closest"] = min(solved, key=lambda d: (round(d.get("violation", 99), 3), -d["torque_Nm"]))
        return out
    out["highest_torque"] = max(ok, key=lambda d: d["torque_Nm"])
    smooth = [d for d in ok if d["ripple"] <= cfg["limits"]["pick_max_ripple"]]
    if smooth:
        out["optimal"] = max(smooth, key=lambda d: d["torque_Nm"])
    else:                     # the lowest ripple among the best half in torque
        best_half = sorted(ok, key=lambda d: -d["torque_Nm"])[:max(1, len(ok) // 2)]
        out["optimal"] = min(best_half, key=lambda d: d["ripple"])
    return out


def write_picks(rundir, cfg):
    designs = read_designs(rundir)
    chosen = picks(designs, cfg)
    with open(os.path.join(rundir, "picks.json"), "w") as f:
        json.dump({k: {"id": v["id"], "values": v["values"]} for k, v in chosen.items()}, f, indent=1)
    return chosen


def verify(key, cfg, out, positions=None, log=print):
    """The picks of a topology solved again on the finer mesh: more rotor positions, no-load sweep (cogging,
    EMF), fields kept for the ParaView export. The picks run in parallel processes."""
    rundir = os.path.join(out, "runs", key)
    positions = positions or cfg["optimizer"].get("verify_positions", 36)
    with open(os.path.join(rundir, "picks.json")) as f:
        chosen = json.load(f)
    unique = {}
    for name, pick in chosen.items():
        unique.setdefault(json.dumps(pick["values"], sort_keys=True), []).append(name)
    os.makedirs(os.path.join(rundir, "verify"), exist_ok=True)
    results = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, len(unique))) as pool:
        jobs = {}
        for tag, names in unique.items():
            pick = chosen[names[0]]
            work = os.path.join(rundir, "verify", f"{names[0]}_work")
            jobs[pool.submit(evaluate_values, key, pick["values"], cfg, work, positions, True, True, True)] = (names, pick)
        for job in concurrent.futures.as_completed(jobs):
            names, pick = jobs[job]
            record = job.result()
            for name in names:
                rec = dict(record, pick=name, id=pick["id"], picks=names)
                drive_eval.save(os.path.join(rundir, "verify", f"{name}.json"), rec)
                results[name] = rec
            log(f"[{key}] verified {'/'.join(names)}: torque {record.get('torque_Nm', float('nan')):.3f} Nm, "
                f"peak {record.get('peak_torque_Nm', float('nan')):.2f} Nm, ripple {100 * record.get('ripple', float('nan')):.1f} %, "
                f"eta {100 * record.get('efficiency', 0):.1f} %")
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None, help="output folder (default: the folder of the config)")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--population", type=int, default=None)
    ap.add_argument("--generations", type=int, default=None)
    ap.add_argument("--verify", action="store_true", help="verify the picks (after the optimization)")
    ap.add_argument("--skip-optimize", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.workers:
        cfg["optimizer"]["workers"] = args.workers
    out = args.out or cfg["_dir"]
    keys = args.only or cfg["topologies"]
    def log(text):
        print(time.strftime("%H:%M:%S"), text, flush=True)
    for key in keys:
        try:
            if not args.skip_optimize:
                run_topology(key, cfg, out, args.population, args.generations, log)
            chosen = write_picks(os.path.join(out, "runs", key), cfg)
            log(f"[{key}] picks: " + ", ".join(f"{k} {v['torque_Nm']:.3f} Nm" for k, v in chosen.items()))
            if args.verify and chosen:
                verify(key, cfg, out, log=log)
        except Exception:                      # one topology must not stop the others
            log(f"[{key}] FAILED\n{traceback.format_exc()}")
    return 0


# ----------------------------------------------------------------------------- reference model and speed sensitivity

def reference_model(cfg, out, log=print):
    """T66: the ILM-E-like machine under the datasheet's conditions (its rotor length, wound for 48 V at its
    no-load speed) and under the study's rules (30 mm, the rated speed of the study)."""
    ref = cfg["reference_model"]
    folder = os.path.join(out, "reference_model")
    os.makedirs(folder, exist_ok=True)
    cases = {}
    ds = copy.deepcopy(cfg)
    ds["envelope"]["stack_length_mm"] = ref["datasheet_stack_mm"]
    ds["drive"]["speed_rpm"] = ref["datasheet_speed_rpm"]
    cases["datasheet_conditions"] = ds
    cases["study_rules"] = cfg
    records = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(evaluate_values, ref["machine"], ref["values"], c, os.path.join(folder, f"{name}_work"),
                            c["optimizer"].get("verify_positions", 36), True, True, True): name for name, c in cases.items()}
        for job in concurrent.futures.as_completed(jobs):
            name = jobs[job]
            records[name] = job.result()
            drive_eval.save(os.path.join(folder, f"{name}.json"), records[name])
            r = records[name]
            log(f"[reference {name}] torque {r.get('torque_Nm', float('nan')):.3f} Nm, kT {r.get('kt_Nm_A', float('nan')):.3f}, "
                f"peak {r.get('peak_torque_Nm', float('nan')):.2f} Nm")
    light_records = {k: light(v) for k, v in records.items()}
    with open(os.path.join(folder, "summary.json"), "w") as f:
        json.dump({"note": ref["note"], "records": light_records}, f, indent=1)
    return records


def speed_sensitivity(cfg, out, speeds=None, log=print, only=None, reference=True):
    """The optimal pick of every topology wound again for other rated speeds (the turns follow the voltage)."""
    speeds = speeds or cfg.get("speed_sensitivity_rpm", [250.0, 500.0, 1606.0])
    folder = os.path.join(out, "speed_sensitivity")
    os.makedirs(folder, exist_ok=True)
    jobs = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=cfg["optimizer"]["workers"]) as pool:
        for key in (only or cfg["topologies"]):
            path = os.path.join(out, "runs", key, "picks.json")
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                chosen = json.load(f)
            if "optimal" not in chosen:
                continue
            for speed in speeds:
                c = copy.deepcopy(cfg)
                c["drive"]["speed_rpm"] = speed
                work = os.path.join(folder, f"{key}_{int(speed)}_work")
                jobs[pool.submit(evaluate_values, key, chosen["optimal"]["values"], c, work)] = (key, speed)
        ref = cfg.get("reference_model") if reference else None
        if ref:
            for speed in speeds:
                c = copy.deepcopy(cfg)
                c["drive"]["speed_rpm"] = speed
                work = os.path.join(folder, f"ilm_e_model_{int(speed)}_work")
                jobs[pool.submit(evaluate_values, ref["machine"], ref["values"], c, work)] = ("ilm_e_model", speed)
        results = {}
        for job in concurrent.futures.as_completed(jobs):
            key, speed = jobs[job]
            r = job.result()
            results.setdefault(key, {})[str(int(speed))] = light(r)
            log(f"[speed {key} {speed:.0f} rpm] torque {r.get('torque_Nm', float('nan')):.3f} Nm, eta {100 * r.get('efficiency', 0):.1f} %")
    path = os.path.join(folder, "results.json")
    if os.path.isfile(path):                    # keep the results of earlier calls (other topologies)
        with open(path) as f:
            earlier = json.load(f)
        for key, value in results.items():
            earlier.setdefault(key, {}).update(value)
        results = earlier
    with open(path, "w") as f:
        json.dump(results, f)
    return results


def slice_check(keys, cfg, out, slices=5, log=print):
    """T67: the verified picks of axial machines solved again with more slices (finer mesh, same positions)."""
    jobs = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, min(len(keys), cfg["optimizer"]["workers"]))) as pool:
        for key in keys:
            rundir = os.path.join(out, "runs", key)
            for name in ("optimal", "closest"):
                path = os.path.join(rundir, "verify", f"{name}.json")
                if not os.path.isfile(path):
                    continue
                with open(path) as f:
                    record = json.load(f)
                c = copy.deepcopy(cfg)
                c["envelope"]["fidelity"]["fine_axial_slices"] = slices
                work = os.path.join(rundir, "verify", f"{name}_{slices}slices_work")
                jobs[pool.submit(evaluate_values, key, record["values"], c,
                                 work, cfg["optimizer"].get("verify_positions", 36), False, False, True)] = (key, name, record)
                break
        results = {}
        for job in concurrent.futures.as_completed(jobs):
            key, name, base = jobs[job]
            r = job.result()
            drive_eval.save(os.path.join(out, "runs", key, "verify", f"{name}_{slices}slices.json"), r)
            row = {"slices_3": {k: base.get(k) for k in ("torque_Nm", "peak_torque_Nm", "ripple", "efficiency")},
                   f"slices_{slices}": {k: r.get(k) for k in ("torque_Nm", "peak_torque_Nm", "ripple", "efficiency")}}
            results[key] = row
            log(f"[{key} {slices} slices] torque {r.get('torque_Nm', float('nan')):.3f} (3: {base['torque_Nm']:.3f}) Nm, "
                f"peak {r.get('peak_torque_Nm', float('nan')):.2f} (3: {base['peak_torque_Nm']:.2f}) Nm, "
                f"eta {100 * r.get('efficiency', 0):.1f} (3: {100 * base['efficiency']:.1f}) %")
    path = os.path.join(out, "runs", "slice_convergence.json")
    with open(path, "w") as f:
        json.dump(results, f, indent=1)
    return results


def tasks_main(argv=None):
    ap = argparse.ArgumentParser(description="Reference model (T66) and speed sensitivity of the study")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--speeds", action="store_true")
    ap.add_argument("--skew-check", nargs="*", default=None, help="topologies whose optimal pick gets the stepped-skew check")
    ap.add_argument("--only", nargs="*", default=None, help="speed sensitivity: these topologies only")
    ap.add_argument("--slice-check", nargs="*", default=None, help="axial topologies solved again with 5 slices (T67)")
    ap.add_argument("--no-reference", action="store_true", help="speed sensitivity: without the reference model")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.workers:
        cfg["optimizer"]["workers"] = args.workers
    out = args.out or cfg["_dir"]

    def log(text):
        print(time.strftime("%H:%M:%S"), text, flush=True)
    if args.reference:
        reference_model(cfg, out, log)
    if args.speeds:
        speed_sensitivity(cfg, out, log=log, only=args.only, reference=not args.no_reference)
    if args.slice_check:
        slice_check(args.slice_check, cfg, out, log=log)
    if args.skew_check:
        for key in args.skew_check:
            skew_check(key, cfg, out, log=log)



def skew_check(key, cfg, out, pick="optimal", steps=5, positions=18, log=print):
    """T61-3: the skew of a verified pick solved as `steps` rotor slices (each shifted by its share of the skew
    angle, the currents those of the central slice) against the harmonic skew model of the evaluation."""
    import numpy as np
    from emachine.physics import drive as D
    from emachine.pipeline.drive import FieldRunner
    rundir = os.path.join(out, "runs", key)
    with open(os.path.join(rundir, "verify", f"{pick}.json")) as f:
        record = json.load(f)
    topo = TOPOLOGIES[key]()
    design = topo.design(envelope_for(cfg, key), record["values"])
    skew_e, pe = design.get("skew_e_rad", 0.0), int(design["pe"])
    settings = settings_for(cfg, topo)
    register_solvers()
    runner = FieldRunner(design["params"], settings["analysis"], os.path.join(rundir, "verify", f"{pick}_skew_work"),
                         kind=design.get("geometry_kind", "section2d"), solver=design.get("solver", "elmer_sections"))
    n_eff, gamma, seq = record["winding"]["n_eff"], math.radians(record["gamma_deg"]), record["sequence"]
    i_r = cfg["drive"]["rated_current_A"]
    shifts = [skew_e / pe * (s / (steps - 1) - 0.5) for s in range(steps)] if steps > 1 else [0.0]
    angles = [math.pi / pe * k / positions for k in range(positions)]          # mechanical radians, half a period
    sliced = np.zeros((steps, positions))
    for s, shift in enumerate(shifts):
        for k, ang in enumerate(angles):
            i_abc = D.phase_currents(n_eff * i_r, pe * ang, gamma, seq)
            sliced[s, k] = runner.solve(math.degrees(ang + shift), i_abc).torque_Nm
    stepped = sliced.mean(axis=0)
    unskewed = sliced[steps // 2] if steps % 2 else None
    model = None
    if unskewed is not None:
        k1 = D.skew_factor(1, skew_e)
        model = D.skewed(unskewed - unskewed.mean(), skew_e, antiperiodic=False) + unskewed.mean() * k1
    result = {"machine": key, "pick": pick, "skew_el_deg": math.degrees(skew_e), "steps": steps,
              "stepped_mean_Nm": float(stepped.mean()), "stepped_ripple": D.ripple(stepped),
              "unskewed_mean_Nm": float(unskewed.mean()) if unskewed is not None else None,
              "unskewed_ripple": D.ripple(unskewed) if unskewed is not None else None,
              "model_mean_Nm": float(model.mean()) if model is not None else None,
              "model_ripple": D.ripple(model) if model is not None else None,
              "stepped_Nm": stepped.tolist(), "unskewed_Nm": unskewed.tolist() if unskewed is not None else None}
    with open(os.path.join(rundir, "verify", f"{pick}_skew_check.json"), "w") as f:
        json.dump(result, f, indent=1)
    log(f"[{key} skew check] {math.degrees(skew_e):.1f} el. deg, {steps} steps: mean {result['stepped_mean_Nm']:.3f} Nm "
        f"(model {result['model_mean_Nm']}), ripple {100 * result['stepped_ripple']:.1f} % (model "
        f"{100 * (result['model_ripple'] or float('nan')):.1f} %, unskewed {100 * (result['unskewed_ripple'] or float('nan')):.1f} %)")
    return result


if __name__ == "__main__":
    import sys
    sys.exit(tasks_main())
