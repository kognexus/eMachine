"""
The naming standard of docs/naming.md applied to specifications: old names are translated to the
standard names when a specification loads (`standard_machine`), and a loaded specification can be
written back in the old names (`legacy_spec`), so that the cache keys of runs made before the
standard (T43) stay the same and the regression data can be compared.

This module is the only place in emachine that knows the old names.
"""

import copy

from .errors import SpecError

#: old key in the section `machine` -> standard key
KEYS = {"family": "flux_path", "topology": "principle", "configuration": "rotor_placement",
        "stator_type": "stator", "rotor_type": "rotor", "sides": "arrangement"}

#: old value -> standard value, per standard key (old values are also accepted under the new keys)
VALUES = {
    "flux_path": {"raxial": "rafm"},
    "rotor_placement": {"inrunner": "inner", "outrunner": "outer"},
    "stator": {"u": "u_core", "ui": "ui_core", "c": "c_core", "e": "e_core", "z": "z_core",
               "cp": "claw_pole", "tr": "toothed_ring"},
    "rotor": {"flux_concentrating": "spoke", "axial": "axial_ring"},
    "arrangement": {1: "single", 2: "double_rotor"},
}

#: old topologies that are a principle with a rotor layout in the standard
PRINCIPLES = {"ipm": ("pmsm", "interior"), "pmasynrm": ("synrm", "flux_barrier_pm")}


def standard_machine(user_machine):
    """The section `machine` of a user's file with the standard names (a new dictionary)."""
    m = dict(user_machine)
    for old, new in KEYS.items():
        if old in m:
            value = m.pop(old)
            if new in m and _standard_value(new, m[new]) != _standard_value(new, value):
                raise SpecError(f"'machine.{old}' (old name) and 'machine.{new}' disagree: {value!r}, {m[new]!r}.")
            m.setdefault(new, value)
    principle = m.get("principle")
    if principle in PRINCIPLES:
        m["principle"], rotor = PRINCIPLES[principle]
        if "rotor" in m and _standard_value("rotor", m["rotor"]) != rotor:
            raise SpecError(f"'machine.topology' = {principle!r} means rotor {rotor!r}, "
                            f"but 'machine.rotor' is {m['rotor']!r}.")
        m["rotor"] = rotor
    for key in VALUES:
        if key in m:
            m[key] = _standard_value(key, m[key])
    return m


def standard_spec(user):
    """A user's specification with the standard names (a new dictionary; sections not copied deeply)."""
    user = dict(user)
    if isinstance(user.get("machine"), dict):
        machine = standard_machine(user["machine"])
        if "winding" in machine:                     # machine.winding (old) is winding.span
            span = machine.pop("winding")
            winding = dict(user.get("winding") or {})
            if winding.get("span") not in (None, span):
                raise SpecError(f"'machine.winding' (old name) and 'winding.span' disagree: {span!r}, {winding['span']!r}.")
            winding["span"] = span
            user["winding"] = winding
        user["machine"] = machine
    return user


def _standard_value(key, value):
    table = VALUES.get(key, {})
    try:
        return table.get(value, value)
    except TypeError:              # unhashable value: left for the validation to report
        return value


def legacy_machine(machine):
    """A loaded section `machine` with the names used before the standard (inverse of standard_machine)."""
    m = dict(machine)
    flux_path, principle, rotor = m.pop("flux_path"), m.pop("principle"), m.pop("rotor", None)
    m["family"] = flux_path
    m["topology"] = principle
    for (old_principle, (new_principle, layout)) in PRINCIPLES.items():
        if principle == new_principle and rotor == layout:
            m["topology"] = old_principle
    if flux_path == "tfm" and principle == "pmsm" and rotor is not None:
        m["rotor_type"] = {v: k for k, v in VALUES["rotor"].items()}.get(rotor, rotor)
    if "stator" in m:
        stator = m.pop("stator")
        if flux_path == "tfm":
            m["stator_type"] = {v: k for k, v in VALUES["stator"].items()}.get(stator, stator)
    if "rotor_placement" in m:
        m["configuration"] = {v: k for k, v in VALUES["rotor_placement"].items()}[m.pop("rotor_placement")]
    if "arrangement" in m:
        m["sides"] = {v: k for k, v in VALUES["arrangement"].items()}.get(m.pop("arrangement"))
    return m


