"""
Hybrid topologies of the catalogue: the radial-axial ("raxial") PMSM of T53 to T57 (machines/rafm), the
toroidal winding working on an outer rotor ring and two rotor discs, evaluated on the study's drive
through its quasi-3D field model (geometry "rafm.quasi3d", solver "elmer_quasi3d").
"""

import math

from emachine.spec.loader import load_spec

from ..rafm.pmsm import RadialAxialFluxPMSM
from .base import Checks, Topology, var

#: (slots, pole pairs) of balanced toroidal windings with k_w1 >= 0.95
TOROIDAL = [(12, 5), (12, 7), (12, 10), (18, 8), (18, 10), (24, 10), (24, 11), (24, 14), (30, 14), (36, 16)]


def raxial_spec(env, slots, gap):
    return load_spec({"machine": {"flux_path": "rafm", "principle": "pmsm", "rotor": "surface", "stator": "toroidal",
                                  "rotor_placement": "outer", "phases": 3, "slots": slots,
                                  "outer_diameter_mm": env["outer_diameter_mm"], "stack_length_mm": env["stack_length_mm"],
                                  "air_gap_mm": gap, "bore_diameter_mm": env["bore_diameter_mm"]},
                      "winding": {"span": "toroidal", "fill_factor": 0.6, "coil_clearance_mm": 0.3},
                      "limits": {"iron_thickness_mm": [1.2, 8.0], "min_slot_width_mm": 2.0, "min_coil_height_mm": 1.0,
                                 "pole_pairs": [4, 20]},
                      "materials": {"stator_core": {"mu_r": 600.0, "saturation_T": 1.95},
                                    "rotor_iron": {"mu_r": 600.0, "saturation_T": 1.95}}})


class Raxial(Topology):
    key = "rafm_raxial"
    title = "Radial-axial (raxial) PM, toroidal winding, outer ring and two discs"
    flux_path = "rafm"
    principle = "pm"
    summary = ("An SMC yoke ring with teeth facing an outer magnet ring radially and two magnet discs axially; one "
               "toroidal coil per slot works on all three air gaps (Zhang, Liu, Wu 2023; T53 to T57).")
    sources = "T53-T57 (Zhang et al. 2023), afpm_tfm.md"
    combos = TOROIDAL

    def variables(self, env):
        """Thicknesses of the rotor parts, and shares of the room that is left for coil, yoke and teeth
        (the radial chain from the rotor ring to the bore and the axial chain over the 30 mm)."""
        return [var("combo", 0, len(self.combos) - 1, "int"), var("air_gap_mm", 0.3, 1.0, unit="mm"),
                var("rotor_iron_mm", 1.2, 4.0, unit="mm"), var("magnet_thickness_mm", 1.5, 4.0, unit="mm"),
                var("magnet_arc_el_deg", 120.0, 180.0, unit="el. deg"), var("coil_share", 0.12, 0.4),
                var("yoke_share", 0.2, 0.5), var("axial_magnet_thickness_mm", 1.5, 4.0, unit="mm"),
                var("axial_magnet_arc_el_deg", 120.0, 180.0, unit="el. deg"), var("disc_iron_mm", 1.2, 4.0, unit="mm"),
                var("axial_tooth_extra_mm", 0.3, 3.0, unit="mm"), var("radial_tooth_length_share", 0.5, 1.0),
                var("slot_share", 0.3, 0.65), var("opening_share", 0.3, 1.0), var("tip_height_mm", 0.5, 2.0, unit="mm")]

    @staticmethod
    def machine_values(env, values, slots, p):
        """The variables of rafm/pmsm (lengths) from the shares."""
        R, rb, L = env["outer_diameter_mm"] / 2, env["bore_diameter_mm"] / 2, env["stack_length_mm"]
        a = 0.3
        g = values["air_gap_mm"]
        room = R - values["rotor_iron_mm"] - values["magnet_thickness_mm"] - g - rb
        c = values["coil_share"] * room
        tip = values["tip_height_mm"]
        free = room - 2 * (c + a + 0.1) - tip             # after the coil's inner and outer sides and the tips
        yoke = values["yoke_share"] * free
        tooth_r = room - (c + a + 0.1) - yoke              # the radial teeth take the rest
        r_yi = rb + c + a + 0.1
        slot_w = values["slot_share"] * 2 * math.pi * r_yi / slots
        tooth_a = c + a + tip + values["axial_tooth_extra_mm"]
        core = L - 2 * (g + values["axial_magnet_thickness_mm"] + values["disc_iron_mm"])
        return {"pole_pairs": p, "current_density_A_mm2": 5.0, "rotor_iron_mm": values["rotor_iron_mm"],
                "magnet_thickness_mm": values["magnet_thickness_mm"], "magnet_arc_el_deg": values["magnet_arc_el_deg"],
                "radial_tooth_height_mm": tooth_r, "radial_tooth_length_mm": values["radial_tooth_length_share"] * core,
                "yoke_width_mm": yoke, "axial_tooth_height_mm": tooth_a, "disc_iron_mm": values["disc_iron_mm"],
                "axial_magnet_thickness_mm": values["axial_magnet_thickness_mm"],
                "axial_magnet_arc_el_deg": values["axial_magnet_arc_el_deg"], "slot_width_mm": slot_w,
                "slot_opening_mm": values["opening_share"] * slot_w, "tooth_tip_height_mm": tip, "coil_thickness_mm": c}

    def design(self, env, values):
        slots, p = self.combos[int(values["combo"])]
        spec = raxial_spec(env, slots, values["air_gap_mm"])
        machine = RadialAxialFluxPMSM()
        vals = self.machine_values(env, values, slots, p)
        checks = Checks()
        for c in machine.checks(spec, vals):
            if c.violation > 0:
                checks.items.append((c.name, c.violation))
        checks.raise_if_any()
        request = machine.geometry(spec, vals)
        params = dict(request.parameters)
        params.pop("analysis", None)
        params["mesh"] = {"gap_cell": max(0.6 * values["air_gap_mm"], 0.3), "size_max": 3.0}
        params["electrical_pole_pairs"] = p
        d = machine.derive(spec, vals)
        w = machine.winding(spec, vals)
        desc = machine.winding_description(spec, vals)
        dims = {k: d[k] for k in ("stator_radius", "yoke_inner_radius", "yoke_outer_radius", "slot_width", "slot_opening",
                                  "coil_thickness", "radial_tooth_length", "core_length", "yoke_length", "rotor_gap_radius")
                if k in d}
        return self.base_design(key=self.key, principle="pm", params=params, geometry_kind="rafm.quasi3d",
                                solver="elmer_quasi3d", pe=p, coils_per_phase=w.coils_per_phase,
                                side_area_mm2=w.coil_area_mm2, turn_length_mm=w.mean_turn_length_mm, end_overhang_mm=0.0,
                                active_length_mm=d.get("radial_tooth_length", env["stack_length_mm"]),
                                winding={"slots": slots, "poles": 2 * p, **desc}, dims=dims,
                                axial_length_mm=env["stack_length_mm"], outer_diameter_mm=env["outer_diameter_mm"])


TOPOLOGIES = [Raxial]
