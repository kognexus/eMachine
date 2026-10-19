"""
Radial flux topologies of the catalogue (T59, T63). Dimensions in mm; the envelope gives the outer
radius R (stator, or rotor of an outer-rotor machine), the bore radius r_b (the ILM-E's hollow rotor)
and the active stack length L.

Stator variables (shares chosen so that most random designs can be drawn):
    combo          index into the slot/pole list of the topology
    gap_radius_mm  radius of the stator surface at the air gap
    air_gap_mm     0.3 to 1.0 (user)
    tooth_share    tooth body width / slot pitch at the gap
    yoke_share     yoke height / tooth width (FSCW: about 0.5 to 1, the flux of one tooth splits in two)
    tip_height_mm, opening_share (slot opening / slot width at the gap)
"""

import math

from .. import winding_layout
from .base import (FSCW, ISW_Q1, Checks, Topology, cogging_period_el_rad, fscw_sides, phase_sequence, srm_sides,
                   var)

MIN_IRON = 1.2           # thinnest iron section (tooth, yoke, bridge-free iron), mm
MIN_SLOT = 1.0           # narrowest slot, mm
MIN_OPENING = 0.8        # narrowest slot opening, mm (segmented or needle-wound stator)


def stator_variables(gap_low, gap_high, opening=(0.15, 0.6)):
    return [var("gap_radius_mm", gap_low, gap_high, unit="mm"), var("air_gap_mm", 0.3, 1.0, unit="mm"),
            var("tooth_share", 0.3, 0.75), var("yoke_share", 0.45, 1.3), var("tip_height_mm", 0.3, 1.5, unit="mm"),
            var("opening_share", opening[0], opening[1])]


def slotted_stator(checks, slots, sides, r_gap, r_back, facing, values, stack, notches=0, notch_width=0.0,
                   notch_depth=0.0, tooth_width=None, open_slots=False, span_slots=1):
    """A slotted stator ring between the gap surface r_gap and the back radius r_back (the outer radius
    for facing "in", the bore for "out"). Returns (part, winding data)."""
    pitch = 2 * math.pi * r_gap / slots
    w_t = tooth_width if tooth_width is not None else values["tooth_share"] * pitch
    yoke = max(MIN_IRON, values["yoke_share"] * w_t) if "yoke_share" in values else values["yoke_mm"]
    tip = 0.0 if open_slots else values["tip_height_mm"]
    depth = abs(r_back - r_gap) - yoke
    checks.at_least("tooth_width", w_t, MIN_IRON)
    checks.at_least("slot_depth", depth - tip, 2.0)
    if facing == "in":
        r_slot0, r_slot1 = r_gap + tip, r_gap + depth
        part = {"role": "stator", "type": "slotted", "r_in": r_gap, "r_out": r_back, "facing": "in"}
    else:
        r_slot0, r_slot1 = r_gap - depth, r_gap - tip
        part = {"role": "stator", "type": "slotted", "r_in": r_back, "r_out": r_gap, "facing": "out"}
    narrow = 2 * math.pi * min(r_slot0, r_slot1) / slots - w_t
    checks.at_least("slot_width", narrow, MIN_SLOT)
    slot_gap = pitch - w_t
    opening = slot_gap if open_slots else values["opening_share"] * slot_gap
    if not open_slots:
        checks.at_least("slot_opening", opening, MIN_OPENING)
    # slot area: ring sector of the slot pitch less the tooth body
    area = (math.pi * (max(r_slot0, r_slot1) ** 2 - min(r_slot0, r_slot1) ** 2) / slots - w_t * abs(r_slot1 - r_slot0))
    side = area / 2
    w_c = max(area / max(abs(r_slot1 - r_slot0), 1e-6) / 2, 0.1)      # mean width of a coil side
    if span_slots == 1:
        turn = 2 * (stack + w_t) + math.pi * w_c
        overhang = w_c + 1.0
    else:
        r_mid = (r_slot0 + r_slot1) / 2
        turn = 2 * stack + 2 * 1.2 * span_slots * 2 * math.pi * r_mid / slots + math.pi * w_c
        overhang = 0.5 * span_slots * 2 * math.pi * r_mid / slots
    part.update({"slots": slots, "slot_depth": depth, "tooth_width": w_t, "tip_height": tip, "opening": opening,
                 "notches": notches, "notch_width": notch_width, "notch_depth": notch_depth, "sides": sides})
    dims = {"slot_pitch_mm": pitch, "tooth_width_mm": w_t, "yoke_mm": yoke, "slot_depth_mm": depth, "tip_height_mm": tip,
            "slot_opening_mm": opening, "slot_area_mm2": area, "coil_side_width_mm": w_c}
    return part, {"side_area_mm2": side, "turn_length_mm": turn, "end_overhang_mm": overhang, "dims": dims}


