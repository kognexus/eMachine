"""
Axial flux topologies of the catalogue (T60, T63). The active annulus lies between the bore radius
and the outer radius less the end windings of the tooth coils (one coil-side width at each end); the
30 mm active length holds every disc, stator and gap. Slices at the three Gauss radii of the annulus.

Variables: combo (slots, poles), air gap, slot share (slot width / slot pitch, constant angle), tip
height and opening share, magnet thickness and arc, rotor and stator yoke thickness, skew (magnet
skew, as a share of the cogging period).
"""

import math

from .base import FSCW, Checks, Topology, cogging_period_el_rad, fscw_sides, gauss_slices, phase_sequence, srm_sides, var

MIN_IRON = 1.2
END_CLEARANCE = 0.5
AF_FSCW = [c for c in FSCW if c[0] <= 30]


class AxialBase(Topology):
    flux_path = "afm"
    principle = "pm"
    combos = AF_FSCW
    rotors = 1
    stators = 1

    @staticmethod
    def slices(env):
        return int(env.get("fidelity", {}).get("axial_slices", 2))

    @staticmethod
    def mesh(env, gap):
        level = env.get("fidelity", {})
        return {"gap_cell": max(level.get("axial_gap_cell_factor", 0.7) * gap, level.get("axial_gap_cell_min_mm", 0.3)),
                "size_max": level.get("axial_size_max_mm", 3.0), "reach": level.get("axial_reach_mm", 4.0)}

    def common(self, env):
        return [var("combo", 0, len(self.combos) - 1, "int"), var("air_gap_mm", 0.3, 1.0, unit="mm"),
                var("slot_share", 0.35, 0.65), var("tip_height_mm", 0.3, 1.5, unit="mm"), var("opening_share", 0.2, 0.7)]

    def magnets(self):
        return [var("magnet_thickness_mm", 1.5, 5.0, unit="mm"), var("magnet_arc_share", 0.65, 1.0),
                var("skew_share", 0.0, 1.0)]

    def annulus(self, env, checks, slots, slot_share):
        """Active radii: the coil sides' end turns take one coil-side width at each end."""
        R, rb = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2
        # coil side width from the slot at the inner active radius (iterate once)
        r_i = rb + 3.0
        for _ in range(3):
            w_c = slot_share * 2 * math.pi * r_i / slots / 2
            r_i = rb + w_c + END_CLEARANCE
        r_o = R - w_c - END_CLEARANCE
        checks.at_least("active_annulus", r_o - r_i, 5.0)
        return r_i, r_o, w_c

    def winding(self, slots, poles, r_i, r_o, w_c, slot_share, depth):
        """Side area (constant cross-section, set at the inner radius), turn length, coils."""
        side = w_c * depth
        tooth_mid = (1 - slot_share) * 2 * math.pi * (r_i + r_o) / 2 / slots
        turn = 2 * (r_o - r_i) + 2 * tooth_mid + math.pi * w_c
        return side, turn

    def finish(self, env, values, layers, slices, slots, poles, layout, desc, side, turn, w_c, dims, coils, gap,
               pe=None, principle=None, rotor_poles=None, magnet_width=5.0):
        pe = pe or poles // 2
        skew_e = values.get("skew_share", 0.0) * cogging_period_el_rad(slots, poles, pe)
        params = {"kind": "axial", "layers": layers, "slices": slices, "electrical_pole_pairs": pe,
                  "rotor_eddy_width_mm": [layers[0].get("z1", 2) - layers[0].get("z0", 0) if layers[0]["role"] == "rotor" else 2.0,
                                          2.0, magnet_width], "mesh": self.mesh(env, gap)}
        return self.base_design(key=self.key, principle=principle or self.principle, params=params, pe=pe,
                                rotor_poles=rotor_poles, coils_per_phase=coils, side_area_mm2=side, turn_length_mm=turn,
                                end_overhang_mm=0.0, active_length_mm=sum(s["depth"] for s in slices),
                                sequence_hint=phase_sequence(layout) if layout is not None else 1, skew_e_rad=skew_e,
                                skew_factor=math.sin(skew_e / 2) / (skew_e / 2) if skew_e > 1e-9 else 1.0,
                                winding={"slots": slots, "poles": poles, **(desc or {})}, dims=dims,
                                axial_length_mm=env["stack_length_mm"], outer_diameter_mm=env["outer_diameter_mm"])