#: keys of the section `winding` added by the standard (T46), with the values of windings before it
NEW_WINDING_KEYS = {"layers": 2, "pitch_slots": None, "slot_class": "any", "wire": None}


def legacy_spec(spec):
    """A loaded specification with the names used before the standard (a new dictionary). Keys added
    by the standard are left out where they have the value that was implied before."""
    out = copy.deepcopy(spec)
    out["machine"] = legacy_machine(out["machine"])
    winding = out.get("winding")
    if winding is not None and "span" in winding:
        span = winding.pop("span")
        if span != "ring":
            out["machine"]["winding"] = span
        for key, implied in NEW_WINDING_KEYS.items():
            if winding.get(key, implied) == implied:
                winding.pop(key, None)
    return out


#: machine keys left out of a cache key when they have these values, so that the caches of runs
#: made before the machine plugins (T34) stay valid
DEFAULT_MACHINE = {"family": "tfm", "topology": "pmsm"}


#: machine options added after the cache keys were fixed (T71 to T73) and their defaults. At the default
#: they are left out of a cache key, so the caches of older runs stay valid.
LATER_OPTIONS = {"halbach_segments": 2, "rotor_magnet_slots": False, "rotor_skew_el_deg": 0.0,
                 "rotor_skew_steps": 1, "ring_tooth_tips": False}


def cache_view(spec):
    """The sections of a spec as cache keys see them: old names, the default machine left out."""
    out = legacy_spec(spec) if "machine" in spec else copy.deepcopy(spec)
    machine = out.get("machine")
    if machine is not None:
        for key, default in LATER_OPTIONS.items():
            if key in machine and machine[key] == default:
                del machine[key]
    if machine is not None and all(machine.get(k) == v for k, v in DEFAULT_MACHINE.items()):
        out["machine"] = {k: v for k, v in machine.items() if k not in DEFAULT_MACHINE}
    return out


# ---------------------------------------------------------------- design variables (T49, T50)
#
# Ratios became lengths and arcs (docs/parameters.md). Designs, seeds and run files written before
# are converted when they are read; a cache key sees the TFM variables in the old names, so the
# caches of older TFM runs stay valid (the RFM stator changed: it fills the outer diameter now).

#: old name -> (new name, factor): converted by a factor (or by the spec, for the SRM rotor)
SCALED_VARIABLES = {"tooth_span": ("tooth_arc_el_deg", 180.0), "magnet_arc_ratio": ("magnet_arc_el_deg", 180.0),
                    "rotor_tooth_ratio": ("rotor_tooth_arc_el_deg", 180.0),
                    "rotor_pole_arc_ratio": ("rotor_pole_arc_deg", None)}
#: old ratios of the slotted stator, converted from a whole design only
STATOR_RATIOS = ("bore_ratio", "slot_depth_ratio", "tooth_ratio")
#: old ratios with no conversion: the rotors were drawn only, no run used them
DROPPED_VARIABLES = {"magnet_width_ratio": "magnet_length_mm", "insulation_ratio": "barrier_width_mm",
                     "magnet_fill_ratio": "magnet_width_mm"}
#: the claw tip of the claw pole before it was a variable: this share of the root, not below the minimum iron
CLAW_TIP_SHARE = 0.5


def _factor(spec, factor):
    return 360.0 / spec["machine"]["rotor_poles"] if factor is None else factor