class RadialFSCW(Topology):
    """Common to radial machines with a slotted stator and a slot-star winding (inner rotor by default)."""

    flux_path = "rfm"
    principle = "pm"
    combos = FSCW
    outer_rotor = False
    span = "concentrated"
    layers = 2

    def gap_range(self, env):
        R, rb = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2
        if self.outer_rotor:
            return rb + 6.0, R - 4.0
        return max(rb + 5.0, 0.45 * R), R - 5.0        # a small shaft (T69) does not open the range below 0.45 R

    def variables(self, env):
        lo, hi = self.gap_range(env)
        return [var("combo", 0, len(self.combos) - 1, "int")] + stator_variables(lo, hi) + self.rotor_variables(env)

    def rotor_variables(self, env):
        return []

    def poles_of(self, values):
        return self.combos[int(values["combo"])]

    def design(self, env, values):
        checks = Checks()
        R, rb, L = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2, env["stack_length_mm"]
        slots, poles = self.poles_of(values)
        p = poles // 2
        span = self.span if (slots, poles) not in ISW_Q1 else "distributed"
        layers = self.layers if span == "concentrated" else 1
        sides, layout, desc = fscw_sides(slots, p, layers, span)
        g = values["air_gap_mm"]
        r_g = values["gap_radius_mm"]
        if self.outer_rotor:
            stator, wind = slotted_stator(checks, slots, sides, r_g, rb, "out", values, L,
                                          span_slots=1 if span == "concentrated" else layout.pitch)
            rotor_in, rotor_out = r_g + g, R
        else:
            stator, wind = slotted_stator(checks, slots, sides, r_g, R, "in", values, L,
                                          span_slots=1 if span == "concentrated" else layout.pitch)
            rotor_in, rotor_out = rb, r_g - g
        rotor, extra = self.rotor_part(checks, env, values, rotor_in, rotor_out, poles, layout)
        checks.raise_if_any()
        parts = [stator, rotor] if self.outer_rotor else [rotor, stator]
        pe = extra.get("pe", p)
        skew_e = values.get("skew_share", 0.0) * cogging_period_el_rad(slots, extra.get("rotor_poles_for_cogging", poles), pe)
        params = {"kind": "radial", "parts": parts, "bore_radius": rb, "stack_length": L, "electrical_pole_pairs": pe,
                  "rotor_eddy_width_mm": [0.35, 0.35, extra.get("magnet_eddy_width", 5.0)], "mesh": self.mesh(env, g)}
        dims = dict(wind["dims"], gap_radius_mm=r_g, air_gap_mm=g, rotor_inner_mm=rotor_in, rotor_outer_mm=rotor_out,
                    **extra.get("dims", {}))
        return self.base_design(
            key=self.key, principle=self.principle, params=params, pe=pe, known_axis=getattr(self, "known_axis", False), coils_per_phase=len(layout.coils) // 3,
            side_area_mm2=wind["side_area_mm2"] * (2 if layers == 1 else 1), turn_length_mm=wind["turn_length_mm"],
            end_overhang_mm=wind["end_overhang_mm"], active_length_mm=L, sequence_hint=phase_sequence(layout),
            skew_e_rad=skew_e, skew_factor=math.sin(skew_e / 2) / (skew_e / 2) if skew_e > 1e-9 else 1.0,
            winding={"slots": slots, "poles": poles, **desc}, dims=dims, ferrite_magnets=extra.get("ferrite", False),
            axial_length_mm=L + 2 * wind["end_overhang_mm"], outer_diameter_mm=2 * R)

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        raise NotImplementedError


def magnet_variables():
    return [var("magnet_thickness_mm", 1.5, 5.0, unit="mm"), var("magnet_arc_share", 0.65, 1.0),
            var("skew_share", 0.0, 1.0)]


class SPMInner(RadialFSCW):
    known_axis = True
    key = "rfm_spm_in"
    title = "Radial-flux surface PM, inner rotor, FSCW"
    summary = ("The ILM-E's own topology: magnets on a laminated rotor inside a slotted stator with tooth coils. "
               "Slot/pole combination, split ratio, tooth, yoke, tips, magnet arc and skew are optimized.")
    sources = "afpm_tfm.md (FSCW combos, magnet arc), ripple_methods.md (skew, LCM rule)"

    def rotor_variables(self, env):
        return magnet_variables()

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        hm = values["magnet_thickness_mm"]
        checks.at_least("rotor_yoke", r_out - hm - r_in, MIN_IRON + 0.8)
        part = {"role": "rotor", "type": "surface", "r_in": r_in, "r_out": r_out, "facing": "out", "poles": poles,
                "offset_deg": winding_layout.flux_axis_deg(layout, 0), "magnet_thickness": hm,
                "magnet_arc": values["magnet_arc_share"], "segments": 1}
        return part, {"dims": {"magnet_thickness_mm": hm, "magnet_arc_el_deg": 180 * values["magnet_arc_share"]},
                      "magnet_eddy_width": values["magnet_arc_share"] * math.pi * r_out / poles}


class HalbachInner(SPMInner):
    key = "rfm_halbach_in"
    title = "Radial-flux Halbach PM, inner rotor, FSCW"
    summary = "Segmented Halbach magnets (2 to 4 per pole) concentrate the field on the gap side; sinusoidal gap field."
    sources = "afpm_tfm.md (quasi-Halbach +12 % torque density), ripple_methods.md"

    def rotor_variables(self, env):
        return [var("magnet_thickness_mm", 1.5, 5.0, unit="mm"), var("segments", 2, 4, "int"), var("skew_share", 0.0, 1.0)]

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        hm = values["magnet_thickness_mm"]
        checks.at_least("rotor_yoke", r_out - hm - r_in, MIN_IRON)
        part = {"role": "rotor", "type": "halbach", "r_in": r_in, "r_out": r_out, "facing": "out", "poles": poles,
                "offset_deg": winding_layout.flux_axis_deg(layout, 0), "magnet_thickness": hm,
                "segments": int(values["segments"])}
        return part, {"dims": {"magnet_thickness_mm": hm, "halbach_segments": int(values["segments"])},
                      "magnet_eddy_width": math.pi * r_out / poles / int(values["segments"])}


