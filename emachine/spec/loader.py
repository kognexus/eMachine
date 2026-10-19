"""
Design specification: the one file in which the user states the optimization problem.

`load_spec` merges the user's file over DEFAULTS and validates the result. Every limit and
material value used anywhere in the system is read from the specification.

The section `machine` holds the common keys below; `flux_path` and `principle` name the machine
(registered in emachine.core.registry as "<flux_path>/<principle>"), which adds its own options
(among them `rotor`, the rotor layout, and `stator`) and validates them. Files without them are
transverse flux PM machines ("tfm", "pmsm"). Names follow docs/naming.md; old names (`family`,
`topology`, `configuration`, `stator_type`, ...) are translated by emachine.spec.names.
"""

import copy
import json

from emachine.core import registry

from .errors import SpecError
from .names import standard_spec, standard_variables

OBJECTIVES = ("max_torque", "min_losses", "min_ripple", "max_efficiency")
CONDUCTORS = ("round_wire", "strip")

DEFAULTS = {
    "machine": {                        # common keys; the machine adds its own options
        "flux_path": "tfm",             # "tfm", "rfm", "afm", "rafm" (docs/naming.md)
        "principle": "pmsm",            # torque principle: "pmsm", "synrm", "srm", "vernier"
        "rotor_placement": "outer",     # "inner" (rotor inside the stator) or "outer"
        "outer_diameter_mm": 80.0,      # outside of the machine: rotor (outer rotor) or stator (inner rotor)
        "stack_length_mm": 23.0,        # axial length of all phases together
        "phases": 1,
        "air_gap_mm": 0.5,
        "bore_diameter_mm": 10.0,       # hole through the machine: nothing solid may reach inside it.
                                        # Inner rotor: shaft diameter. Outer rotor: free bore inside the stator.
    },
    "operating_point": {
        "speed_rpm": 300.0,
        "ambient_C": 25.0,
        "current_angle_deg": 0.0,           # current ahead of the induced voltage (d-q control); 0 = in phase
    },
    "limits": {
        "iron_thickness_mm": [2.0, 10.0],   # any iron section: legs, yoke, core thickness, bridge, rotor iron
        "pole_pairs": [4, 32],
        "bus_voltage_V": [12.0, 48.0],      # the design must be drivable at or below the upper value
        "max_current_A": 15.0,              # peak phase current
        "max_winding_temp_C": 120.0,
        "max_magnet_temp_C": 80.0,
        "max_current_density_A_mm2": 10.0,  # RMS, in the copper
        "max_torque_ripple_percent": 20.0,  # (highest - lowest) / mean of the machine torque. null = no limit
        "max_core_flux_density_T": None,    # on 95 % of the core volume. null = no limit when saturation is
                                            # modelled, and 1.8 T when the stator core is linear
        "min_slot_width_mm": 3.0,
        "min_coil_height_mm": 2.0,
        "min_core_gap_mm": 0.5,             # clearance between neighbouring stator cores
    },
    "variables": {},                        # optional: name -> [min, max], or a number to fix it
    "materials": {
        "magnet": {"remanence_T": 1.3, "mu_r": 1.05,
                   "conductivity_S_m": 6.7e5,       # sintered NdFeB (about 1.5 micro-ohm m); null = no eddy loss
                   "density_kg_m3": 7500.0,
                   "eddy_width_mm": None,           # width of the eddy-current path; null = magnet width (T31)
                   "eddy_correction": 1.0},
        "stator_core": {                    # soft magnetic composite. Loss per harmonic ellipse (T31):
                                            # R P_r + (1 - R)^2 P_a, P_a = k_h f B^alpha + k_e (f B)^2 + k_a (f B)^1.5
            "mu_r": 500.0,                  # initial relative permeability
            "saturation_T": 1.9,            # saturation polarisation; null = linear material
            "bh_curve": None,               # optional measured curve [[H in A/m, B in T], ...]
            "density_kg_m3": 7450.0,
            # Alternating and rotational loss of SOMALOY 500 (Guo, Zhu, Zhong, Wu, IEEE TMAG 39(5), 2003);
            # replace with the data of the grade used.
            "k_hysteresis": 0.1402,
            "alpha": 1.548,
            "k_eddy": 1.233e-5,
            "k_anomalous": 3.645e-4,
            "rotational": {"a1": 6.814, "a2": 1.054, "a3": 1.445, "saturation_T": 2.134,
                           "k_eddy": 2.303e-4, "k_anomalous": 0.0},     # null = alternating loss only
        },
        "rotor_iron": {"mu_r": 1000.0, "saturation_T": 2.1, "bh_curve": None,
                       "conductivity_S_m": 6.0e6,   # solid mild steel; null = no eddy loss
                       "density_kg_m3": 7850.0,
                       "eddy_width_mm": None,       # null = radial thickness of the rotor core
                       "eddy_correction": 1.0},
        "rotor_housing": {"mu_r": 1.0,
                          "conductivity_S_m": None, # e.g. 3.5e7 for aluminium; null = no eddy loss
                          "density_kg_m3": 2700.0,
                          "eddy_width_mm": None,
                          "eddy_correction": 1.0},
        "copper": {"resistivity_20C_ohm_m": 1.72e-8, "temp_coefficient_per_K": 0.00393},
    },
    "winding": {
        "span": None,                       # "concentrated" (tooth coils), "distributed" (overlapping coils) or
                                            # "ring" (TFM); null = the machine's own (docs/naming.md)
        "layers": 2,                        # coil sides per slot, 1 or 2 (slotted machines)
        "pitch_slots": None,                # coil span in slots; null = 1 (concentrated) or full pitch (distributed)
        "slot_class": "any",                # "any", "integral" or "fractional": allowed q = slots / (2 p phases)
        "conductor": "round_wire",          # "round_wire": many turns of enamelled wire. "strip": a stack of
                                            # flat copper rings (strip wound), few turns of a thick conductor
        "fill_factor": 0.45,                # round wire: copper area / coil cross-section
        "strip_fill_factor": 0.85,          # strip: copper area / coil cross-section
        "strip_min_thickness_mm": 0.3,      # strip: thinnest strip that can be wound; caps the number of layers
        "turns": None,                      # turns (layers of a strip coil) per phase. null = the most turns the
                                            # bus voltage allows (and, for a strip, the strip thickness)
        "wire": None,                       # "awg": turns and the AWG wire chosen together to fill the coil; null: any wire
        "coil_clearance_mm": 0.5,           # between coil and core
        "coil_margin_mm": 1.0,              # between coil and the pole-face plane, or the top of the I-bridge
    },
    "thermal": {
        "h_external_W_m2K": 25.0,           # outer surfaces to ambient air
        "h_air_gap_W_m2K": 60.0,            # across the air gap
        "h_mount_W_m2K": 150.0,             # stator mounting surface to the frame, treated as ambient
        "insulation_thickness_mm": 0.3,
        "insulation_conductivity_W_mK": 0.2,
        "winding_conductivity_W_mK": 0.8,   # effective, across the wire bundle
    },
    "objectives": ["max_torque", "min_losses", "min_ripple"],
    "optimizer": {"algorithm": "nsga2",     # registered optimizer: "nsga2", "random"
                  "population": 16, "generations": 8, "seed": 1, "jobs": 6,
                  "current_steps": 6},      # with load levels: further designs per geometry along current density
    "fidelity": {
        "level": "fast",                    # used during optimization
        "positions": 12,                    # rotor positions per half electrical period (multiple of 3)
        "staged": True,                     # every second position first; the rest only for designs that are
                                            # not already outside the limits
        "early_stop_margin": 0.1,           # total limit violation above which the first stage is final
        "load_levels": 0,                   # 0: one field solution per design. 2 to 5: a geometry is solved at
                                            # this many current densities and the others are interpolated
        "levels": {                         # cell size on the sliding surfaces = factor * air gap
            "fast": {"gap_cell_factor": 1.5, "size_max_mm": 6.0},   # chosen in ticket T08
            "fine": {"gap_cell_factor": 0.6, "size_max_mm": 6.0},
        },
    },
}



