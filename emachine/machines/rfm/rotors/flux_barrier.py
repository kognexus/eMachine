"""Flux barriers without magnets (SynRM): `barriers` bands per pole around the q axis."""

import math

from emachine.core.types import Check, Variable

from ...base import RotorLayout


def barrier_pitch(rotor_radius, pole_pairs, barriers):
    """Radial pitch of the barrier circles around the q axis (as the CAD of the eMachine feature):
    the circles are centred on the q axis outside the rotor; the largest meets the surface at
    right angles on the neighbouring d axes, the smallest touches the surface on the q axis."""
    beta = math.pi / (2 * pole_pairs)
    centre = rotor_radius / math.cos(beta)
    return (rotor_radius * math.tan(beta) - (centre - rotor_radius)) / barriers


class FluxBarrier(RotorLayout):
    name = "flux_barrier"
    ticket = "B07"

    def variables(self, spec):
        return [Variable("barrier_width_mm", 0.5, 8.0, unit="mm"), Variable("rib_mm", 0.3, 1.5, unit="mm")]

    def checks(self, spec, values, d):
        pitch = barrier_pitch(d["rotor_radius"], d["pole_pairs"], spec["machine"]["barriers"])
        return [Check.at_least("rib", values["rib_mm"], 0.3),
                Check.at_least("barrier_iron", pitch - values["barrier_width_mm"],      # iron between two barriers
                               spec["limits"]["iron_thickness_mm"][0], d["rotor_radius"])]