class SPMOuter(SPMInner):
    key = "rfm_spm_out"
    title = "Radial-flux surface PM, outer rotor, FSCW"
    summary = ("Stator inside on the 52 mm hub, magnets on the inside of a rotor ring at the outer diameter: "
               "larger air-gap radius for the same envelope.")
    outer_rotor = True

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        hm = values["magnet_thickness_mm"]
        checks.at_least("rotor_yoke", r_out - r_in - hm, MIN_IRON + 0.8)
        part = {"role": "rotor", "type": "surface", "r_in": r_in, "r_out": r_out, "facing": "in", "poles": poles,
                "offset_deg": winding_layout.flux_axis_deg(layout, 0), "magnet_thickness": hm,
                "magnet_arc": values["magnet_arc_share"], "segments": 1}
        return part, {"dims": {"magnet_thickness_mm": hm, "magnet_arc_el_deg": 180 * values["magnet_arc_share"]},
                      "magnet_eddy_width": values["magnet_arc_share"] * math.pi * r_in / poles}


class ConsequentInner(SPMInner):
    key = "rfm_cpm_in"
    title = "Radial-flux consequent-pole PM, inner rotor, FSCW"
    summary = "Magnets on every second pole, iron poles between: half the magnet mass; even harmonics to watch."
    sources = "afpm_tfm.md (BKHZKL4S consequent pole: -22 % torque, -38 % ripple)"

    def rotor_variables(self, env):
        return [var("magnet_thickness_mm", 1.5, 5.0, unit="mm"), var("magnet_arc_share", 0.7, 1.0),
                var("iron_arc_share", 0.4, 0.9), var("skew_share", 0.0, 1.0)]

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        hm = values["magnet_thickness_mm"]
        checks.at_least("rotor_yoke", r_out - hm - r_in, MIN_IRON + 0.8)
        part = {"role": "rotor", "type": "consequent", "r_in": r_in, "r_out": r_out, "facing": "out", "poles": poles,
                "offset_deg": winding_layout.flux_axis_deg(layout, 0), "magnet_thickness": hm,
                "magnet_arc": values["magnet_arc_share"], "iron_arc": values["iron_arc_share"]}
        return part, {"dims": {"magnet_thickness_mm": hm, "magnet_arc_el_deg": 180 * values["magnet_arc_share"],
                               "iron_arc_el_deg": 180 * values["iron_arc_share"]},
                      "magnet_eddy_width": values["magnet_arc_share"] * math.pi * r_out / poles}


def v_fits(part, r_in, poles):
    """Violations of an interior V: bars and pockets inside the rotor, within their pole, iron below."""
    from ..section2d.radial import v_bar_corners, v_pocket
    out = []
    r_out = part["r_out"]
    half_pole = math.pi / poles
    for side in (1, -1):
        corners, _, _ = v_bar_corners(part, side)
        for x, y in (v_pocket(part, side) or [])[1:3]:
            r = math.hypot(x, y)
            out.append(("pocket_pole_width", abs(math.atan2(y, x)) * r - (half_pole * r - 0.4)))
        for x, y in corners:
            r = math.hypot(x, y)
            out.append(("v_outside", r - (r_out - part["bridge"] - 0.2)))
            out.append(("v_inner_iron", (r_in + MIN_IRON + 0.5) - r))
            out.append(("v_pole_width", abs(math.atan2(y, x)) * r - (half_pole * r - 0.6)))
    return [(n, v) for n, v in out if v > 0]


