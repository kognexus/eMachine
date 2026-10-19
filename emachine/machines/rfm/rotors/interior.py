"""Interior magnets (IPM): one V of two bars per pole, an iron bridge to the rotor surface."""

import math

from emachine.core.types import Check, Variable

from ...base import RotorLayout


def v_dimensions(values, rotor_radius, pole_pairs):
    """Depth of the V below the rotor surface and its width across the pole (mm)."""
    half = math.radians(values["v_angle_deg"] / 2)          # between a bar and the pole axis
    length, t = values["magnet_length_mm"], values["magnet_thickness_mm"]
    depth = values["bridge_mm"] + length * math.cos(half) + t
    width = 2 * length * math.sin(half) + t
    return depth, width, math.pi * rotor_radius / pole_pairs


class Interior(RotorLayout):
    name = "interior"
    ticket = "B06"

    def variables(self, spec):
        return [Variable("magnet_thickness_mm", 1.5, 8.0, unit="mm"),
                Variable("magnet_length_mm", 2.0, max(2.0, 0.25 * spec["machine"]["outer_diameter_mm"]), unit="mm"),
                Variable("v_angle_deg", 90.0, 180.0, unit="deg"), Variable("bridge_mm", 0.5, 2.0, unit="mm")]

    def checks(self, spec, values, d):
        depth, width, pole_arc = v_dimensions(values, d["rotor_radius"], d["pole_pairs"])
        core = d["rotor_radius"] - depth - spec["machine"]["bore_diameter_mm"] / 2
        return [Check.at_least("bridge", values["bridge_mm"], 0.5),
                Check.at_most("magnet_width", width, pole_arc, d["rotor_radius"]),     # the V stays within its pole
                Check.at_least("rotor_core", core, spec["limits"]["iron_thickness_mm"][0], d["rotor_radius"])]
