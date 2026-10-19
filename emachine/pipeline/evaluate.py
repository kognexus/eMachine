"""
Evaluation of one design: objectives and constraints from all the models.

    geometry checks -> field analysis -> torque metrics -> losses and temperatures -> turns,
    current and voltage -> constraints -> objectives

Results are cached under a hash of the specification and the design, so a repeated design
costs nothing and an interrupted optimization can resume. Field solutions are cached apart from
the limits, so changing a limit does not repeat them.

Two ways of saving field solutions:

    stages        every second rotor position first; the rest only if the design is not already
                  outside the limits (ticket T20)
    load levels   a geometry is solved at a few current densities and every other current
                  density of it is interpolated (ticket T21)
"""

import hashlib
import inspect
import json
import math
import os
import shutil
import time

import numpy as np

from emachine.spec.names import cache_view, legacy_values, standard_values
from emachine.physics import losses
from emachine.physics import thermal as thermal_network
from emachine.physics import torque
from emachine.physics import winding as winding_model
from emachine.physics.interpolation import pchip

from . import design_space as design
from .sweep import analytic_stand_in, field_analysis  # noqa: F401  (analytic_stand_in: for tests and dry runs)

RIPPLE_CAP = 1.0e3            # ripple reported for a design without positive mean torque
UNANALYSED_PENALTY = 1.0      # added to the violation of designs that were not analysed
FAILED_PENALTY = 10.0
LINEAR_CORE_FLUX_LIMIT_T = 1.8  # applied when the stator core is linear and the user set no limit
RIPPLE_VIOLATION_CAP = 10.0   # largest contribution of the ripple limit to the violation
MODEL_VERSION = 3             # raised when a model change makes cached results invalid (2: B05, 3: T31 losses)


def keyed_spec(spec, sections=None):
    """The part of a spec a cache key depends on, in the names used before the naming standard (T43),
    so that the keys of older runs stay the same (emachine.spec.names.cache_view)."""
    keep = sections or [k for k in spec if k not in ("optimizer", "variables", "objectives")]
    return cache_view({k: v for k, v in spec.items() if k in keep})


def keyed_values(spec, values):
    """A design as cache keys see it: TFM variables in the names used before T50 (tooth_span, ...),
    so the caches of older TFM runs stay valid, whichever names the design was written in."""
    return legacy_values(spec, standard_values(spec, values))


def cache_key(spec, values):
    relevant = keyed_spec(spec)
    text = json.dumps({"spec": relevant, "values": keyed_values(spec, values), "model": MODEL_VERSION}, sort_keys=True)
    return hashlib.sha1(text.encode()).hexdigest()[:20]


def record_name(spec, values, analyse=None):
    """File name of the cached record of a design. Dry-run results are kept apart from field-solver results."""
    return cache_key(spec, values) + ("" if analyse is None else "-" + _analysis_name(analyse)) + ".json"


def _analysis_name(analyse):
    return "field solver" if analyse is None else getattr(analyse, "__name__", "custom")


def field_key(spec, parameters, analyse=None, positions=None):
    """
    Identity of a field solution: everything the field depends on (geometry, mesh, materials,
    ampere-turns, positions), and nothing else. Limits, speed, thermal data and objectives are not
    part of it, so changing them re-uses the field solution.
    """
    core = spec["materials"]["stator_core"]
    if isinstance(parameters.get("design"), dict):     # TFM variables in the names of older runs (T50)
        parameters = dict(parameters, design=keyed_values(spec, parameters["design"]))
    positions = int(spec["fidelity"]["positions"]) if positions is None else int(positions)
    text = json.dumps({"parameters": parameters, "positions": positions,
                       "loss": [core[k] for k in ("density_kg_m3", "k_hysteresis", "alpha", "k_eddy")],
                       "model": MODEL_VERSION, "analysis": _analysis_name(analyse)}, sort_keys=True)
    return hashlib.sha1(text.encode()).hexdigest()[:20]


# ----------------------------------------------------------------------------- field solutions

def staging(spec):
    """Rotor positions of the first stage, or None when the sweep is not staged."""
    fidelity = spec["fidelity"]
    n = int(fidelity["positions"])
    half = n // 2
    if not fidelity["staged"] or n % 2 or half < 3:
        return None
    if spec["machine"]["phases"] == 3 and half % 3:
        return None
    return half


