"""Salient iron poles on the rotor discs (switched reluctance)."""

from ...base import RotorLayout, lawrenson_checks, pole_arc_variables, stator_pole_arc_deg


class Salient(RotorLayout):
    name = "salient"
    ticket = "B11"

    def variables(self, spec):
        return pole_arc_variables(spec)            # rotor_pole_height_mm: axial height of the poles

    def checks(self, spec, values, d):
        # the stator poles widen outwards (rectangular slots): their arc at the mean radius
        return lawrenson_checks(spec, stator_pole_arc_deg(d["slots"], d["slot_width"], d["mean_radius"]),
                                values["rotor_pole_arc_deg"])