class IPMV(RadialFSCW):
    key = "rfm_ipm_v"
    title = "Radial-flux interior PM (V magnets), FSCW"
    summary = "Two bars per pole in a V, air pockets to the bridge: reluctance torque adds to the magnet torque."
    sources = "synrm_ipm.md (YT3SF56W Prius V proportions: 8 poles, V depth about 0.4 of the rotor radius; MTPA)"
    #: few poles leave room for V bars (T69): q = 1 integer slot and q = 1/2 windings, then FSCW up to 16 poles
    combos = ISW_Q1[:3] + [(12, 8), (18, 12)] + [c for c in FSCW if c[1] <= 16]

    def rotor_variables(self, env):
        return [var("magnet_thickness_mm", 1.2, 3.5, unit="mm"), var("bar_share", 0.4, 0.98),
                var("v_angle_deg", 110.0, 180.0, unit="deg"), var("v_depth_share", 0.0, 0.8),
                var("bridge_mm", 0.4, 1.0, unit="mm"), var("skew_share", 0.0, 1.0)]

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        t = values["magnet_thickness_mm"]
        least = t + values["bridge_mm"] + 0.4                 # the bar's thickness must fit under the bridge
        room = min(r_out - r_in - MIN_IRON - 1.0, 0.45 * r_out) - least    # deeper apexes leave no pole width for bars
        depth = least + values["v_depth_share"] * max(0.0, room)
        part = {"role": "rotor", "type": "interior_v", "r_in": r_in, "r_out": r_out, "facing": "out", "poles": poles,
                "offset_deg": winding_layout.flux_axis_deg(layout, 0), "magnet_thickness": t, "magnet_length": 0.5,
                "v_angle_deg": values["v_angle_deg"], "v_depth": depth, "bridge": values["bridge_mm"], "post": 0.6}
        if v_fits(part, r_in, poles):
            checks.at_least("v_bar_room", 0.0, 1.0)
            return part, {}
        lo, hi = 0.5, 25.0                      # the longest bar that fits
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if not v_fits(dict(part, magnet_length=mid), r_in, poles) else (lo, mid)
        length = values["bar_share"] * lo
        checks.at_least("v_bar_length", length, 1.5)
        part["magnet_length"] = length
        return part, {"dims": {"magnet_thickness_mm": t, "magnet_length_mm": length, "v_angle_deg": values["v_angle_deg"],
                               "v_depth_mm": depth, "bridge_mm": values["bridge_mm"]},
                      "magnet_eddy_width": length}


class Spoke(RadialFSCW):
    key = "rfm_spoke"
    title = "Radial-flux spoke PM (flux concentrating) on a non-magnetic hub, FSCW"
    summary = ("Tangentially magnetised magnets between iron poles concentrate the flux of two magnets in each pole; "
               "the poles stand on a non-magnetic hub (stainless steel or aluminium, dovetails) so the magnets are not "
               "short-circuited below.")
    sources = "synrm_ipm.md, afpm_tfm.md (flux concentration at high pole numbers); T68"
    combos = [c for c in FSCW if 14 <= c[1] <= 24]

    def rotor_variables(self, env):
        return [var("spoke_width_mm", 1.2, 4.0, unit="mm"), var("spoke_depth_share", 0.5, 1.0),
                var("bridge_mm", 0.0, 0.8, unit="mm"), var("skew_share", 0.0, 1.0)]

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        """The spokes reach from the bridge down a share of the rotor depth (above a 2 mm hub ring at least);
        below them the hub is non-magnetic, so the iron poles stand apart."""
        room = r_out - values["bridge_mm"] - r_in - 2.0
        depth = values["spoke_depth_share"] * room
        r0 = r_out - values["bridge_mm"] - depth
        pole_width = 2 * math.pi * r0 / poles - values["spoke_width_mm"]
        checks.at_least("pole_iron", pole_width, MIN_IRON)
        checks.at_least("spoke_depth", depth, 2.0)
        part = {"role": "rotor", "type": "spoke", "r_in": r_in, "r_out": r_out, "facing": "out", "poles": poles,
                "offset_deg": winding_layout.flux_axis_deg(layout, 0), "spoke_width": values["spoke_width_mm"],
                "spoke_inner": r0, "bridge": values["bridge_mm"], "pocket": 0.0, "hub_radius": r0}
        return part, {"dims": {"spoke_width_mm": values["spoke_width_mm"], "spoke_depth_mm": depth,
                               "bridge_mm": values["bridge_mm"], "hub_radius_mm": r0,
                               "iron_pole_width_at_hub_mm": pole_width,
                               "iron_pole_width_at_gap_mm": 2 * math.pi * r_out / poles - values["spoke_width_mm"]},
                      "magnet_eddy_width": depth}


class SynRM(RadialFSCW):
    key = "rfm_synrm"
    title = "Synchronous reluctance (flux barriers), FSCW or q = 1"
    principle = "synrm"
    summary = "Rotor of flux barriers, no magnets: torque from the difference of the d and q inductances."
    sources = "synrm_ipm.md (Vagati rules, insulation ratio 0.4-0.5, ribs 0.3-0.5 mm, FSCW penalty)"
    combos = ISW_Q1 + [(12, 8), (18, 12)] + [c for c in FSCW if c[1] <= 14]

    def rotor_variables(self, env):
        return [var("barriers", 1, 4, "int"), var("insulation", 0.25, 0.6), var("rib_mm", 0.3, 0.8, unit="mm"),
                var("skew_share", 0.0, 1.0)]

    def poles_of(self, values):
        return self.combos[int(values["combo"])]

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        part = {"role": "rotor", "type": "flux_barrier", "r_in": r_in, "r_out": r_out, "facing": "out", "poles": poles,
                "offset_deg": 0.0, "barriers": int(values["barriers"]), "insulation": values["insulation"],
                "rib": values["rib_mm"], "inner_ring": 1.5}
        from ..section2d.radial import barrier_circles
        _, rings = barrier_circles(part)
        width = rings[0][1] - rings[0][0]
        checks.at_least("barrier_width", width, 0.5, 1.0)
        pitch = (rings[1][0] - rings[0][0]) if len(rings) > 1 else 2 * width
        checks.at_least("barrier_iron", pitch - width, MIN_IRON, 1.0)
        return part, {"dims": {"barriers": int(values["barriers"]), "insulation": values["insulation"],
                               "barrier_width_mm": width, "rib_mm": values["rib_mm"]}}


