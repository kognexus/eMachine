"""Surface magnets (SPM) on a solid or laminated rotor yoke; solved on the 2D cross-section (T41)."""

import math

from emachine.core.types import Check, GeometryRequest, Variable

from ...base import RotorLayout, analysis_settings
from ... import winding_layout


class Surface(RotorLayout):
    name = "surface"
    ticket = "T41"
    solvable = True

    def variables(self, spec):
        return [Variable("magnet_thickness_mm", 1.0, 8.0, unit="mm"),
                Variable("magnet_arc_el_deg", 108.0, 180.0, unit="el. deg")]     # 180: the whole pole

    def checks(self, spec, values, d):
        rotor_core = d["rotor_radius"] - values["magnet_thickness_mm"] - spec["machine"]["bore_diameter_mm"] / 2
        return [Check.at_least("rotor_yoke", rotor_core, spec["limits"]["iron_thickness_mm"][0], d["outer_radius"])]

    def geometry(self, machine, spec, values, fidelity=None):
        d, m = machine.derive(spec, values), spec["machine"]
        layout = machine.layout(spec, values)
        level = spec["fidelity"]["levels"][fidelity or spec["fidelity"]["level"]]
        rotor_radius = d["rotor_radius"]
        shaft = m["bore_diameter_mm"] / 2
        p = d["pole_pairs"]
        arc = values["magnet_arc_el_deg"] / 180.0          # share of the pole pitch (the mesher's input)
        parameters = {
            "rfm": {"slots": d["slots"], "pole_pairs": p, "outer_radius": d["back_radius"],
                    "bore_radius": d["bore_radius"], "slot_depth": d["slot_depth"], "slot_width": d["slot_width"],
                    "air_gap": m["air_gap_mm"], "magnet_thickness": values["magnet_thickness_mm"],
                    "magnet_arc_ratio": arc, "shaft_radius": shaft,
                    "stack_length": d["stack_length"], "sides": [list(s) for s in layout.sides()],
                    "rotor_offset_deg": winding_layout.flux_axis_deg(layout, 0),
                    "rotor_core_thickness": rotor_radius - values["magnet_thickness_mm"] - shaft,
                    "magnet_width": arc * math.pi * rotor_radius / p},
            "mesh": {"gap_cell": level["gap_cell_factor"] * m["air_gap_mm"] / 2, "size_max": level["size_max_mm"] / 2},
            "sweep": {"mode": "all_phases", "pole_pairs": p, "phases": m["phases"],
                      "current_angle_deg": spec["operating_point"].get("current_angle_deg", 0.0)},
            "analysis": analysis_settings(spec, d["ampere_turns_peak"]),
            "design": dict(values),
        }
        return GeometryRequest("rfm.section2d", parameters)
