"""
Regression cases: numerical results of the code (specs, designs, losses, torque, efficiency map,
NSGA-II, mesh volumes, one Elmer solution), recorded in baseline/<case>.json by capture.py and
reproduced by every run of test_regression.py. They were first recorded before the restructuring
into `emachine` (T32); the variable names of that time are kept in the recorded data.

Each case is a function that returns plain data (dicts, lists, numbers, strings).
"""

import glob
import json
import math
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def plain(value):
    """JSON-friendly copy: arrays to lists, numpy scalars to Python numbers, tuples to lists."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _spec_files():
    files = sorted(f for f in glob.glob(os.path.join(ROOT, "examples", "*.json")) if not f.endswith("_design.json") and not os.path.basename(f).startswith(("rfm_", "rafm_")))  # specs older than the refactor
    return files


def _designs():
    """(label, spec, values) of the reference designs."""
    from emachine.machines.tfm import design
    from emachine.machines.tfm.reference import REFERENCE_DESIGN
    from emachine.spec import load_spec
    out = [("default_reference", load_spec({}), dict(REFERENCE_DESIGN))]
    user = load_spec(os.path.join(ROOT, "examples", "user_tr48.json"))
    with open(os.path.join(ROOT, "examples", "user_tr48_design.json")) as f:
        out.append(("user_tr48", user, design.clip(user, json.load(f))))
    for path in sorted(glob.glob(os.path.join(ROOT, "examples", "three_phase_*.json"))):
        spec = load_spec(path)
        middle = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
        if "claw_root_height_mm" in middle:      # the claw tip of the baseline data (T50)
            middle["claw_tip_height_mm"] = max(spec["limits"]["iron_thickness_mm"][0], 0.5 * middle["claw_root_height_mm"])
        out.append((os.path.basename(path)[:-5], spec, design.clip(spec, middle)))
    return out


# ----------------------------------------------------------------------------- fast cases

#: Keys added on purpose after the baseline data was recorded, left out of the comparison.
ADDED_MACHINE_KEYS = ("family", "topology")         # T34: machine plugins
ADDED_OPTIMIZER_KEYS = ("algorithm",)                # T37: optimizer plugins
ADDED_OPERATING_KEYS = ("current_angle_deg",)        # T41: d-q control
ADDED_VARIABLES = ("claw_tip_height_mm",)             # T50: was max(minimum iron, 0.5 x claw root)
ADDED_WINDING_KEYS = ("awg", "wire_diameter_mm", "awg_fill_share")    # T57: wire gauge of the turns


def without_wire(d):
    return {k: v for k, v in d.items() if k not in ADDED_WINDING_KEYS}


def recorded_values(spec, values):
    """A TFM design in the variable names of the baseline data (before T50)."""
    from emachine.spec.names import legacy_values
    return legacy_values(spec, values)


def recorded_variables(spec, variables):
    """The variable list in the names and units of the baseline data (before T50)."""
    from emachine.spec.names import SCALED_VARIABLES
    back = {new: (old, factor) for old, (new, factor) in SCALED_VARIABLES.items() if factor}
    out = []
    for var in variables:
        if var["name"] in ADDED_VARIABLES:
            continue
        old, factor = back.get(var["name"], (var["name"], 1.0))
        out.append(dict(var, name=old, low=var["low"] / factor, high=var["high"] / factor))
    return out


def case_specs():
    from emachine.spec import load_spec

    from emachine.spec.names import legacy_spec

    def recorded(spec):
        spec = legacy_spec(spec)              # T43: the standard names, written back in the recorded ones
        spec["machine"] = {k: v for k, v in spec["machine"].items() if k not in ADDED_MACHINE_KEYS}
        spec["optimizer"] = {k: v for k, v in spec["optimizer"].items() if k not in ADDED_OPTIMIZER_KEYS}
        spec["operating_point"] = {k: v for k, v in spec["operating_point"].items() if k not in ADDED_OPERATING_KEYS}
        spec["variables"] = {v["name"]: [v["low"], v["high"]] if v["low"] != v["high"] else v["low"]
                             for v in recorded_variables(spec, [{"name": k, "low": x[0] if isinstance(x, list) else x,
                                                                 "high": x[1] if isinstance(x, list) else x}
                                                                for k, x in spec["variables"].items()])}
        return spec

    out = {"defaults": recorded(load_spec({}))}
    for path in _spec_files():
        out[os.path.basename(path)] = recorded(load_spec(path))
    return plain(out)


def case_designs():
    from emachine.machines.tfm import checks, design
    from emachine.machines.tfm import thermal as tfm_thermal
    from emachine.machines.tfm.cad import sheet as onshape
    from emachine.physics import thermal
    from emachine.physics import winding as electrical
    from emachine.pipeline import design_space
    from emachine.pipeline.evaluate import temperatures
    out = {}
    for label, spec, values in _designs():
        d = design.derived(spec, values)
        machine = design_space.machine_of(spec)
        winding, copper = machine.winding(spec, values), spec["materials"]["copper"]
        parameters = design.to_parameters(spec, values)
        flux = 1e-4 * np.cos(electrical.electrical_angles(12))
        variables = recorded_variables(spec, design.variables(spec))
        old = recorded_values(spec, values)
        parameters = dict(parameters, design=recorded_values(spec, parameters["design"]))
        out[label] = {
            "values": old,
            "variables": variables,
            "vector": [old[v["name"]] for v in variables],
            "derived": d,
            "checks": [c.as_dict() for c in checks.check(spec, values)],
            "parameters": parameters,
            "from_parameters": recorded_values(spec, design.from_parameters(spec, parameters)),
            "sheet": onshape.to_text(onshape.sheet(parameters)),
            "resistance_20_turns_80C": electrical.resistance(electrical.winding_resistance(copper, winding, 80.0), 20),
            "copper_loss_60C": electrical.copper_loss(electrical.winding_resistance(copper, winding, 60.0),
                                                      d["ampere_turns_rms"]),
            "turns": without_wire(electrical.turns_for(winding, copper, spec["limits"], flux,
                                                       d["electrical_frequency_Hz"], d["ampere_turns_peak"], 80.0,
                                                       spec["winding"]["strip_min_thickness_mm"])),
            "thermal_response": thermal.response(tfm_thermal.network(spec, values, d), ("winding", "core", "rotor")),
            "thermal_coupled": temperatures(spec, machine, values, d, 5.0, 1.0),
        }
    return plain(out)


def case_stand_in_evaluation():
    from emachine.pipeline import evaluate
    out = {}
    for label, spec, values in _designs()[:2]:
        with tempfile.TemporaryDirectory() as tmp:
            record = evaluate.evaluate(spec, values, tmp, analyse=evaluate.analytic_stand_in, use_cache=False)
        drop = {"seconds", "rundir", "record_file", "time"}
        out[label] = {k: v for k, v in record.items() if k not in drop}
        out[label]["values"] = recorded_values(spec, out[label]["values"])
        out[label]["winding"] = without_wire(out[label]["winding"])
    return plain(out)


def _synthetic_core_files(tmp, n=12):
    """Stator and rotor fields over half a period (as tests/test_t31_losses.py)."""
    files = []
    rng = np.random.default_rng(7)
    centroid = rng.uniform(0.03, 0.04, (40, 3))
    rotor = np.column_stack([0.045 * np.cos(np.radians(np.linspace(1, 19, 20))),
                             0.045 * np.sin(np.radians(np.linspace(1, 19, 20))), np.zeros(20)])
    for k in range(n):
        angle = k * 20.0 / (2 * n)
        t = 2 * math.pi * angle / 20.0
        b = np.column_stack([np.cos(t + centroid[:, 0] * 50), 0.4 * np.sin(t + centroid[:, 1] * 30), 0.1 * np.ones(40)])
        sign = np.where(np.arange(20) < 10, 1.0, -1.0)
        rb = np.column_stack([0.15 * np.cos(2 * t) * sign, 0.9 * sign, np.zeros(20)])
        path = os.path.join(tmp, f"c{k:02d}.npz")
        np.savez(path, centroid=centroid, volume=np.full(40, 2e-9), b=b, periodicity=18, angle_deg=angle,
                 rotor_centroid=rotor, rotor_volume=np.full(20, 1e-9), rotor_b=rb,
                 rotor_kind=np.where(np.arange(20) % 2 == 0, 0, 2).astype(np.int8),
                 rotor_eddy_width_m=np.array([0.003, 0.003, 0.008]))
        files.append(path)
    return files


def case_losses():
    from emachine.physics import losses
    from emachine.spec import load_spec
    spec = load_spec({"materials": {"rotor_iron": {"conductivity_S_m": 6e6}}})
    with tempfile.TemporaryDirectory() as tmp:
        files = _synthetic_core_files(tmp)
        c = losses.iron_loss_coefficients(spec, files)
        stator, rotor = losses.loss_at(c, 300.0, spec["materials"])
        parts = losses.rotor_loss(c, 300.0, spec["materials"])
        volume, density = losses.stator_loss_density(spec["materials"]["stator_core"], 300.0, files)
    return plain({"coefficients": c, "stator_W": stator, "rotor_W": rotor, "parts_W": parts,
                  "density_sum": float(np.sum(volume * density)),
                  "density_alt": losses.iron_loss_density(spec["materials"]["stator_core"], 200.0, 1.2),
                  "rotational": losses.rotational_hysteresis_per_cycle(spec["materials"]["stator_core"]["rotational"],
                                                                      [0.2, 0.8, 1.4])})


def case_torque():
    from emachine.physics import torque
    angle = np.linspace(0, math.pi, 24, endpoint=False)
    phase = 1.0 + 0.3 * np.sin(2 * angle) + 0.05 * np.sin(6 * angle)
    total = torque.machine_torque(phase, 3)
    return plain({"machine": total, "metrics": torque.metrics(total), "single": torque.metrics(torque.machine_torque(phase, 1))})


def case_effmap():
    from emachine.machines.tfm import design
    from emachine.analysis import effmap
    from emachine.spec import load_spec
    spec = load_spec({})
    from emachine.machines.tfm.reference import REFERENCE_DESIGN
    values = design.clip(spec, REFERENCE_DESIGN)
    angle = np.pi * np.arange(12) / 12
    levels = [{"ampere_turns_peak": ni, "torque_Nm": list(np.full(12, 2e-3 * ni)),
               "flux_per_turn_Wb": list(2e-4 * np.cos(angle) * (1 - 1e-4 * ni)), "a_h": 0.02, "a_e": 3e-5,
               "a_x": 1e-4} for ni in (0.0, 300.0, 600.0)]
    machine = effmap.Machine(spec, values, levels, 40)
    result = effmap.compute(machine, np.linspace(0, 2000, 9), 7)
    info = effmap.summary(machine, result, 300.0, 300.0)
    return plain({"summary": info, "efficiency": result["grid"]["efficiency"],
                  "envelope": result["envelope"], "table": effmap.level_table(machine, levels)})


def case_nsga2():
    from emachine.optimization import nsga2
    variables = [{"name": f"x{i}", "kind": "real", "low": 0.0, "high": 1.0} for i in range(3)] + \
        [{"name": "n", "kind": "int", "low": 1, "high": 5}]

    def zdt1(designs):
        out = []
        for x in designs:
            g = 1 + 9 * sum(x[1:3]) / 2 + 0.1 * (x[3] - 3) ** 2
            out.append(([x[0], g * (1 - math.sqrt(x[0] / g))], max(0.0, 0.2 - x[0])))
        return out

    state = nsga2.optimize(variables, zdt1, population=12, generations=6, seed=5)
    return plain({"population": sorted((p["x"], p["f"], p["violation"]) for p in state["population"])})


FAST = {"specs": case_specs, "designs": case_designs, "stand_in_evaluation": case_stand_in_evaluation,
        "losses": case_losses, "torque": case_torque, "effmap": case_effmap, "nsga2": case_nsga2}


# ----------------------------------------------------------------------------- slow cases

def case_mesh_volumes():
    """Volume of every region of the stator and rotor builders, for each stator type of the mesher."""
    import gmsh
    from emachine.machines.tfm.geometry import sector as mesher
    out = {}
    stators = {
        "u": {"core_type": "u"}, "ui": {"core_type": "ui"}, "cp": {"core_type": "cp"},
        "cp_full_discs": {"core_type": "cp", "claw_full_discs": True, "claw_tip_height": 8.0},
        "tr": {"core_type": "tr"}, "tr_arched_staggered": {"core_type": "tr", "ring_arched_valleys": True,
                                                          "ring_staggered_teeth": True},
        "c": {"core_type": "c"}, "e": {"core_type": "e"}, "z": {"core_type": "z"},
        "u_inner": {"core_type": "u", "inner_stator": True, "air_gap_radius": 60.0},
    }
    for label, stator in stators.items():
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        try:
            parts, names, info = mesher.build_stator(dict(mesher.DEFAULTS["stator"], **stator))
            mesher.occ.synchronize()
            volumes = {}
            for (_, tag), name in zip(parts, names):
                volumes[name] = volumes.get(name, 0.0) + mesher.occ.getMass(3, tag)
            out[label] = {"volumes_mm3": volumes, "half_width": info["half_width"], "r_min": info["r_min"]}
        finally:
            gmsh.finalize()
    rotors = {"surface": {"type": "surface"}, "halbach": {"type": "halbach"},
              "flux_concentrating": {"type": "flux_concentrating"},
              "axial": {"type": "axial", "row_gap": 10.0},
              "outrunner": {"configuration": "outrunner", "type": "surface", "outer_diameter": 134.0}}
    for label, rotor in rotors.items():
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        try:
            parts, names, info = mesher.build_rotor(dict(mesher.DEFAULTS["rotor"], **rotor), 0.0)
            mesher.occ.synchronize()
            volumes = {}
            for (_, tag), name in zip(parts, names):
                volumes[name] = volumes.get(name, 0.0) + mesher.occ.getMass(3, tag)
            out["rotor_" + label] = {"volumes_mm3": volumes, "gap_radius": info["gap_radius"]}
        finally:
            gmsh.finalize()
    return plain(out)


def case_elmer_position():
    """One field solution of the default reference design at one rotor angle, loaded."""
    from emachine.pipeline import sweep
    from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS
    from emachine.machines.tfm import design
    from emachine.machines.tfm.reference import REFERENCE_DESIGN
    from emachine.spec import load_spec
    spec = load_spec({})
    parameters = design.to_parameters(spec, design.clip(spec, REFERENCE_DESIGN))
    analysis = dict(ANALYSIS_DEFAULTS, **parameters.get("analysis", {}))
    with tempfile.TemporaryDirectory() as tmp:
        row = sweep.solve_position(parameters, analysis, 2.5, os.path.join(tmp, "p"), current=300.0)
    return plain({k: row[k] for k in ("torque_Nm", "flux_linkage_Wb", "field_energy_J", "core_volume_mm3", "elements")})


SLOW = {"mesh_volumes": case_mesh_volumes, "elmer_position": case_elmer_position}

#: relative tolerance per case: the solver results carry iteration noise
TOLERANCE = {"elmer_position": 1e-6}