class PMaSynRM(SynRM):
    key = "rfm_pmasynrm"
    title = "PM-assisted SynRM (ferrite in the barriers), FSCW or q = 1"
    principle = "pmasynrm"
    summary = "Flux-barrier rotor with ferrite magnets in the barriers: higher power factor and torque."
    sources = "synrm_ipm.md (ferrite +30 % torque, power factor 0.65 -> 0.85-0.93; 7NBX9CHG, 4E8HKLAJ, I4LZ4ACL)"

    def rotor_variables(self, env):
        return super().rotor_variables(env) + [var("pm_width_mm", 2.0, 14.0, unit="mm")]

    def rotor_part(self, checks, env, values, r_in, r_out, poles, layout):
        part, extra = super().rotor_part(checks, env, values, r_in, r_out, poles, layout)
        part.update({"type": "flux_barrier_pm", "pm_width": values["pm_width_mm"], "pm_remanence": env["ferrite_remanence_T"],
                     "pm_mu_r": 1.1})
        extra["dims"]["pm_width_mm"] = values["pm_width_mm"]
        extra["ferrite"] = True
        return part, extra


class SRM(RadialFSCW):
    key = "rfm_srm"
    title = "Switched reluctance, radial, 3 phases"
    principle = "srm"
    summary = "Salient stator and rotor poles, tooth coils, unipolar currents switched phase by phase."
    sources = "srm.md (pole arcs after Lawrenson, beta_r 0.5-2 deg above beta_s, split ratio 0.58-0.71, 12/14 and 12/8)"
    #: 6/4 and 6/8 leave no slot in the 16.5 mm between bore and outer radius (poles too wide for their yokes)
    combos = [(12, 8), (12, 16), (18, 12), (24, 16)]

    def variables(self, env):
        lo, hi = self.gap_range(env)
        return [var("combo", 0, len(self.combos) - 1, "int"), var("gap_radius_mm", lo, hi, unit="mm"),
                var("air_gap_mm", 0.3, 1.0, unit="mm"), var("stator_arc_share", 0.0, 1.0), var("rotor_arc_ratio", 1.0, 1.35),
                var("yoke_share", 0.5, 1.0), var("rotor_pole_height_share", 0.3, 0.9)]

    @staticmethod
    def pole_arcs(ns, nr, values):
        """Stator arc from the stroke (Lawrenson's least arc) up to 1.6 strokes, the rotor arc a ratio of it."""
        stroke = 360.0 / (3 * nr)
        beta_s = stroke * (1.0 + 0.6 * values["stator_arc_share"])
        return stroke, beta_s, values["rotor_arc_ratio"] * beta_s

    def design(self, env, values):
        checks = Checks()
        R, rb, L = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2, env["stack_length_mm"]
        ns, nr = self.combos[int(values["combo"])]
        g, r_g = values["air_gap_mm"], values["gap_radius_mm"]
        stroke, beta_s, beta_r = self.pole_arcs(ns, nr, values)
        checks.at_most("pole_arcs", beta_s + beta_r, 0.95 * 360.0 / nr, stroke)
        w_t = 2 * r_g * math.sin(math.radians(beta_s) / 2)
        sides = srm_sides(ns)
        stator, wind = slotted_stator(checks, ns, sides, r_g, R, "in", values, L, tooth_width=w_t, open_slots=True)
        r_out = r_g - g
        depth = r_out - rb
        yoke_min = max(MIN_IRON, 0.5 * w_t)
        h_r = values["rotor_pole_height_share"] * (depth - yoke_min)
        checks.at_least("rotor_pole_height", h_r, 1.0)
        checks.raise_if_any()
        rotor = {"role": "rotor", "type": "salient", "r_in": rb, "r_out": r_out, "facing": "out", "poles": nr,
                 "offset_deg": 180.0 / ns, "pole_arc_deg": beta_r, "pole_height": h_r}
        params = {"kind": "radial", "parts": [rotor, stator], "bore_radius": rb, "stack_length": L,
                  "electrical_pole_pairs": nr, "rotor_eddy_width_mm": [0.35, 0.35, 1.0], "mesh": self.mesh(env, g)}
        dims = dict(wind["dims"], gap_radius_mm=r_g, air_gap_mm=g, stator_pole_arc_deg=beta_s, rotor_pole_arc_deg=beta_r,
                    rotor_pole_height_mm=h_r)
        return self.base_design(key=self.key, principle="srm", params=params, pe=nr, rotor_poles=nr, coils_per_phase=ns // 3,
                                side_area_mm2=wind["side_area_mm2"], turn_length_mm=wind["turn_length_mm"],
                                end_overhang_mm=wind["end_overhang_mm"], active_length_mm=L,
                                winding={"slots": ns, "poles": nr, "label": f"SRM {ns}/{nr}, tooth coils"}, dims=dims,
                                axial_length_mm=L + 2 * wind["end_overhang_mm"], outer_diameter_mm=2 * R)


#: Vernier combinations: winding slots Q, modulators per tooth k, winding pole pairs P_w (FSCW of Q slots,
#: q = Q / (6 P_w) between 1/4 and 1/2), rotor pole pairs P_r = Q k - P_w (afpm_tfm.md: gear ratio P_r / P_w >= 3)
VERNIER = [(6, 3, 2), (12, 2, 5), (12, 2, 4), (12, 3, 4), (12, 3, 5), (9, 2, 4), (18, 2, 8), (6, 2, 2)]


