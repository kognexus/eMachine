"""Salient iron rotor poles (switched reluctance)."""

from emachine.core.types import Check

from ...base import RotorLayout, lawrenson_checks, pole_arc_variables, stator_pole_arc_deg


class Salient(RotorLayout):
    name = "salient"
    ticket = "B09"

    def variables(self, spec):
        return pole_arc_variables(spec)

    def checks(self, spec, values, d):
        core = d["rotor_radius"] - values["rotor_pole_height_mm"] - spec["machine"]["bore_diameter_mm"] / 2
        return lawrenson_checks(spec, stator_pole_arc_deg(d["slots"], d["slot_width"], d["bore_radius"]),
                                values["rotor_pole_arc_deg"]) + \
            [Check.at_least("rotor_core", core, spec["limits"]["iron_thickness_mm"][0], d["rotor_radius"])]
