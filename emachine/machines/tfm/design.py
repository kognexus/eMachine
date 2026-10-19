"""
Design variables and their mapping to a complete motor description.

The optimizer works on the variables listed by `variables(spec)`. `to_parameters` turns one set
of values into the parameter dictionary used by the mesher and the solver, in such a way that
the macro inputs of the specification (outer diameter, stack length, phases) always hold.
`derived` returns the geometric quantities that the other models need.
"""

import math

from emachine.spec import SpecError, copper_fill
from emachine.spec.names import standard_values

from .options import outer_rotor, rotor_code, stator_code

BRIDGE_TOP_RATIO = 0.8      # I-bridge top width / slot width (shape of the chamfer, docs/parameters.md)
HALBACH_SEGMENTS = 2        # magnet segments per pole


def phase_width(spec):
    """Axial width available to one phase, in mm."""
    m = spec["machine"]
    return (m["stack_length_mm"] - (m["phases"] - 1) * m["phase_spacing_mm"]) / m["phases"]


def variables(spec):
    """Ordered design variables: list of {name, kind ('int' or 'real'), low, high}."""
    m, lim = spec["machine"], spec["limits"]
    iron_lo, iron_hi = lim["iron_thickness_mm"]
    width = phase_width(spec)
    if width <= 0:
        raise SpecError("The phase spacing uses up the whole stack length.")
    leg_hi = min(iron_hi, (width - lim["min_slot_width_mm"]) / 2)
    if leg_hi < iron_lo:
        raise SpecError(f"A phase is only {width:.2f} mm wide: two legs of {iron_lo} mm and a slot of "
                        f"{lim['min_slot_width_mm']} mm do not fit. Increase the stack length.")
    radius = m["outer_diameter_mm"] / 2
    # Radial room between bore and outer diameter. A machine needs an air gap, a magnet, rotor iron,
    # a yoke and a slot in it, so the slot can take at most what the thinnest of the others leaves.
    room = radius - m["bore_diameter_mm"] / 2
    slot_hi = min(0.45 * radius, room - m["air_gap_mm"] - 1.5 - 2 * iron_lo)
    if slot_hi < 4.0:
        raise SpecError(f"There is no room for a machine between the bore diameter ({m['bore_diameter_mm']} mm) "
                        f"and the outer diameter ({m['outer_diameter_mm']} mm).")
    out = [
        {"name": "pole_pairs", "kind": "int", "low": lim["pole_pairs"][0], "high": lim["pole_pairs"][1]},
        # circumferential width of a core at the gap, in electrical degrees (180: the whole pole pitch)
        {"name": "tooth_arc_el_deg", "kind": "real", "low": 90.0, "high": 171.0},
        {"name": "leg_width_mm", "kind": "real", "low": iron_lo, "high": leg_hi},
        {"name": "slot_height_mm", "kind": "real", "low": 4.0, "high": slot_hi},
        {"name": "yoke_height_mm", "kind": "real", "low": iron_lo, "high": iron_hi},
        {"name": "magnet_thickness_mm", "kind": "real", "low": 1.5, "high": 6.0},
        {"name": "current_density_A_mm2", "kind": "real", "low": 1.0,
         "high": max(1.0, lim["max_current_density_A_mm2"])},
    ]
    if outer_rotor(m):
        out.append({"name": "rotor_iron_mm", "kind": "real", "low": iron_lo, "high": iron_hi})
    if stator_code(m) == "ui":
        out.append({"name": "bridge_height_mm", "kind": "real", "low": iron_lo, "high": iron_hi})
    if stator_code(m) == "tr":
        # Height of the teeth above the continuous side walls; kept below the slot height by a check.
        out.append({"name": "ring_tooth_height_mm", "kind": "real", "low": 1.0, "high": slot_hi})
    if stator_code(m) == "cp":
        slot_w_max = width - 2 * iron_lo
        out.append({"name": "claw_root_height_mm", "kind": "real", "low": iron_lo, "high": iron_hi})
        out.append({"name": "claw_tip_height_mm", "kind": "real", "low": iron_lo, "high": iron_hi})
        out.append({"name": "claw_tip_gap_mm", "kind": "real", "low": 1.0, "high": max(1.0, 0.6 * slot_w_max)})
    if rotor_code(m) in ("surface", "axial"):     # axial: arc of the disc teeth; magnet_thickness is their height
        out.append({"name": "magnet_arc_el_deg", "kind": "real", "low": 108.0 if rotor_code(m) == "surface" else 72.0,
                    "high": 180.0})
    if rotor_code(m) == "flux_concentrating":
        out.append({"name": "magnet_height_mm", "kind": "real", "low": 4.0, "high": max(4.0, 0.3 * radius)})
    if m.get("rotor_magnet_slots"):
        # How far each magnet pocket reaches from its side wall over the coil slot (T71). Half the
        # widest slot closes the gap between the pockets; the check keeps a web between them.
        out.append({"name": "magnet_overhang_mm", "kind": "real", "low": 0.0,
                    "high": max(0.0, (width - 2 * iron_lo) / 2)})
    if m.get("ring_tooth_tips"):
        # T73: axial reach of each tooth tip over the coil slot, and its radial thickness.
        out.append({"name": "ring_tip_overhang_mm", "kind": "real", "low": 0.3,
                    "high": max(0.3, width - 2 * iron_lo - lim["min_core_gap_mm"])})
        out.append({"name": "ring_tip_height_mm", "kind": "real", "low": 0.5, "high": max(0.5, iron_hi)})

    known = {v["name"] for v in out}
    for name, value in spec["variables"].items():
        if name not in known:
            raise SpecError(f"'variables.{name}' is not a design variable of this machine. Available: {sorted(known)}.")
        var = next(v for v in out if v["name"] == name)
        low, high = (value, value) if not isinstance(value, (list, tuple)) else value
        var["low"], var["high"] = low, high
    for var in out:
        if var["kind"] == "int":
            var["low"], var["high"] = int(math.ceil(var["low"])), int(math.floor(var["high"]))
        if var["low"] > var["high"]:
            raise SpecError(f"Design variable '{var['name']}' has an empty range [{var['low']}, {var['high']}].")
    return out