def _merge(defaults, user, where):
    out = copy.deepcopy(defaults)
    if not isinstance(user, dict):
        raise SpecError(f"'{where}' must be a JSON object.")
    for key, value in user.items():
        path = f"{where}.{key}" if where else key
        if key not in out:
            raise SpecError(f"Unknown key '{path}'.")
        if isinstance(out[key], dict) and value is not None:
            out[key] = _merge(out[key], value, path)
        else:
            out[key] = value
    return out


def _merge_fidelity(defaults, user):
    """Like _merge, but the user may define additional named levels."""
    user = dict(user) if isinstance(user, dict) else user
    levels = user.pop("levels", None) if isinstance(user, dict) else None
    out = _merge(defaults, user, "fidelity")
    if levels is not None:
        if not isinstance(levels, dict):
            raise SpecError("'fidelity.levels' must be a JSON object.")
        template = defaults["levels"]["fast"]
        for name, value in levels.items():
            out["levels"][name] = _merge(out["levels"].get(name, template), value, f"fidelity.levels.{name}")
    return out


def _number(spec, path, low=None, high=None, integer=False):
    node = spec
    for part in path.split("."):
        node = node[part]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        raise SpecError(f"'{path}' must be a number, got {node!r}.")
    if integer and int(node) != node:
        raise SpecError(f"'{path}' must be a whole number, got {node!r}.")
    if low is not None and node < low:
        raise SpecError(f"'{path}' must be at least {low}, got {node!r}.")
    if high is not None and node > high:
        raise SpecError(f"'{path}' must be at most {high}, got {node!r}.")
    return node