def vernier_poles(q, k, pw):
    return q * k - pw


class Vernier(RadialFSCW):
    key = "rfm_vernier"
    title = "Radial-flux PM vernier (split teeth), inner rotor"
    principle = "vernier"
    summary = ("Split-tooth stator: every tooth ends in k modulators, so Q k teeth modulate the field of the "
               "magnets (P_r pole pairs) into the winding's P_w pole pairs: magnetic gearing at the gap.")
    sources = "afpm_tfm.md (P_r = N_s - P_w, gear ratio >= 5, pole pitch / gap >= 8, power factor 0.6-0.8)"
    combos = VERNIER

    def variables(self, env):
        lo, hi = self.gap_range(env)
        return [var("combo", 0, len(self.combos) - 1, "int"), var("gap_radius_mm", lo, hi, unit="mm"),
                var("air_gap_mm", 0.3, 1.0, unit="mm"), var("tooth_share", 0.25, 0.6), var("yoke_share", 0.45, 1.2),
                var("tip_height_mm", 1.0, 3.0, unit="mm"), var("modulator_gap_share", 0.3, 0.6),
                var("magnet_thickness_mm", 1.5, 4.0, unit="mm"), var("magnet_arc_share", 0.65, 1.0),
                var("skew_share", 0.0, 1.0)]

    def design(self, env, values):
        checks = Checks()
        R, rb, L = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2, env["stack_length_mm"]
        q, k, pw = self.combos[int(values["combo"])]
        pr = vernier_poles(q, k, pw)
        g, r_g = values["air_gap_mm"], values["gap_radius_mm"]
        sides, layout, desc = fscw_sides(q, pw, 2)
        tau_m = 2 * math.pi * r_g / (q * k)
        gap_w = values["modulator_gap_share"] * tau_m
        vals = dict(values, opening_share=1.0)
        stator, wind = slotted_stator(checks, q, sides, r_g, R, "in", vals, L, notches=k - 1, notch_width=gap_w,
                                      notch_depth=values["tip_height_mm"])
        stator["opening"] = gap_w
        checks.at_least("modulator_width", tau_m - gap_w, MIN_IRON)
        checks.at_least("slot_opening", gap_w, MIN_OPENING)
        r_out = r_g - g
        hm = values["magnet_thickness_mm"]
        checks.at_least("rotor_yoke", r_out - hm - rb, MIN_IRON + 0.8)
        checks.at_least("pole_pitch_over_gap", math.pi * r_out / pr / g, 4.0, 4.0)
        checks.raise_if_any()
        rotor = {"role": "rotor", "type": "surface", "r_in": rb, "r_out": r_out, "facing": "out", "poles": 2 * pr,
                 "offset_deg": 0.0, "magnet_thickness": hm, "magnet_arc": values["magnet_arc_share"], "segments": 1}
        skew_e = values["skew_share"] * cogging_period_el_rad(q * k, 2 * pr, pr)
        params = {"kind": "radial", "parts": [rotor, stator], "bore_radius": rb, "stack_length": L,
                  "electrical_pole_pairs": pr, "rotor_eddy_width_mm": [0.35, 0.35, values["magnet_arc_share"] * math.pi * r_out / (2 * pr)],
                  "mesh": self.mesh(env, g)}
        dims = dict(wind["dims"], gap_radius_mm=r_g, air_gap_mm=g, modulators=q * k, modulator_gap_mm=gap_w,
                    magnet_thickness_mm=hm, magnet_arc_el_deg=180 * values["magnet_arc_share"], rotor_pole_pairs=pr,
                    winding_pole_pairs=pw, gear_ratio=pr / pw)
        return self.base_design(key=self.key, principle="vernier", params=params, pe=pr, coils_per_phase=len(layout.coils) // 3,
                                side_area_mm2=wind["side_area_mm2"], turn_length_mm=wind["turn_length_mm"],
                                end_overhang_mm=wind["end_overhang_mm"], active_length_mm=L, sequence_hint=-phase_sequence(layout),
                                skew_e_rad=skew_e, skew_factor=math.sin(skew_e / 2) / (skew_e / 2) if skew_e > 1e-9 else 1.0,
                                winding={"slots": q, "poles": 2 * pw, "rotor_poles": 2 * pr, **desc}, dims=dims,
                                axial_length_mm=L + 2 * wind["end_overhang_mm"], outer_diameter_mm=2 * R)