class SingleSided(AxialBase):
    key = "afm_ss"
    title = "Axial-flux PM, single-sided (one slotted stator, one rotor disc)"
    summary = "One SMC/laminated slotted stator with tooth coils facing one magnet disc; large axial pull."
    sources = "afpm_tfm.md (Di/Do 0.58-0.63, FSCW combos, axial force)"

    def variables(self, env):
        return self.common(env) + self.magnets() + [var("rotor_yoke_mm", 2.0, 8.0, unit="mm"),
                                                    var("stator_yoke_mm", 2.0, 8.0, unit="mm")]

    def design(self, env, values):
        checks = Checks()
        L = env["stack_length_mm"]
        slots, poles = self.combos[int(values["combo"])]
        sides, layout, desc = fscw_sides(slots, poles // 2, 2)
        g, hm, ry, sy = values["air_gap_mm"], values["magnet_thickness_mm"], values["rotor_yoke_mm"], values["stator_yoke_mm"]
        tooth_h = L - ry - hm - g - sy
        checks.at_least("tooth_height", tooth_h - values["tip_height_mm"], 3.0)
        r_i, r_o, w_c = self.annulus(env, checks, slots, values["slot_share"])
        checks.raise_if_any()
        z = 0.0
        stator = {"role": "stator", "z0": z, "z1": sy + tooth_h, "faces": "up", "slots": slots, "slot_share": values["slot_share"],
                  "slot_depth": tooth_h, "tip_height": values["tip_height_mm"],
                  "opening_share": values["opening_share"] * values["slot_share"], "sides": sides}
        z = sy + tooth_h + g
        rotor = {"role": "rotor", "type": "surface", "z0": z, "z1": L, "faces": "down", "poles": poles,
                 "magnet_thickness": hm, "magnet_arc": values["magnet_arc_share"]}
        slices = gauss_slices(r_i, r_o, self.slices(env))
        depth = tooth_h - values["tip_height_mm"]
        side, turn = self.winding(slots, poles, r_i, r_o, w_c, values["slot_share"], depth)
        dims = {"active_inner_radius_mm": r_i, "active_outer_radius_mm": r_o, "tooth_height_mm": tooth_h,
                "stator_yoke_mm": sy, "rotor_yoke_mm": ry, "magnet_thickness_mm": hm, "air_gap_mm": g, "coil_side_width_mm": w_c,
                "magnet_arc_el_deg": 180 * values["magnet_arc_share"]}
        return self.finish(env, values, [stator, rotor], slices, slots, poles, layout, desc, side, turn, w_c, dims,
                           len(layout.coils) // 3, g, magnet_width=values["magnet_arc_share"] * math.pi * (r_i + r_o) / 2 / poles)


class YASA(AxialBase):
    key = "afm_yasa"
    title = "Axial-flux PM, dual rotor, yokeless segmented stator (YASA)"
    summary = ("Two magnet discs with a yokeless stator of separate teeth between them; the flux passes "
               "straight through each tooth (N-S rotors): no stator yoke, short end windings.")
    sources = "afpm_tfm.md (YASA/TORUS, BKHZKL4S cobot motor 27/30 dual rotor, Di/Do)"

    def variables(self, env):
        return self.common(env) + self.magnets() + [var("rotor_yoke_mm", 1.5, 6.0, unit="mm")]

    def design(self, env, values):
        checks = Checks()
        L = env["stack_length_mm"]
        slots, poles = self.combos[int(values["combo"])]
        sides, layout, desc = fscw_sides(slots, poles // 2, 2)
        g, hm, ry, tip = values["air_gap_mm"], values["magnet_thickness_mm"], values["rotor_yoke_mm"], values["tip_height_mm"]
        stator_h = L - 2 * (ry + hm + g)
        checks.at_least("stator_length", stator_h - 2 * tip, 4.0)
        r_i, r_o, w_c = self.annulus(env, checks, slots, values["slot_share"])
        checks.raise_if_any()
        z0 = ry + hm + g
        bottom = {"role": "rotor", "type": "surface", "z0": 0.0, "z1": ry + hm, "faces": "up", "poles": poles,
                  "magnet_thickness": hm, "magnet_arc": values["magnet_arc_share"]}
        stator = {"role": "stator", "z0": z0, "z1": z0 + stator_h, "faces": "both", "slots": slots,
                  "slot_share": values["slot_share"], "slot_depth": stator_h, "tip_height": tip,
                  "opening_share": values["opening_share"] * values["slot_share"], "sides": sides}
        top = {"role": "rotor", "type": "surface", "z0": z0 + stator_h + g, "z1": L, "faces": "down", "poles": poles,
               "magnet_thickness": hm, "magnet_arc": values["magnet_arc_share"], "polarity": -1.0}
        slices = gauss_slices(r_i, r_o, self.slices(env))
        side, turn = self.winding(slots, poles, r_i, r_o, w_c, values["slot_share"], stator_h - 2 * tip)
        dims = {"active_inner_radius_mm": r_i, "active_outer_radius_mm": r_o, "stator_length_mm": stator_h,
                "rotor_yoke_mm": ry, "magnet_thickness_mm": hm, "air_gap_mm": g, "coil_side_width_mm": w_c,
                "magnet_arc_el_deg": 180 * values["magnet_arc_share"]}
        return self.finish(env, values, [bottom, stator, top], slices, slots, poles, layout, desc, side, turn, w_c, dims,
                           len(layout.coils) // 3, g, magnet_width=values["magnet_arc_share"] * math.pi * (r_i + r_o) / 2 / poles)


class DualStator(AxialBase):
    key = "afm_afir"
    title = "Axial-flux PM, dual stator, magnet rotor in the middle (AFIR)"
    summary = "Two slotted stators with tooth coils on both sides of an ironless magnet disc; both windings in series."
    sources = "afpm_tfm.md (TORUS-S / AFIR, Di/Do)"

    def variables(self, env):
        return self.common(env) + self.magnets() + [var("stator_yoke_mm", 1.5, 6.0, unit="mm")]

    def design(self, env, values):
        checks = Checks()
        L = env["stack_length_mm"]
        slots, poles = self.combos[int(values["combo"])]
        sides, layout, desc = fscw_sides(slots, poles // 2, 2)
        g, hm, sy, tip = values["air_gap_mm"], values["magnet_thickness_mm"], values["stator_yoke_mm"], values["tip_height_mm"]
        tooth_h = (L - hm - 2 * g) / 2 - sy
        checks.at_least("tooth_height", tooth_h - tip, 2.5)
        r_i, r_o, w_c = self.annulus(env, checks, slots, values["slot_share"])
        checks.raise_if_any()
        s1 = {"role": "stator", "z0": 0.0, "z1": sy + tooth_h, "faces": "up", "slots": slots, "slot_share": values["slot_share"],
              "slot_depth": tooth_h, "tip_height": tip, "opening_share": values["opening_share"] * values["slot_share"], "sides": sides}
        z = sy + tooth_h + g
        rotor = {"role": "rotor", "type": "through", "z0": z, "z1": z + hm, "faces": "both", "poles": poles,
                 "magnet_arc": values["magnet_arc_share"]}
        z += hm + g
        s2 = dict(s1, z0=z, z1=L, faces="down")
        slices = gauss_slices(r_i, r_o, self.slices(env))
        side, turn = self.winding(slots, poles, r_i, r_o, w_c, values["slot_share"], tooth_h - tip)
        dims = {"active_inner_radius_mm": r_i, "active_outer_radius_mm": r_o, "tooth_height_mm": tooth_h,
                "stator_yoke_mm": sy, "magnet_thickness_mm": hm, "air_gap_mm": g, "coil_side_width_mm": w_c,
                "magnet_arc_el_deg": 180 * values["magnet_arc_share"]}
        return self.finish(env, values, [s1, rotor, s2], slices, slots, poles, layout, desc, side, turn, w_c, dims,
                           2 * len(layout.coils) // 3, g, magnet_width=values["magnet_arc_share"] * math.pi * (r_i + r_o) / 2 / poles)


class CorelessHalbach(AxialBase):
    key = "afm_coreless"
    title = "Axial-flux PM, coreless stator between two Halbach rotors"
    summary = "Concentrated coils without iron (no cogging, no iron loss) between two Halbach magnet discs."
    sources = "afpm_tfm.md (coreless/PCB stators, Halbach), ripple_methods.md"
    combos = [c for c in AF_FSCW if c[1] <= 28]

    def variables(self, env):
        return [var("combo", 0, len(self.combos) - 1, "int"), var("air_gap_mm", 0.3, 1.0, unit="mm"),
                var("slot_share", 0.5, 0.95), var("coil_layer_mm", 3.0, 12.0, unit="mm"),
                var("magnet_thickness_mm", 2.0, 7.0, unit="mm"), var("segments", 2, 4, "int"),
                var("rotor_yoke_mm", 0.0, 4.0, unit="mm")]

    def design(self, env, values):
        checks = Checks()
        L = env["stack_length_mm"]
        slots, poles = self.combos[int(values["combo"])]
        sides, layout, desc = fscw_sides(slots, poles // 2, 2)
        g, hm, ry, h = values["air_gap_mm"], values["magnet_thickness_mm"], values["rotor_yoke_mm"], values["coil_layer_mm"]
        spare = L - 2 * (ry + hm + g) - h
        checks.at_least("axial_length", -abs(spare) if spare < 0 else 0.0, 0.0, 1.0)
        r_i, r_o, w_c = self.annulus(env, checks, slots, values["slot_share"])
        checks.raise_if_any()
        ry += max(spare, 0.0) / 2                  # the rest of the length goes to the rotor discs
        z0 = ry + hm + g
        yoke = ry > 0.3
        bottom = {"role": "rotor", "type": "halbach", "z0": 0.0, "z1": ry + hm, "faces": "up", "poles": poles,
                  "magnet_thickness": hm, "segments": int(values["segments"]), "yoke": yoke}
        stator = {"role": "stator", "z0": z0, "z1": z0 + h, "faces": "both", "slots": slots, "slot_share": values["slot_share"],
                  "slot_depth": h, "tip_height": 0.0, "core": False, "sides": sides}
        top = {"role": "rotor", "type": "halbach", "z0": z0 + h + g, "z1": L, "faces": "down", "poles": poles,
               "magnet_thickness": hm, "segments": int(values["segments"]), "yoke": yoke, "polarity": -1.0}
        slices = gauss_slices(r_i, r_o, self.slices(env))
        side, turn = self.winding(slots, poles, r_i, r_o, w_c, values["slot_share"], h)
        dims = {"active_inner_radius_mm": r_i, "active_outer_radius_mm": r_o, "coil_layer_mm": h, "rotor_disc_mm": ry,
                "magnet_thickness_mm": hm, "air_gap_mm": g, "coil_side_width_mm": w_c, "halbach_segments": int(values["segments"])}
        return self.finish(env, values, [bottom, stator, top], slices, slots, poles, layout, desc, side, turn, w_c, dims,
                           len(layout.coils) // 3, g, magnet_width=math.pi * (r_i + r_o) / 2 / poles / int(values["segments"]))


class AxialSRM(AxialBase):
    key = "afm_srm"
    title = "Axial-flux switched reluctance, dual stator, salient rotor disc"
    principle = "srm"
    summary = "A salient iron rotor disc between two salient-pole stators with tooth coils (both in series)."
    sources = "srm.md (EDDC3MA5, ER5CPGK3, 2DD9JYGR double-stator AF-SRM; Lawrenson pole arcs)"
    combos = [(12, 8), (12, 16), (18, 12), (24, 16)]

    def variables(self, env):
        return [var("combo", 0, len(self.combos) - 1, "int"), var("air_gap_mm", 0.3, 1.0, unit="mm"),
                var("stator_arc_share", 0.0, 1.0), var("rotor_arc_ratio", 1.0, 1.25), var("stator_yoke_mm", 1.5, 6.0, unit="mm"),
                var("rotor_pole_height_mm", 1.0, 5.0, unit="mm"), var("rotor_core_mm", 1.5, 6.0, unit="mm")]

    def design(self, env, values):
        checks = Checks()
        L = env["stack_length_mm"]
        ns, nr = self.combos[int(values["combo"])]
        g, sy = values["air_gap_mm"], values["stator_yoke_mm"]
        stroke = 360.0 / (3 * nr)
        beta_s = stroke * (1.0 + 0.35 * values["stator_arc_share"])     # Lawrenson's least arc and up
        beta_r = values["rotor_arc_ratio"] * beta_s
        checks.at_most("pole_arcs", beta_s + beta_r, 0.95 * 360.0 / nr, stroke)
        checks.at_most("stator_pole_arc", beta_s, 0.6 * 360.0 / ns, stroke)
        rotor_t = 2 * values["rotor_pole_height_mm"] + values["rotor_core_mm"]
        tooth_h = (L - rotor_t - 2 * g) / 2 - sy
        checks.at_least("tooth_height", tooth_h, 3.0)
        slot_share = 1 - beta_s / (360.0 / ns)
        r_i, r_o, w_c = self.annulus(env, checks, ns, slot_share)
        checks.raise_if_any()
        sides = srm_sides(ns)
        off = 180.0 / ns           # stator pole 0 between slots 0 and 1; rotor pole 0 aligned with it
        s1 = {"role": "stator", "z0": 0.0, "z1": sy + tooth_h, "faces": "up", "slots": ns, "slot_share": slot_share,
              "slot_depth": tooth_h, "tip_height": 0.0, "sides": sides}
        z = sy + tooth_h + g
        rotor = {"role": "rotor", "type": "salient", "z0": z, "z1": z + rotor_t, "faces": "both", "poles": nr,
                 "pole_arc_deg": beta_r, "pole_height": values["rotor_pole_height_mm"], "offset_deg": off}
        z += rotor_t + g
        s2 = dict(s1, z0=z, z1=L, faces="down")
        slices = gauss_slices(r_i, r_o, self.slices(env))
        side, turn = self.winding(ns, nr, r_i, r_o, w_c, slot_share, tooth_h)
        dims = {"active_inner_radius_mm": r_i, "active_outer_radius_mm": r_o, "tooth_height_mm": tooth_h,
                "stator_yoke_mm": sy, "air_gap_mm": g, "stator_pole_arc_deg": beta_s, "rotor_pole_arc_deg": beta_r,
                "rotor_disc_mm": rotor_t, "coil_side_width_mm": w_c}
        design = self.finish(env, values, [s1, rotor, s2], slices, ns, nr, None, {"label": f"SRM {ns}/{nr}, tooth coils, 2 stators"},
                             side, turn, w_c, dims, 2 * ns // 3, g, pe=nr, principle="srm", rotor_poles=nr)
        return design


TOPOLOGIES = [SingleSided, YASA, DualStator, CorelessHalbach, AxialSRM]