def _pair(spec, path, low=None, integer=False):
    node = spec
    for part in path.split("."):
        node = node[part]
    if (not isinstance(node, (list, tuple)) or len(node) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in node)):
        raise SpecError(f"'{path}' must be [min, max], got {node!r}.")
    if node[0] > node[1]:
        raise SpecError(f"'{path}': min {node[0]!r} is above max {node[1]!r}.")
    if low is not None and node[0] < low:
        raise SpecError(f"'{path}': min must be at least {low}, got {node[0]!r}.")
    if integer and any(int(v) != v for v in node):
        raise SpecError(f"'{path}' must hold whole numbers, got {node!r}.")
    return node


def _machine_class(machine):
    flux_path = machine.get("flux_path", DEFAULTS["machine"]["flux_path"])
    principle = machine.get("principle", DEFAULTS["machine"]["principle"])
    try:
        return registry.get("machine", f"{flux_path}/{principle}")
    except registry.RegistryError as error:
        raise SpecError(f"Unknown machine 'machine.flux_path' / 'machine.principle' = {flux_path}/{principle}. {error}")


def number(spec, path, low=None, high=None, integer=False):
    """Checks that a key of the specification is a number within limits; for machine plugins."""
    return _number(spec, path, low, high, integer)


def load_spec(source=None):
    """Returns the validated specification. `source` is a file path, a dictionary or None (defaults)."""
    if source is None:
        user = {}
    elif isinstance(source, dict):
        user = source
    else:
        with open(source) as f:
            user = json.load(f)

    spec = copy.deepcopy(DEFAULTS)
    if not isinstance(user, dict):
        raise SpecError("The specification must be a JSON object.")
    user = standard_spec(user)
    machine_class = _machine_class(user.get("machine") if isinstance(user.get("machine"), dict) else {})
    if machine_class.rotors:
        spec["machine"]["rotor"] = machine_class.rotors[0]
    spec["machine"].update(copy.deepcopy(machine_class().options()))
    for section, value in user.items():
        if section not in spec:
            raise SpecError(f"Unknown section '{section}'.")
        if section == "variables":
            if not isinstance(value, dict):
                raise SpecError("'variables' must be a JSON object.")
            spec[section] = copy.deepcopy(value)
        elif section == "objectives":
            spec[section] = value
        elif section == "fidelity":
            spec[section] = _merge_fidelity(spec[section], value)
        else:
            spec[section] = _merge(spec[section], value, section)

    machine = spec["machine"]
    if machine["rotor_placement"] not in ("inner", "outer"):
        raise SpecError(f"'machine.rotor_placement' must be 'inner' or 'outer', got {machine['rotor_placement']!r}.")
    if machine_class.rotors and machine.get("rotor") not in machine_class.rotors:
        raise SpecError(f"'machine.rotor' = {machine.get('rotor')!r} is not a rotor layout of "
                        f"{machine_class.key()}. Available: {', '.join(machine_class.rotors)}.")
    _number(spec, "machine.phases", low=1, integer=True)
    _number(spec, "machine.outer_diameter_mm", low=1e-6)
    _number(spec, "machine.stack_length_mm", low=1e-6)
    _number(spec, "machine.air_gap_mm", low=1e-3)
    _number(spec, "machine.bore_diameter_mm", low=0)
    if machine["bore_diameter_mm"] >= machine["outer_diameter_mm"]:
        raise SpecError("'machine.bore_diameter_mm' must be smaller than 'machine.outer_diameter_mm'.")

    winding = spec["winding"]
    spans = machine_class.winding_spans
    if winding["span"] is None:
        winding["span"] = spans[0]
    if winding["span"] not in spans:
        raise SpecError(f"'winding.span' of a {machine_class.key()} machine must be one of {spans}, got {winding['span']!r}.")
    if winding["wire"] not in (None, "awg"):
        raise SpecError(f"'winding.wire' must be null or 'awg', got {winding['wire']!r}.")
    if winding["layers"] not in (1, 2):
        raise SpecError(f"'winding.layers' must be 1 or 2, got {winding['layers']!r}.")
    if winding["pitch_slots"] is not None:
        _number(spec, "winding.pitch_slots", low=1, integer=True)
    if winding["slot_class"] not in ("any", "integral", "fractional"):
        raise SpecError(f"'winding.slot_class' must be 'any', 'integral' or 'fractional', got {winding['slot_class']!r}.")
    if winding["span"] in ("ring", "toroidal") and (winding["layers"] != 2 or winding["pitch_slots"] is not None
                                                    or winding["slot_class"] != "any"):
        raise SpecError(f"A {winding['span']} winding has no layers, pitch or slot class: leave 'winding.layers', "
                        "'winding.pitch_slots' and 'winding.slot_class' at their defaults.")

    machine_class().validate(spec)

    _number(spec, "operating_point.speed_rpm", low=1e-6)
    _number(spec, "operating_point.ambient_C", low=-273.0)

    _pair(spec, "limits.iron_thickness_mm", low=1e-6)
    _pair(spec, "limits.pole_pairs", low=1, integer=True)
    _pair(spec, "limits.bus_voltage_V", low=1e-6)
    _number(spec, "limits.min_core_gap_mm", low=0)
    if spec["limits"]["max_core_flux_density_T"] is not None:
        _number(spec, "limits.max_core_flux_density_T", low=1e-9)
    if spec["limits"]["max_torque_ripple_percent"] is not None:
        _number(spec, "limits.max_torque_ripple_percent", low=1e-6)
    for key in ("max_current_A", "max_current_density_A_mm2", "min_slot_width_mm", "min_coil_height_mm"):
        _number(spec, f"limits.{key}", low=1e-9)
    for key in ("max_winding_temp_C", "max_magnet_temp_C"):
        _number(spec, f"limits.{key}", low=spec["operating_point"]["ambient_C"])

    for name, value in spec["variables"].items():
        if isinstance(value, (list, tuple)):
            _pair(spec, f"variables.{name}")
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SpecError(f"'variables.{name}' must be a number or [min, max], got {value!r}.")
    spec["variables"] = standard_variables(spec)

    for path in ("materials.magnet.remanence_T", "materials.magnet.mu_r", "materials.stator_core.mu_r",
                 "materials.stator_core.density_kg_m3", "materials.stator_core.alpha",
                 "materials.rotor_iron.mu_r", "materials.rotor_housing.mu_r",
                 "materials.copper.resistivity_20C_ohm_m"):
        _number(spec, path, low=1e-12)
    for path in ("materials.stator_core.k_hysteresis", "materials.stator_core.k_eddy",
                 "materials.stator_core.k_anomalous", "materials.copper.temp_coefficient_per_K"):
        _number(spec, path, low=0)
    rotational = spec["materials"]["stator_core"]["rotational"]
    if rotational is not None:
        for key in ("a1", "a2", "a3", "saturation_T"):
            _number(spec, f"materials.stator_core.rotational.{key}", low=1e-9)
        for key in ("k_eddy", "k_anomalous"):
            _number(spec, f"materials.stator_core.rotational.{key}", low=0)
    for name in ("magnet", "rotor_iron", "rotor_housing"):
        if spec["materials"][name]["conductivity_S_m"] is not None:
            _number(spec, f"materials.{name}.conductivity_S_m", low=0)
        _number(spec, f"materials.{name}.density_kg_m3", low=1e-9)
        _number(spec, f"materials.{name}.eddy_correction", low=0)
        if spec["materials"][name]["eddy_width_mm"] is not None:
            _number(spec, f"materials.{name}.eddy_width_mm", low=1e-9)
    for name in ("stator_core", "rotor_iron"):
        material = spec["materials"][name]
        if material["saturation_T"] is not None:
            _number(spec, f"materials.{name}.saturation_T", low=0.1, high=3.0)
            if material["mu_r"] <= 1:
                raise SpecError(f"'materials.{name}.mu_r' must be above 1 for a saturating material.")
        curve = material["bh_curve"]
        if curve is not None:
            ok = (isinstance(curve, list) and len(curve) >= 3
                  and all(isinstance(p, (list, tuple)) and len(p) == 2
                          and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p) for p in curve))
            if not ok:
                raise SpecError(f"'materials.{name}.bh_curve' must be a list of at least three [H, B] pairs.")
            points = [(0.0, 0.0)] + [tuple(p) for p in curve if tuple(p) != (0, 0)]
            if any(h1 <= h0 or b1 <= b0 for (h0, b0), (h1, b1) in zip(points, points[1:])):
                raise SpecError(f"'materials.{name}.bh_curve' must rise strictly in both H and B, starting above [0, 0].")
    if spec["winding"]["conductor"] not in CONDUCTORS:
        raise SpecError(f"Unknown 'winding.conductor' {spec['winding']['conductor']!r}. Choose from {CONDUCTORS}.")
    _number(spec, "winding.fill_factor", low=0.01, high=1.0)
    _number(spec, "winding.strip_fill_factor", low=0.01, high=1.0)
    _number(spec, "winding.strip_min_thickness_mm", low=1e-3)
    if spec["winding"]["turns"] is not None:
        _number(spec, "winding.turns", low=1, integer=True)
    _number(spec, "winding.coil_clearance_mm", low=0)
    _number(spec, "winding.coil_margin_mm", low=spec["winding"]["coil_clearance_mm"])
    for key in spec["thermal"]:
        _number(spec, f"thermal.{key}", low=1e-9)

    objectives = spec["objectives"]
    if not isinstance(objectives, list) or not objectives:
        raise SpecError("'objectives' must be a non-empty list.")
    for name in objectives:
        if name not in OBJECTIVES:
            raise SpecError(f"Unknown objective {name!r} in 'objectives'. Choose from {OBJECTIVES}.")
    if len(set(objectives)) != len(objectives):
        raise SpecError("'objectives' lists an objective twice.")

    if spec["optimizer"]["algorithm"] not in registry.names("optimizer"):
        raise SpecError(f"Unknown 'optimizer.algorithm' {spec['optimizer']['algorithm']!r}. "
                        f"Registered: {registry.names('optimizer')}.")
    _number(spec, "optimizer.population", low=4, integer=True)
    _number(spec, "optimizer.generations", low=0, integer=True)
    _number(spec, "optimizer.seed", integer=True)
    _number(spec, "optimizer.jobs", low=1, integer=True)
    _number(spec, "optimizer.current_steps", low=0, integer=True)
    if not isinstance(spec["fidelity"]["staged"], bool):
        raise SpecError(f"'fidelity.staged' must be true or false, got {spec['fidelity']['staged']!r}.")
    _number(spec, "fidelity.early_stop_margin", low=0)
    levels = _number(spec, "fidelity.load_levels", low=0, high=5, integer=True)
    if levels == 1:
        raise SpecError("'fidelity.load_levels' must be 0 (off) or 2 to 5.")
    positions = _number(spec, "fidelity.positions", low=3, integer=True)
    if machine["phases"] == 3 and positions % 3:
        raise SpecError("'fidelity.positions' must be a multiple of 3 for a three-phase machine.")
    level = spec["fidelity"]["level"]
    if level not in spec["fidelity"]["levels"]:
        raise SpecError(f"'fidelity.level' = {level!r} is not defined in 'fidelity.levels'.")
    for name in spec["fidelity"]["levels"]:
        _number(spec, f"fidelity.levels.{name}.gap_cell_factor", low=0.1)
        _number(spec, f"fidelity.levels.{name}.size_max_mm", low=0.1)
    return spec


def copper_fill(spec):
    """Copper share of the coil cross-section for the conductor of the specification."""
    w = spec["winding"]
    return w["strip_fill_factor"] if w["conductor"] == "strip" else w["fill_factor"]