def _accepts_shift(analyse):
    if analyse is None:
        return True
    try:
        return "shift" in inspect.signature(analyse).parameters
    except (TypeError, ValueError):
        return False


def _sweep(spec, parameters, analyse, positions, rundir, shift=0.0, geometry="tfm.sector3d"):
    """One sweep of the analysis function. `shift` moves all positions by a fraction of a step."""
    run = analyse
    if run is None:
        run = field_analysis(geometry)
    jobs = int(spec["optimizer"]["jobs"])
    if shift:
        return run(parameters, positions, rundir, jobs, shift=shift)
    return run(parameters, positions, rundir, jobs)


def interleave(first, second):
    """Samples of two half sweeps in the order of the full sweep: first[0], second[0], first[1], ..."""
    first, second = np.asarray(first), np.asarray(second)
    out = np.empty(len(first) + len(second), dtype=float)
    out[0::2], out[1::2] = first, second
    return out


def _merge(first, second):
    """Raw results of the half sweep and the shifted half sweep, combined into the full sweep."""
    files = [f for pair in zip(first.get("core_field_files", []), second.get("core_field_files", [])) for f in pair]
    iterations = None
    if first.get("nonlinear_iterations") is not None and second.get("nonlinear_iterations") is not None:
        iterations = [i for pair in zip(first["nonlinear_iterations"], second["nonlinear_iterations"]) for i in pair]
    return {"torque_Nm": interleave(first["torque_Nm"], second["torque_Nm"]),
            "flux_per_turn_Wb": interleave(first["flux_per_turn_Wb"], second["flux_per_turn_Wb"]),
            "core_field_files": files, "elements": first.get("elements"),
            "seconds": (first.get("seconds") or 0.0) + (second.get("seconds") or 0.0),
            "warnings": sorted(set(first.get("warnings", [])) | set(second.get("warnings", []))),
            "nonlinear_iterations": iterations}


def _reduce(spec, raw, analyse):
    """A raw analysis result reduced to what the other models need."""
    files = [f for f in raw.get("core_field_files", []) if f]
    return {
        "torque_Nm": [float(v) for v in raw["torque_Nm"]],
        "flux_per_turn_Wb": [float(v) for v in raw["flux_per_turn_Wb"]],
        "iron": losses.iron_loss_coefficients(spec, files) if files else None,
        "elements": raw.get("elements"),
        "seconds": raw.get("seconds"),
        "warnings": list(raw.get("warnings", [])),
        "nonlinear_iterations": raw.get("nonlinear_iterations"),
        "analysis": _analysis_name(analyse),
    }