def standard_values(spec, values):
    """A design (variable name -> value) in the names of docs/parameters.md (a new dictionary).
    Values written in the old names are converted to the same machine."""
    v = dict(values)
    m = spec["machine"]
    for old, (new, factor) in SCALED_VARIABLES.items():
        if old in v:
            v[new] = v.pop(old) * _factor(spec, factor)      # an old name given explicitly wins
    v.pop("stator_pole_arc_ratio", None)           # the SRM stator pole is the tooth: derived
    for old, new in DROPPED_VARIABLES.items():
        if old in v:
            raise SpecError(f"The design variable '{old}' was replaced by '{new}' (docs/parameters.md); "
                            f"this design cannot be converted, give '{new}'.")
    if any(k in v for k in STATOR_RATIOS):
        missing = [k for k in STATOR_RATIOS if k not in v]
        if missing:
            raise SpecError(f"An old design needs all of {STATOR_RATIOS} to be converted; missing {missing}.")
        r_out = m["outer_diameter_mm"] / 2
        r_bore = v.pop("bore_ratio") * r_out
        height = v.pop("slot_depth_ratio") * (r_out - r_bore)
        pitch = 2 * 3.141592653589793 * r_bore / m["slots"]
        v["slot_height_mm"] = height
        v["slot_width_mm"] = pitch - v.pop("tooth_ratio") * pitch
        v.pop("yoke_mm", None)
        v["yoke_height_mm"] = r_out - r_bore - height     # the stator fills the outer diameter now
    if "yoke_mm" in v:
        v["yoke_height_mm"] = v.pop("yoke_mm")
    if m.get("stator") == "claw_pole" and "claw_root_height_mm" in v and "claw_tip_height_mm" not in v:
        v["claw_tip_height_mm"] = max(spec["limits"]["iron_thickness_mm"][0], CLAW_TIP_SHARE * v["claw_root_height_mm"])
    return v


def legacy_values(spec, values):
    """A TFM design in the variable names of the runs before T50, for cache keys (inverse of
    standard_values); other machines unchanged."""
    if spec["machine"]["flux_path"] != "tfm":
        return dict(values)
    v = dict(values)
    for old, (new, factor) in SCALED_VARIABLES.items():
        if new in v:
            v[old] = v.pop(new) / _factor(spec, factor)
    if "claw_tip_height_mm" in v and "claw_root_height_mm" in v:
        rule = max(spec["limits"]["iron_thickness_mm"][0], CLAW_TIP_SHARE * v["claw_root_height_mm"])
        if v["claw_tip_height_mm"] == rule:
            v.pop("claw_tip_height_mm")
    return v


def standard_variables(spec):
    """The section `variables` of a spec (bounds or fixed values) in the standard names: bounds
    converted by a factor where the old variable was a fixed multiple; a SpecError naming the new
    variables for ratios that need the whole design."""
    out, given = {}, dict(spec["variables"])
    fixed = [given.get(k) for k in STATOR_RATIOS]
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in fixed):
        # a spec of a run before T49 that fixed the stator: the same stator in lengths
        stator = standard_values(spec, {k: given.pop(k) for k in STATOR_RATIOS + ("yoke_mm",) if k in given})
        out.update({k: stator[k] for k in ("slot_height_mm", "slot_width_mm", "yoke_height_mm")})
    for name, value in given.items():
        if name in SCALED_VARIABLES:
            new, factor = SCALED_VARIABLES[name]
            k = _factor(spec, factor)
            out[new] = [x * k for x in value] if isinstance(value, (list, tuple)) else value * k
        elif name in STATOR_RATIOS:
            raise SpecError(f"'variables.{name}' was replaced by 'slot_height_mm', 'slot_width_mm' and "
                            "'yoke_height_mm' (lengths in mm, docs/parameters.md).")
        elif name in DROPPED_VARIABLES:
            raise SpecError(f"'variables.{name}' was replaced by '{DROPPED_VARIABLES[name]}' (docs/parameters.md).")
        elif name == "stator_pole_arc_ratio":
            raise SpecError("'variables.stator_pole_arc_ratio' was dropped: the stator pole of the SRM is "
                            "the tooth, set by 'slot_width_mm' (docs/parameters.md).")
        elif name == "yoke_mm":
            out["yoke_height_mm"] = value
        else:
            out[name] = value
    return out