def clip(spec, values):
    """Values rounded (integers) and clipped to their bounds, as a new dictionary."""
    values, out = standard_values(spec, values), {}
    for var in variables(spec):
        value = values[var["name"]]
        if var["kind"] == "int":
            value = int(round(value))
        out[var["name"]] = min(max(value, var["low"]), var["high"])
    return out


def to_vector(spec, values):
    return [values[v["name"]] for v in variables(spec)]


def to_values(spec, vector):
    return clip(spec, {v["name"]: x for v, x in zip(variables(spec), vector)})


def derived(spec, values):
    """Geometric and electrical quantities implied by a design. Lengths in mm unless named otherwise."""
    values = standard_values(spec, values)
    m, w = spec["machine"], spec["winding"]
    outrunner = outer_rotor(m)
    ui = stator_code(m) == "ui"
    cp = stator_code(m) == "cp"
    fc = rotor_code(m) == "flux_concentrating"
    p = int(values["pole_pairs"])
    gap = m["air_gap_mm"]
    width = phase_width(spec)
    leg = values["leg_width_mm"]
    slot_w = width - 2 * leg
    slot_h = values["slot_height_mm"]
    yoke = values["yoke_height_mm"]
    # Claw pole: the claws lie between the air gap and the coil window.
    claw_root = values["claw_root_height_mm"] if cp else 0.0
    claw_tip = values["claw_tip_height_mm"] if cp else 0.0
    claw_tip_gap = values["claw_tip_gap_mm"] if cp else 0.0
    window_top = claw_root + slot_h          # height of the top of the coil window above the air gap
    height = window_top + yoke
    magnet = values["magnet_height_mm"] if fc else values["magnet_thickness_mm"]
    r_out = m["outer_diameter_mm"] / 2
    bore = m["bore_diameter_mm"] / 2

    if outrunner:
        rotor_iron = values["rotor_iron_mm"]
        rotor_gap_radius = r_out - rotor_iron - magnet      # inner radius of the magnet ring
        stator_radius = rotor_gap_radius - gap              # pole-face radius of the stator
        stator_far = stator_radius - height                 # inner end of the stator cores
        sign = -1.0
    else:
        stator_radius = r_out - height
        rotor_gap_radius = stator_radius - gap              # outer radius of the magnet ring
        rotor_iron = rotor_gap_radius - magnet - bore       # rotor core from the shaft to the magnets
        stator_far = r_out
        sign = 1.0

    clearance = w["coil_clearance_mm"]
    bridge = values["bridge_height_mm"] if ui else 0.0
    tips = stator_code(m) == "tr" and m.get("ring_tooth_tips", False)
    tip_h = values["ring_tip_height_mm"] if tips else 0.0
    tip_over = values["ring_tip_overhang_mm"] if tips else 0.0
    # Tooth tips (T73) hang over the slot next to the air gap, so the coil sits below them.
    coil_h = slot_h - 2 * clearance if cp else slot_h - clearance - w["coil_margin_mm"] - bridge - tip_h
    coil_w = slot_w - 2 * clearance
    coil_area = max(coil_h, 0.0) * max(coil_w, 0.0)
    # Same placement as the mesher: the coil sits against the yoke end of the slot.
    r_a = stator_radius + sign * (window_top - clearance - coil_h)
    r_b = stator_radius + sign * (window_top - clearance)
    coil_r0, coil_r1 = min(r_a, r_b), max(r_a, r_b)
    coil_mean_radius = 0.5 * (coil_r0 + coil_r1)

    tau = math.pi * stator_radius / p if stator_radius > 0 else 0.0
    span = values["tooth_arc_el_deg"] / 180.0          # share of the pole pitch
    thickness = span * tau
    # Share of the circumference taken by stator iron, and iron area facing the rotor (one phase).
    if cp:
        coverage = span
        pole_faces = 2 * p * thickness * (width - claw_tip_gap)
    else:
        coverage = span / 2.0
        pole_faces = p * thickness * 2.0 * (leg + tip_over) + (p * thickness * width if ui else 0.0)
    ampere_turns_rms = values["current_density_A_mm2"] * coil_area * copper_fill(spec)
    return {
        "outrunner": outrunner,
        "pole_pairs": p,
        "phase_width": width,
        "slot_width": slot_w,
        "slot_height": slot_h,
        "leg_width": leg,
        "yoke_height": yoke,
        "stator_height": height,
        "bridge_height": bridge,
        "claw_root_height": claw_root,
        "claw_tip_height": claw_tip,
        "claw_tip_gap": claw_tip_gap,
        "window_top": window_top,
        "cores_per_pole_pair": 2 if (cp or ui) else 1,
        "ring_tooth_height": values["ring_tooth_height_mm"] if stator_code(m) == "tr" else 0.0,
        "ring_tip_height": tip_h,
        "ring_tip_overhang": tip_over,
        "pole_shift_deg": m["pole_shift_el_deg"] / p,           # mechanical angle
        "core_coverage": coverage,
        "pole_face_area_mm2": pole_faces,
        "stator_radius": stator_radius,
        "stator_far_radius": stator_far,
        "rotor_gap_radius": rotor_gap_radius,
        "rotor_iron": rotor_iron,
        "magnet": magnet,
        "pole_pitch": tau,
        "core_thickness": thickness,
        "coil_height": coil_h,
        "coil_width": coil_w,
        "coil_area_mm2": coil_area,
        "coil_r0": coil_r0,
        "coil_r1": coil_r1,
        "coil_mean_radius": coil_mean_radius,
        "turn_length_mm": 2 * math.pi * coil_mean_radius,
        "ampere_turns_rms": ampere_turns_rms,
        "ampere_turns_peak": math.sqrt(2) * ampere_turns_rms,
        "electrical_frequency_Hz": p * spec["operating_point"]["speed_rpm"] / 60.0,
        "outer_radius": r_out,
        "bore_radius": bore,
        # Innermost solid surface: the inner end of the stator cores (outrunner) or the shaft (inrunner).
        "inner_diameter": 2 * stator_far if outrunner else 2 * bore,
    }