class DualStatorVernier(Vernier):
    key = "rfm_ds_vernier"
    title = "Dual-stator PM vernier: outer and inner split-tooth stators, magnet ring between"
    summary = ("A ring of radially magnetised magnets between two split-tooth stators (outer stator facing in, "
               "inner stator facing out on the hub); both windings in series; two air gaps.")
    sources = "afpm_tfm.md (vernier rules; dual-stator vernier, 54GF545H)"

    def variables(self, env):
        R, rb = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2
        return [var("combo", 0, len(self.combos) - 1, "int"), var("ring_radius_mm", rb + 6.0, R - 5.0, unit="mm"),
                var("air_gap_mm", 0.3, 1.0, unit="mm"), var("magnet_thickness_mm", 1.5, 4.0, unit="mm"),
                var("magnet_arc_share", 0.65, 1.0), var("outer_tooth_share", 0.25, 0.6), var("inner_tooth_share", 0.25, 0.6),
                var("yoke_room_share", 0.2, 0.5), var("tip_height_mm", 0.5, 2.0, unit="mm"),
                var("modulator_gap_share", 0.3, 0.6), var("skew_share", 0.0, 1.0)]

    def design(self, env, values):
        """Two stators share 16.5 mm of radial room with the ring and two gaps: each yoke is a share of its
        stator's room (a share of the wide vernier tooth would leave no slot)."""
        checks = Checks()
        R, rb, L = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2, env["stack_length_mm"]
        q, k, pw = self.combos[int(values["combo"])]
        pr = vernier_poles(q, k, pw)
        g, hm = values["air_gap_mm"], values["magnet_thickness_mm"]
        r_ring_in = values["ring_radius_mm"] - hm / 2
        r_ring_out = r_ring_in + hm
        r_go, r_gi = r_ring_out + g, r_ring_in - g
        sides, layout, desc = fscw_sides(q, pw, 2)
        parts, side_total, turn_total, coils = [], 0.0, 0.0, 0
        dims = {}
        for name, r_gap, r_back, facing, share in (("inner", r_gi, rb, "out", values["inner_tooth_share"]),
                                                   ("outer", r_go, R, "in", values["outer_tooth_share"])):
            tau_m = 2 * math.pi * r_gap / (q * k)
            gap_w = values["modulator_gap_share"] * tau_m
            vals = {kk: v for kk, v in values.items() if kk != "yoke_room_share"}
            vals.update(opening_share=1.0, tooth_share=share,
                        yoke_mm=max(MIN_IRON, values["yoke_room_share"] * abs(r_back - r_gap)))
            st, wind = slotted_stator(checks, q, sides, r_gap, r_back, facing, vals, L, notches=k - 1, notch_width=gap_w,
                                      notch_depth=values["tip_height_mm"])
            st["opening"] = gap_w
            checks.at_least(f"{name}_modulator_width", tau_m - gap_w, MIN_IRON)
            checks.at_least(f"{name}_slot_opening", gap_w, MIN_OPENING)
            parts.append(st)
            dims.update({f"{name}_{k2}": v for k2, v in wind["dims"].items()})
            side_total += wind["side_area_mm2"]
            turn_total += wind["turn_length_mm"]
            coils += len(layout.coils) // 3
        checks.raise_if_any()
        rotor = {"role": "rotor", "type": "through", "r_in": r_ring_in, "r_out": r_ring_out, "facing": "both",
                 "poles": 2 * pr, "offset_deg": 0.0, "magnet_arc": values["magnet_arc_share"]}
        parts = [parts[0], rotor, parts[1]]
        skew_e = values["skew_share"] * cogging_period_el_rad(q * k, 2 * pr, pr)
        params = {"kind": "radial", "parts": parts, "bore_radius": rb, "stack_length": L, "electrical_pole_pairs": pr,
                  "rotor_eddy_width_mm": [0.35, 0.35, values["magnet_arc_share"] * math.pi * r_ring_out / (2 * pr)],
                  "mesh": self.mesh(env, g)}
        dims.update(ring_inner_mm=r_ring_in, ring_outer_mm=r_ring_out, air_gap_mm=g, magnet_thickness_mm=hm,
                    rotor_pole_pairs=pr, winding_pole_pairs=pw, gear_ratio=pr / pw)
        # both stators in series: the coils of a phase are those of both; side area and turn length averaged
        return self.base_design(key=self.key, principle="vernier", params=params, pe=pr, coils_per_phase=coils,
                                side_area_mm2=side_total / 2, turn_length_mm=turn_total / 2,
                                end_overhang_mm=max(dims.get("inner_coil_side_width_mm", 1), dims.get("outer_coil_side_width_mm", 1)) + 1,
                                active_length_mm=L, sequence_hint=-phase_sequence(layout), skew_e_rad=skew_e,
                                skew_factor=math.sin(skew_e / 2) / (skew_e / 2) if skew_e > 1e-9 else 1.0,
                                winding={"slots": q, "poles": 2 * pw, "rotor_poles": 2 * pr, "stators": 2, **desc}, dims=dims,
                                axial_length_mm=L + 2 * (max(dims.get("inner_coil_side_width_mm", 1), dims.get("outer_coil_side_width_mm", 1)) + 1),
                                outer_diameter_mm=2 * R)