def _load(path):
    with open(path) as f:
        return json.load(f)


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def solve_fields(spec, designs, workdir, analyse=None, use_cache=True, keep_analysis=False, stop=None):
    """
    Field solutions of several designs that are judged together (the load levels of one
    geometry, or a single design).

    stop  function(list of first-stage results) -> True when no second stage is wanted.
          Without it, or when the sweep cannot be staged, every design is solved in full.

    Returns (list of results, info). info["stage"] is "full" or "first"; info["positions_solved"]
    counts the rotor positions solved in this call. Results are cached in <workdir>/cache/fields.
    """
    n = int(spec["fidelity"]["positions"])
    half = staging(spec) if stop is not None else None
    requests = [design.geometry(spec, values) for values in designs]
    parameters = [r.parameters for r in requests]
    kind = requests[0].kind
    fields_dir = os.path.join(workdir, "cache", "fields")
    full_store = [os.path.join(fields_dir, field_key(spec, p, analyse) + ".json") for p in parameters]
    rundirs = [os.path.join(workdir, "analysis", field_key(spec, p, analyse)) for p in parameters]
    full = [_load(path) if use_cache and os.path.isfile(path) else None for path in full_store]
    info = {"stage": "full", "positions_solved": 0, "reused": all(f is not None for f in full)}

    def finish(fields):
        if not keep_analysis:
            for rundir in rundirs:
                shutil.rmtree(rundir, ignore_errors=True)
        return fields, info

    def solve_full(i, raw=None):
        raw = raw or _sweep(spec, parameters[i], analyse, n, os.path.join(rundirs[i], "full"), geometry=kind)
        full[i] = _reduce(spec, raw, analyse)
        if use_cache:
            _save(full_store[i], full[i])

    if info["reused"]:
        return finish(full)
    if half is None:
        for i in range(len(designs)):
            if full[i] is None:
                solve_full(i)
                info["positions_solved"] += n
        return finish(full)

    # First stage: every second position, which is a sweep of n / 2 positions.
    first, raw_first = [], []
    for i in range(len(designs)):
        raw = None
        if full[i] is not None:
            field = dict(full[i], torque_Nm=full[i]["torque_Nm"][0::2], flux_per_turn_Wb=full[i]["flux_per_turn_Wb"][0::2])
        else:
            store = os.path.join(fields_dir, field_key(spec, parameters[i], analyse, half) + ".json")
            if use_cache and os.path.isfile(store):
                field = _load(store)
            else:
                raw = _sweep(spec, parameters[i], analyse, half, os.path.join(rundirs[i], "first"), geometry=kind)
                field = _reduce(spec, raw, analyse)
                info["positions_solved"] += half
                if use_cache:
                    _save(store, field)
        first.append(field)
        raw_first.append(raw)
    if stop(first):
        info["stage"] = "first"
        return finish(first)

    # Second stage: the positions in between. Together with the first stage they are the full sweep.
    for i in range(len(designs)):
        if full[i] is not None:
            continue
        if raw_first[i] is not None and _accepts_shift(analyse):
            second = _sweep(spec, parameters[i], analyse, half, os.path.join(rundirs[i], "second"), shift=0.5,
                            geometry=kind)
            solve_full(i, _merge(raw_first[i], second))
            info["positions_solved"] += half
        else:           # the first stage came from the cache, or the function cannot shift: solve the full sweep
            solve_full(i)
            info["positions_solved"] += n
    return finish(full)


def field_solution(spec, values, workdir, analyse=None, use_cache=True, keep_analysis=False):
    """Full field solution of one design. Returns (result, True if it came from the cache)."""
    fields, info = solve_fields(spec, [values], workdir, analyse, use_cache, keep_analysis)
    return fields[0], info["reused"]


# ----------------------------------------------------------------------------- load levels

def load_levels(spec, values):
    """
    Current densities at which the geometry of a design is solved, or None when every design
    gets its own field solution (`fidelity.load_levels` = 0, or the current density is fixed).
    """
    count = int(spec["fidelity"]["load_levels"])
    var = next((v for v in design.variables(spec) if v["name"] == "current_density_A_mm2"), None)
    if var is None or count < 2 or var["high"] <= var["low"]:
        return None
    return [float(v) for v in np.linspace(var["low"], var["high"], count)]


def interpolate_fields(fields, level_densities, density):
    """Field result at a current density between the levels of one geometry."""
    x = np.asarray(level_densities, dtype=float)
    out = dict(fields[0])
    for name in ("torque_Nm", "flux_per_turn_Wb"):
        out[name] = pchip(x, np.array([f[name] for f in fields], dtype=float), [density])[0].tolist()
    if all(f["iron"] for f in fields):
        iron = {}
        for name in fields[0]["iron"]:
            if name in losses.SPECTRA:
                spectra = [f["iron"][name] for f in fields]
                if len({len(v) for v in spectra}) != 1 or not spectra[0]:
                    iron[name] = spectra[0]
                    continue
                iron[name] = np.maximum(pchip(x, np.array(spectra, dtype=float), [density])[0], 0.0).tolist()
                continue
            series = np.array([f["iron"][name] for f in fields], dtype=float)
            iron[name] = float(max(pchip(x, series, [density])[0], 0.0)) if name in losses.COEFFICIENTS \
                else float(np.interp(density, x, series))
        out["iron"] = iron
    out["seconds"] = sum((f.get("seconds") or 0.0) for f in fields)
    out["warnings"] = sorted({w for f in fields for w in f.get("warnings", [])})
    out["nonlinear_iterations"] = None
    return out