def to_parameters(spec, values, level=None):
    """Complete parameter dictionary for emachine mesh and emachine solve."""
    values = clip(spec, values)
    d = derived(spec, values)
    m, mat, w = spec["machine"], spec["materials"], spec["winding"]
    fidelity = spec["fidelity"]["levels"][level or spec["fidelity"]["level"]]

    stator = {
        "core_type": stator_code(m),
        "air_gap_radius": d["stator_radius"],
        "pole_pairs": d["pole_pairs"],
        "inner_stator": d["outrunner"],
        "trim_pole_faces": True,
        "tooth_span": values["tooth_arc_el_deg"] / 180.0,
        "leg_width": d["leg_width"],
        "slot_width": d["slot_width"],
        "slot_height": d["slot_height"],
        "yoke_height": d["yoke_height"],
        "bridge_height": d["bridge_height"] if stator_code(m) == "ui" else 1.0,
        "bridge_top_ratio": BRIDGE_TOP_RATIO,
        "include_coil": True,
        "coil_height": d["coil_height"],
        "coil_clearance": w["coil_clearance_mm"],
    }
    if m["pole_shift_el_deg"]:
        stator["pole_shift_deg"] = d["pole_shift_deg"]
    if stator_code(m) == "cp":
        stator.update({"claw_root_height": d["claw_root_height"], "claw_tip_height": d["claw_tip_height"],
                       "claw_tip_gap": d["claw_tip_gap"]})
    if stator_code(m) == "tr":
        stator.update({"ring_tooth_height": d["ring_tooth_height"], "ring_arched_valleys": m["ring_arched_valleys"],
                       "ring_staggered_teeth": m["ring_staggered_teeth"]})
        if m.get("ring_tooth_tips"):
            stator.update({"ring_tip_overhang": d["ring_tip_overhang"], "ring_tip_height": d["ring_tip_height"]})
    rotor = {
        "configuration": "outrunner" if outer_rotor(m) else "inrunner",
        "type": rotor_code(m),
        "stack_length": d["phase_width"],
        "poles": 2 * d["pole_pairs"],
        "segments_per_pole": int(m.get("halbach_segments", HALBACH_SEGMENTS)),
        "magnet_rows": 2,                   # one row under each leg
        "row_gap": d["slot_width"],
        "alternate_rows": True,
    }
    if stator_code(m) == "cp" or m["ring_staggered_teeth"]:
        # The claws span the whole width, or the two walls face opposite poles already: one magnet row.
        rotor.update({"magnet_rows": 1, "row_gap": 0.0, "alternate_rows": False})
    if m.get("rotor_magnet_slots"):
        # T71: one pocket over each side wall, same polarity (the walls face opposite poles already),
        # reaching magnet_overhang_mm over the coil slot. Between the pockets: a non-magnetic web.
        web = d["slot_width"] - 2 * values["magnet_overhang_mm"]
        if web > 1e-6:
            rotor.update({"magnet_rows": 2, "row_gap": web, "alternate_rows": False})
    if m.get("rotor_skew_steps", 1) > 1:
        # T72: step skew inside each phase; the angle is mechanical in the parameter file.
        rotor.update({"skew_steps": int(m["rotor_skew_steps"]), "skew_deg": m["rotor_skew_el_deg"] / d["pole_pairs"]})
    if rotor_code(m) == "axial":          # two toothed discs as wide as the legs, ring magnet as long as the slot
        rotor.update({"magnet_rows": 1, "row_gap": d["slot_width"], "alternate_rows": False})
    if rotor_code(m) == "flux_concentrating":
        rotor["fc_magnet_height"] = values["magnet_height_mm"]
        rotor["fc_magnet_width"] = values["magnet_thickness_mm"]
    else:
        rotor["magnet_thickness"] = values["magnet_thickness_mm"]
    if rotor_code(m) in ("surface", "axial"):
        rotor["magnet_arc_ratio"] = values["magnet_arc_el_deg"] / 180.0
    if d["outrunner"]:
        rotor["inner_diameter"] = 2 * d["rotor_gap_radius"]
        rotor["outer_diameter"] = m["outer_diameter_mm"]
    else:
        rotor["outer_diameter"] = 2 * d["rotor_gap_radius"]
        rotor["shaft_diameter"] = m["bore_diameter_mm"]

    return {
        "stator": stator,
        "rotor": rotor,
        "mesh": {
            "gap_cell": fidelity["gap_cell_factor"] * m["air_gap_mm"],
            "size_max": fidelity["size_max_mm"],
        },
        "analysis": {
            "magnet_remanence_T": mat["magnet"]["remanence_T"],
            "magnet_mu_r": mat["magnet"]["mu_r"],
            "stator_core_mu_r": mat["stator_core"]["mu_r"],
            "rotor_iron_mu_r": mat["rotor_iron"]["mu_r"],
            "rotor_housing_mu_r": mat["rotor_housing"]["mu_r"],
            "stator_core_saturation_T": mat["stator_core"]["saturation_T"],
            "stator_core_bh_curve": mat["stator_core"]["bh_curve"],
            "rotor_iron_saturation_T": mat["rotor_iron"]["saturation_T"],
            "rotor_iron_bh_curve": mat["rotor_iron"]["bh_curve"],
            "coil_turns": 1,                # solved in ampere-turns; turns are chosen afterwards
            "coil_current_A": d["ampere_turns_peak"],
        },
        "design": dict(values),
    }