class DualRotorSPM(RadialFSCW):
    """
    Dual-rotor radial machine (the concept of DeepDrive's in-wheel motors): one double-sided laminated
    stator between an inner and an outer magnet rotor. The stator is two slotted rings back to back with
    aligned teeth and a thin common yoke; the magnets of the two rotors point the same radial way, so the
    flux passes straight through the teeth from rotor to rotor and the yoke carries little. Both windings
    (tooth coils on the inner and on the outer teeth) are in series.
    """

    key = "rfm_dual_rotor"
    title = "Dual-rotor radial surface PM: double-sided stator between an inner and an outer rotor"
    summary = ("Two air gaps, one yokeless double-sided stator; inner rotor facing out, outer rotor facing in, "
               "magnets aligned for through-flux; both tooth-coil windings in series.")
    sources = "DeepDrive dual-rotor radial flux motor (press material, 2023 to 2025)"

    def variables(self, env):
        R, rb = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2
        return [var("combo", 0, len(self.combos) - 1, "int"), var("stator_mid_radius_mm", rb + 6.0, R - 6.0, unit="mm"),
                var("stator_half_mm", 2.5, 10.0, unit="mm"), var("air_gap_mm", 0.3, 1.0, unit="mm"),
                var("tooth_share", 0.3, 0.75), var("yoke_mm", MIN_IRON / 2, 3.0, unit="mm"),
                var("tip_height_mm", 0.3, 1.5, unit="mm"), var("opening_share", 0.15, 0.6),
                var("magnet_thickness_mm", 1.5, 5.0, unit="mm"), var("magnet_arc_share", 0.65, 1.0),
                var("skew_share", 0.0, 1.0), var("halbach_segments", 0, 4, "int")]

    def design(self, env, values):
        checks = Checks()
        R, rb, L = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2, env["stack_length_mm"]
        slots, poles = self.poles_of(values)
        p = poles // 2
        sides, layout, desc = fscw_sides(slots, p, 2, "concentrated")
        g, hm, mid, half = (values["air_gap_mm"], values["magnet_thickness_mm"], values["stator_mid_radius_mm"],
                            values["stator_half_mm"])
        r_gi, r_go = mid - half, mid + half                   # stator surfaces at the inner and outer gap
        vals = dict(values, yoke_mm=values["yoke_mm"] / 2)    # each ring carries half the common yoke
        inner, w_in = slotted_stator(checks, slots, sides, r_gi, mid, "in", vals, L)
        outer, w_out = slotted_stator(checks, slots, sides, r_go, mid, "out", vals, L)
        offset = winding_layout.flux_axis_deg(layout, 0)
        pitch = 360.0 / poles
        # optional Halbach rotors (value halbach_segments >= 2): strong side towards the stator on both rotors
        segments = int(values.get("halbach_segments", 0))
        layout_type, seg = ("halbach", segments) if segments >= 2 else ("surface", 1)
        rotor_in = {"role": "rotor", "type": layout_type, "r_in": rb, "r_out": r_gi - g, "facing": "out", "poles": poles,
                    "offset_deg": offset, "magnet_thickness": hm, "magnet_arc": values["magnet_arc_share"], "segments": seg}
        # facing in, an even pole points inwards: one pole pitch on, the magnet points outwards like the inner one
        rotor_out = {"role": "rotor", "type": layout_type, "r_in": r_go + g, "r_out": R, "facing": "in", "poles": poles,
                     "offset_deg": offset + pitch, "magnet_thickness": hm, "magnet_arc": values["magnet_arc_share"],
                     "segments": seg}
        checks.at_least("inner_rotor_yoke", r_gi - g - hm - rb, MIN_IRON + 0.3)
        checks.at_least("outer_rotor_yoke", R - r_go - g - hm, MIN_IRON + 0.3)
        checks.raise_if_any()
        parts = [rotor_in, inner, outer, rotor_out]
        skew_e = values["skew_share"] * cogging_period_el_rad(slots, poles, p)
        params = {"kind": "radial", "parts": parts, "bore_radius": rb, "stack_length": L, "electrical_pole_pairs": p,
                  "rotor_eddy_width_mm": [0.35, 0.35, (math.pi * r_gi / poles / segments) if segments >= 2
                                          else values["magnet_arc_share"] * math.pi * r_gi / poles],
                  "mesh": self.mesh(env, g)}
        dims = {**{f"inner_{k}": v for k, v in w_in["dims"].items()}, **{f"outer_{k}": v for k, v in w_out["dims"].items()},
                "air_gap_mm": g, "magnet_thickness_mm": hm, "halbach_segments": segments if segments >= 2 else 0,
                "stator_inner_gap_radius_mm": r_gi,
                "stator_outer_gap_radius_mm": r_go}
        overhang = max(w_in["end_overhang_mm"], w_out["end_overhang_mm"])
        coils = 2 * (len(layout.coils) // 3)
        return self.base_design(
            key=self.key, principle=self.principle, params=params, pe=p, coils_per_phase=coils,
            side_area_mm2=(w_in["side_area_mm2"] + w_out["side_area_mm2"]) / 2,
            turn_length_mm=(w_in["turn_length_mm"] + w_out["turn_length_mm"]) / 2, end_overhang_mm=overhang,
            active_length_mm=L, sequence_hint=phase_sequence(layout), skew_e_rad=skew_e,
            skew_factor=math.sin(skew_e / 2) / (skew_e / 2) if skew_e > 1e-9 else 1.0,
            winding={"slots": slots, "poles": poles, "stators": 2, **desc}, dims=dims,
            axial_length_mm=L + 2 * overhang, outer_diameter_mm=2 * R)


TOPOLOGIES = [SPMInner, HalbachInner, SPMOuter, ConsequentInner, IPMV, Spoke, SynRM, PMaSynRM, SRM, Vernier, DualStatorVernier,
              DualRotorSPM]