def sibling_densities(spec, values, count):
    """Further current densities of the same geometry, spread over the range of the variable."""
    var = next((v for v in design.variables(spec) if v["name"] == "current_density_A_mm2"), None)
    if var is None or count < 1 or var["high"] <= var["low"]:
        return []
    step = (var["high"] - var["low"]) / max(count - 1, 1)
    grid = np.linspace(var["low"], var["high"], count) if count > 1 else [0.5 * (var["low"] + var["high"])]
    return [float(v) for v in grid if abs(v - values["current_density_A_mm2"]) > 0.25 * step]


# ----------------------------------------------------------------------------- one design

def _objective_vector(spec, objectives):
    out = []
    for name in spec["objectives"]:
        if name == "max_torque":
            out.append(-objectives["torque_Nm"])
        elif name == "max_efficiency":           # T70: efficiency at the operating point
            out.append(-objectives.get("efficiency", 0.0))
        elif name == "min_losses":
            out.append(objectives["loss_W"])
        else:
            out.append(min(objectives["ripple"], RIPPLE_CAP))
    return out


def _unanalysed(spec, values, reason, violation, checks=None, failed=False):
    worst = [math.inf] * len(spec["objectives"])
    return {"values": values, "analysed": False, "failed": failed, "reason": reason,
            "violated_checks": checks or [], "f": worst, "violation": violation, "cache_hit": False,
            "objectives": None, "seconds": 0.0}


def temperatures(spec, machine, values, d, iron_loss_W, rotor_loss_W, **iteration):
    """Temperatures of the machine's thermal network (nodes winding, core, rotor), with the copper loss at
    the winding temperature. `iteration`: max_iterations, tolerance_K of physics.thermal.coupled."""
    copper, winding = spec["materials"]["copper"], machine.winding(spec, values)
    r = thermal_network.coupled(
        machine.thermal_network(spec, values),
        lambda t: winding_model.copper_loss(winding_model.winding_resistance(copper, winding, t), d["ampere_turns_rms"]),
        {"core": iron_loss_W, "rotor": rotor_loss_W}, **iteration)
    t = r["temperatures"]
    return {"winding_C": t["winding"], "core_C": t["core"], "magnet_C": t["rotor"], "copper_loss_W": r["copper_loss_W"],
            "iterations": r["iterations"], "converged": r["converged"], "heat_to_ambient_W": r["heat_to_ambient_W"]}