def from_parameters(spec, parameters):
    """Design variable values recovered from a parameter dictionary made by `to_parameters`."""
    m = spec["machine"]
    stator, rotor = parameters["stator"], parameters["rotor"]
    fc = rotor_code(m) == "flux_concentrating"
    values = {
        "pole_pairs": int(stator["pole_pairs"]),
        "tooth_arc_el_deg": stator["tooth_span"] * 180.0,
        "leg_width_mm": stator["leg_width"],
        "slot_height_mm": stator["slot_height"],
        "yoke_height_mm": stator["yoke_height"],
        "magnet_thickness_mm": rotor["fc_magnet_width"] if fc else rotor["magnet_thickness"],
        "current_density_A_mm2": parameters["design"]["current_density_A_mm2"],
    }
    magnet = rotor["fc_magnet_height"] if fc else rotor["magnet_thickness"]
    if outer_rotor(m):
        values["rotor_iron_mm"] = rotor["outer_diameter"] / 2 - rotor["inner_diameter"] / 2 - magnet
    if stator_code(m) == "ui":
        values["bridge_height_mm"] = stator["bridge_height"]
    if stator_code(m) == "tr":
        values["ring_tooth_height_mm"] = stator["ring_tooth_height"]
    if stator_code(m) == "cp":
        values["claw_root_height_mm"] = stator["claw_root_height"]
        values["claw_tip_gap_mm"] = stator["claw_tip_gap"]
        values["claw_tip_height_mm"] = stator["claw_tip_height"]
    if rotor_code(m) in ("surface", "axial"):
        values["magnet_arc_el_deg"] = rotor["magnet_arc_ratio"] * 180.0
    if m.get("rotor_magnet_slots"):
        web = rotor["row_gap"] if int(rotor["magnet_rows"]) == 2 else 0.0
        values["magnet_overhang_mm"] = (stator["slot_width"] - web) / 2
    if m.get("ring_tooth_tips"):
        values["ring_tip_overhang_mm"] = stator["ring_tip_overhang"]
        values["ring_tip_height_mm"] = stator["ring_tip_height"]
    if fc:
        values["magnet_height_mm"] = rotor["fc_magnet_height"]
    return values
