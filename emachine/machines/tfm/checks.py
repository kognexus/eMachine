"""
Fast geometric feasibility and limit checks, run before any meshing.

Every check compares one number with one limit. A violated check has a positive, normalised
violation that grows linearly with the distance from the limit, so an optimizer can rank
infeasible designs and move towards feasibility.
"""

import math

from emachine.core.types import Check

from . import design
from .options import rotor_code, stator_code

_at_least, _at_most = Check.at_least, Check.at_most


def check(spec, values):
    """List of checks (emachine.core.types.Check)."""
    m, lim = spec["machine"], spec["limits"]
    d = design.derived(spec, values)
    lo, hi = lim["iron_thickness_mm"]
    p = d["pole_pairs"]
    ui = stator_code(m) == "ui"
    cp = stator_code(m) == "cp"
    tr = stator_code(m) == "tr"
    out = []

    out.append(_at_least("pole_pairs_min", p, lim["pole_pairs"][0]))
    out.append(_at_most("pole_pairs_max", p, lim["pole_pairs"][1]))

    # ---- iron thickness, in every direction
    for name, value in (("iron_leg", d["leg_width"]), ("iron_yoke", d["yoke_height"]),
                        ("iron_core_thickness", d["core_thickness"])):
        out.append(_at_least(name + "_min", value, lo))
        out.append(_at_most(name + "_max", value, hi))
    if ui:
        out.append(_at_least("iron_bridge_min", d["bridge_height"], lo))
        out.append(_at_most("iron_bridge_max", d["bridge_height"], hi))
    if cp:
        out.append(_at_least("iron_claw_root_min", d["claw_root_height"], lo))
        out.append(_at_most("iron_claw_root_max", d["claw_root_height"], hi))
        out.append(_at_least("iron_claw_tip_min", d["claw_tip_height"], lo))
        # The claw must cover part of the width, and its tip must clear the opposite wall.
        out.append(_at_least("claw_tip_gap", d["claw_tip_gap"], 2 * m["air_gap_mm"]))
        out.append(_at_most("claw_tip_gap_max", d["claw_tip_gap"], 0.8 * d["slot_width"], max(d["slot_width"], 1.0)))
    if tr:
        # The teeth stand on the side walls, which stay at least the minimum iron thickness high.
        out.append(_at_most("ring_tooth_height", d["ring_tooth_height"], d["slot_height"] - lo, max(d["slot_height"], 1.0)))
    out.append(_at_least("iron_rotor_min", d["rotor_iron"], lo))
    if d["outrunner"]:
        out.append(_at_most("iron_rotor_max", d["rotor_iron"], hi))

    # ---- room for the coil
    out.append(_at_least("slot_width", d["slot_width"], lim["min_slot_width_mm"]))
    out.append(_at_least("coil_height", d["coil_height"], lim["min_coil_height_mm"]))
    out.append(_at_least("coil_width", d["coil_width"], 0.5))

    # ---- radii
    radius = d["outer_radius"]
    out.append(_at_least("stator_radius", d["stator_radius"], 0.1 * radius, radius))
    if d["outrunner"]:
        out.append(_at_least("bore_clearance", d["stator_far_radius"], d["bore_radius"], radius))

    # ---- neighbouring stator cores must not touch
    gap = lim["min_core_gap_mm"]
    # A pole shift moves every second core towards its neighbour by this arc at the air gap.
    shift_arc = abs(math.radians(d["pole_shift_deg"])) * max(d["stator_radius"], 0.0)
    t = d["core_thickness"] + shift_arc
    if d["pole_shift_deg"]:
        out.append(_at_most("pole_shift_needs_even_pole_pairs", p % 2, 0))
    if tr:
        # Toothed ring: one tooth per pole pair on each wall, on a continuous ring. Neighbouring teeth
        # of a wall are closest at the air gap.
        room = 2 * max(d["stator_radius"], 0.0) * math.sin(math.pi / p)
        out.append(_at_least("tooth_gap", room - t, gap, max(t, 1.0)))
        if d["ring_tip_overhang"] > 0:
            # T73: tips over the slot. Staggered teeth: the tips of the two walls interleave one pole
            # pitch apart; aligned teeth: the two tips of a pair face each other across the slot.
            if m["ring_staggered_teeth"]:
                room = 2 * max(d["stator_radius"], 0.0) * math.sin(math.pi / (2 * p))
                out.append(_at_least("tip_gap", room - t, gap, max(t, 1.0)))
                out.append(_at_most("tip_overhang", d["ring_tip_overhang"], d["slot_width"] - gap, max(d["slot_width"], 1.0)))
            else:
                out.append(_at_most("tip_overhang", 2 * d["ring_tip_overhang"], d["slot_width"] - gap,
                                    max(d["slot_width"], 1.0)))
            out.append(_at_most("tip_height", d["ring_tip_height"], d["ring_tooth_height"] - 0.5,
                                max(d["ring_tooth_height"], 1.0)))
    elif cp:
        # Claw-pole frames sit on every pole pitch. Their side walls and yokes may merge into rings,
        # as in a classic claw-pole stator, but neighbouring claws carry opposite poles and must stay
        # apart. For an inner stator they are closest at the top of the claws.
        radius_claws = d["stator_radius"] - d["claw_root_height"] if d["outrunner"] else d["stator_radius"]
        room = 2 * max(radius_claws, 0.0) * math.sin(math.pi / (2 * p))
        out.append(_at_least("claw_overlap", room - t, gap, max(t, 1.0)))
    elif d["outrunner"]:
        # U-cores converge towards the axis: tightest at their inner end, one pole pair apart.
        room = 2 * max(d["stator_far_radius"], 0.0) * math.sin(math.pi / p)
        out.append(_at_least("core_overlap", room - t, gap, max(t, 1.0)))
        if ui:
            # I-bridge and U-core are one pole apart: tightest at the inner end of the bridge.
            room = 2 * max(d["stator_radius"] - d["bridge_height"], 0.0) * math.sin(math.pi / (2 * p))
            out.append(_at_least("bridge_overlap", room - t, gap, max(t, 1.0)))
    else:
        # Cores diverge outwards: tightest at the pole faces.
        spacing = math.pi / (2 * p) if ui else math.pi / p
        room = 2 * max(d["stator_radius"], 0.0) * math.sin(spacing)
        out.append(_at_least("core_overlap", room - t, gap, max(t, 1.0)))

    # ---- magnets
    if rotor_code(m) == "flux_concentrating":
        inner = d["rotor_gap_radius"] if d["outrunner"] else d["rotor_gap_radius"] - d["magnet"]
        room = max(inner, 0.0) * math.sin(math.pi / (2 * p))
        out.append(_at_most("spoke_magnet_width", values["magnet_thickness_mm"], 0.9 * room, max(room, 1.0)))
    return out


def violations(results):
    """Only the checks that failed."""
    return [r for r in results if r.violation > 0]


def total_violation(results):
    return sum(r.violation for r in results)


def is_feasible(results):
    return total_violation(results) == 0