def assemble(spec, values, result):
    """Record of a design from its field result: torque metrics, losses, temperatures, winding, constraints."""
    machine = design.machine_of(spec)
    d = machine.derive(spec, values)
    phases = spec["machine"]["phases"]
    lim = spec["limits"]
    core = spec["materials"]["stator_core"]
    core_is_linear = core["saturation_T"] is None and core["bh_curve"] is None
    b_limit = lim["max_core_flux_density_T"]
    if b_limit is None and core_is_linear:
        b_limit = LINEAR_CORE_FLUX_LIMIT_T
    ambient = spec["operating_point"]["ambient_C"]
    phase_torque = np.asarray(result["torque_Nm"], dtype=float)
    flux = np.asarray(result["flux_per_turn_Wb"], dtype=float)
    plan = machine.excitation(spec, values)
    total = (torque.machine_torque(phase_torque, phases, period="half") if plan.mode == "single_phase_shifted"
             else phase_torque.copy())
    tm = torque.metrics(total)

    frequency = d["electrical_frequency_Hz"]
    if result["iron"]:
        iron = {k: v for k, v in result["iron"].items() if k not in losses.COEFFICIENTS + losses.SPECTRA}
        stator, rotor = losses.loss_at(result["iron"], frequency, spec["materials"])
        iron["iron_loss_W"], iron["rotor_loss_W"] = float(stator), float(rotor)
    else:
        iron = {"iron_loss_W": 0.0, "rotor_loss_W": 0.0, "core_b_max_T": None, "core_b_p95_T": None,
                "core_b_mean_T": None, "core_mass_kg": None}
    heat = temperatures(spec, machine, values, d, iron["iron_loss_W"], iron["rotor_loss_W"])
    winding = winding_model.turns_for(machine.winding(spec, values), spec["materials"]["copper"], lim, flux,
                                      d["electrical_frequency_Hz"], d["ampere_turns_peak"], heat["winding_C"],
                                      spec["winding"]["strip_min_thickness_mm"])

    loss_total = phases * (heat["copper_loss_W"] + iron["iron_loss_W"] + iron["rotor_loss_W"])
    omega = 2 * math.pi * spec["operating_point"]["speed_rpm"] / 60.0
    power = tm["mean"] * omega
    objectives = {
        "torque_Nm": tm["mean"],
        "loss_W": loss_total,
        "ripple": tm["ripple"] if math.isfinite(tm["ripple"]) else RIPPLE_CAP,
        "efficiency": power / (power + loss_total) if power > 0 and power + loss_total > 0 else 0.0,
    }
    ripple_limit = lim["max_torque_ripple_percent"]
    constraints = {
        "turns": winding["violation"],
        # (highest - lowest) / mean of the machine torque, against the limit in percent.
        "torque_ripple": (min(RIPPLE_VIOLATION_CAP, max(0.0, 100.0 * objectives["ripple"] / ripple_limit - 1.0))
                          if ripple_limit is not None else 0.0),
        "winding_temperature": max(0.0, (heat["winding_C"] - lim["max_winding_temp_C"])
                                   / max(lim["max_winding_temp_C"] - ambient, 1.0)),
        "magnet_temperature": max(0.0, (heat["magnet_C"] - lim["max_magnet_temp_C"])
                                  / max(lim["max_magnet_temp_C"] - ambient, 1.0)),
        "thermal_convergence": 0.0 if heat["converged"] else 1.0,
        "current_density": max(0.0, winding["current_density_rms_A_mm2"] / lim["max_current_density_A_mm2"] - 1.0),
        # With a linear core material, designs that push most of the core beyond the limit would
        # saturate in reality and are not accepted. With saturation modelled there is no limit
        # unless the user sets one.
        "core_flux_density": (max(0.0, iron["core_b_p95_T"] / b_limit - 1.0)
                              if (b_limit is not None and iron["core_b_p95_T"] is not None) else 0.0),
    }
    return {
        "values": values,
        "analysed": True,
        "failed": False,
        "reason": None,
        "violated_checks": [],
        "objectives": objectives,
        "f": _objective_vector(spec, objectives),
        "violation": float(sum(constraints.values())),
        "constraints": constraints,
        "torque": {**tm, "phase_waveform_Nm": phase_torque.tolist(), "machine_waveform_Nm": total.tolist()},
        "flux_per_turn_Wb": flux.tolist(),
        "ampere_turns_peak": d["ampere_turns_peak"],
        "winding": winding,
        "losses": {"copper_W_per_phase": heat["copper_loss_W"], "iron_W_per_phase": iron["iron_loss_W"],
                   "rotor_W_per_phase": iron["rotor_loss_W"],
                   "total_W": loss_total, "not_included": losses.NOT_INCLUDED, **iron},
        "thermal": heat,
        "output_power_W": power,
        "efficiency": power / (power + loss_total) if power + loss_total > 0 else 0.0,
        "geometry": {k: v for k, v in d.items() if isinstance(v, (int, float, bool))},
        "analysis": {"elements": result.get("elements"), "seconds": result.get("seconds"),
                     "warnings": result.get("warnings", []), "positions": len(phase_torque),
                     "core_material": "linear" if core_is_linear else "saturating",
                     "nonlinear_iterations": result.get("nonlinear_iterations"),
                     "fidelity": spec["fidelity"]["level"], "model_version": MODEL_VERSION,
                     "source": result.get("analysis")},
        "cache_hit": False,
    }


def evaluate_geometry(spec, values, workdir, analyse=None, use_cache=True, keep_analysis=False, siblings=0):
    """
    Evaluates a design and, with load levels switched on, up to `siblings` further designs of
    the same geometry at other current densities. Returns the list of records, the asked design first.

    analyse  function(parameters, positions, rundir, jobs[, shift]) -> analysis result; defaults
             to the field analysis of the machine's geometry (sweep.field_analysis). Tests pass the
             analytic stand-in.
    """
    began = time.time()
    values = design.clip(spec, values)
    checks = design.checks(spec, values)
    violated = design.violations(checks)
    if violated:
        return [_unanalysed(spec, values, "geometry", UNANALYSED_PENALTY + design.total_violation(checks),
                            [{k: c.as_dict()[k] for k in ("name", "value", "limit", "sense")} for c in violated])]

    levels = load_levels(spec, values)
    wanted = [values]
    if levels:
        for density in sibling_densities(spec, values, siblings):
            other = dict(values, current_density_A_mm2=density)
            if design.is_feasible(design.checks(spec, other)):
                wanted.append(other)

    def cache_file(v):
        return os.path.join(workdir, "cache", record_name(spec, v, analyse))

    if use_cache and all(os.path.isfile(cache_file(v)) for v in wanted):
        records = [_load(cache_file(v)) for v in wanted]
        for record in records:
            record["cache_hit"] = True
            if record.get("analysed") and record.get("objectives"):
                # The cache key leaves out the objectives: the vector follows this spec's objectives.
                record["objectives"].setdefault("efficiency", max(record.get("efficiency", 0.0), 0.0))
                record["f"] = _objective_vector(spec, record["objectives"])
        return records

    solved = [dict(values, current_density_A_mm2=density) for density in levels] if levels else [values]
    margin = float(spec["fidelity"]["early_stop_margin"])

    def at(fields, v):
        if not levels:
            return fields[0]
        return interpolate_fields(fields, levels, v["current_density_A_mm2"])

    def stop(first_stage):
        # Outside the limits by more than the margin at every current density asked for: the
        # second stage cannot change that, because the ripple of the first stage is a lower bound.
        return all(assemble(spec, v, at(first_stage, v))["violation"] > margin for v in wanted)

    try:
        fields, info = solve_fields(spec, solved, workdir, analyse, use_cache, keep_analysis, stop)
    except Exception as error:           # meshing or solver failure: the design is discarded, the run goes on
        record = _unanalysed(spec, values, f"analysis failed: {str(error).splitlines()[0]}", FAILED_PENALTY, failed=True)
        record["seconds"] = time.time() - began
        return [record]

    records = []
    for k, v in enumerate(wanted):
        record = assemble(spec, v, at(fields, v))
        record["analysis"].update({
            "stage": info["stage"],
            "stopped_early": info["stage"] == "first",              # ripple is then a lower bound
            "field_solution_reused": info["reused"],
            "positions_solved": info["positions_solved"] if k == 0 else 0,
            "load_levels": levels,
            "interpolated": bool(levels) and min(abs(v["current_density_A_mm2"] - x) for x in levels) > 1e-9,
            "sibling": k > 0,
        })
        record["seconds"] = time.time() - began if k == 0 else 0.0
        if use_cache:
            _save(cache_file(v), record)
        records.append(record)
    return records


def evaluate(spec, values, workdir, analyse=None, use_cache=True, keep_analysis=False):
    """Evaluates one design and returns its record."""
    return evaluate_geometry(spec, values, workdir, analyse, use_cache, keep_analysis)[0]


def key_of(x):
    """Identity of a design vector, used to avoid evaluating duplicates."""
    return ",".join(f"{v:.10g}" for v in x)


class BatchEvaluator:
    """
    Adapter for the optimizer: evaluates lists of design vectors and keeps every record.
    With load levels switched on, the further designs of each geometry are handed to the optimizer
    through `take_extra`.
    """

    def __init__(self, spec, workdir, analyse=None, log=None):
        self.spec, self.workdir, self.analyse, self.log = spec, workdir, analyse, log
        self.records = {}
        self.positions_solved = 0
        self._extra = []

    def __call__(self, designs):
        steps = int(self.spec["optimizer"]["current_steps"])
        out = []
        for x in designs:
            records = evaluate_geometry(self.spec, design.to_values(self.spec, x), self.workdir, self.analyse,
                                        siblings=steps)
            record = records[0]
            self.records[key_of(x)] = record
            out.append((record["f"], record["violation"]))
            if record["analysed"]:
                self.positions_solved += record["analysis"].get("positions_solved", 0)
            if self.log:
                self.log(record)
            for sibling in records[1:]:
                vector = design.to_vector(self.spec, sibling["values"])
                if key_of(vector) not in self.records:
                    self.records[key_of(vector)] = sibling
                    self._extra.append((vector, sibling["f"], sibling["violation"]))
        return out

    def take_extra(self):
        """Designs that came for free since the last call: list of (design vector, objectives, violation)."""
        extra, self._extra = self._extra, []
        return extra
