"""
The analytic stand-in: a cheap replacement for the field solution, for testing the workflow
without Gmsh or Elmer. It is a rough textbook estimate and must not be used for design decisions.
"""

import math

from emachine.core.interfaces import FieldSolver
from emachine.core.registry import register
from emachine.core.types import FieldSample, Mesh


def parameters_mesh(parameters):
    """The stand-in needs no mesh: the "mesh" carries the parameters of the design."""
    return Mesh(path="", regions={}, meta={"parameters": parameters})


@register("solver", "analytic")
class AnalyticStandIn(FieldSolver):
    """Torque and flux of one TFM phase, or of all phases of a radial flux surface PM machine, from
    the magnet remanence and the dimensions. The excitation must give the electrical angle and the
    amplitude of the sinusoidal drive."""

    WARNING = "analytic stand-in, not a field solution"

    def __init__(self, settings=None):
        self.settings = dict(settings or {})

    def solve(self, mesh, excitation, workdir=None):
        parameters = mesh.meta["parameters"]
        if "rfm" in parameters:
            return self._radial_flux(parameters, excitation)
        stator, rotor = parameters["stator"], parameters["rotor"]
        remanence = dict(parameters.get("analysis", {}), **self.settings)["magnet_remanence_T"]
        p = stator["pole_pairs"]
        radius = stator["air_gap_radius"] * 1e-3
        leg = stator["leg_width"] * 1e-3
        thickness = stator["tooth_span"] * math.pi * radius / p
        magnet = rotor.get("magnet_thickness", rotor.get("fc_magnet_width", 2.0)) * 1e-3
        gap = abs(rotor.get("inner_diameter", rotor["outer_diameter"]) / 2 - stator["air_gap_radius"]) * 1e-3
        b_gap = remanence * magnet / (magnet + gap + 1e-9) * 0.6
        flux_peak = b_gap * leg * thickness * p                   # all U-cores of the ring link the coil
        ni = excitation.amplitude
        angle = excitation.electrical_angle_rad
        cogging = 0.15 * p * flux_peak * ni * (1.2 - stator["tooth_span"])
        torque = (p * flux_peak * ni * math.sin(angle) ** 2 + cogging * math.sin(2 * angle)
                  + 0.3 * cogging * math.sin(6 * angle))
        flux = flux_peak * math.cos(angle) - 2e-9 * ni * math.sin(angle)
        return FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=torque, flux_linkage_Wb=(flux,),
                           extras={"elements": 0, "warnings": [self.WARNING]})

    def _radial_flux(self, parameters, excitation):
        """Surface PM: fundamental of the magnet field across the air gap (Carter factor, no
        leakage) times the winding factor of the coil sides; torque 3/2 p psi NI cos(current angle)."""
        rfm = parameters["rfm"]
        analysis = dict(parameters.get("analysis", {}), **self.settings)
        remanence, mu = analysis["magnet_remanence_T"], analysis.get("magnet_mu_r", 1.05)
        p, gap, magnet = rfm["pole_pairs"], rfm["air_gap"], rfm["magnet_thickness"] / mu
        x = rfm["slot_width"] / (2 * (gap + magnet))
        gamma = 4 / math.pi * (x * math.atan(x) - math.log(math.sqrt(1 + x * x)))
        pitch = 2 * math.pi * rfm["bore_radius"] / rfm["slots"]
        carter = pitch / (pitch - gamma * (gap + magnet))
        b_1 = 4 / math.pi * remanence * magnet / (magnet + carter * gap) * math.sin(rfm["magnet_arc_ratio"] * math.pi / 2)
        pole_flux = 2 * b_1 * (rfm["bore_radius"] - gap / 2) * rfm["stack_length"] * 1e-6 / p
        phases = 1 + max(side[2] for side in rfm["sides"])
        share = lambda side: side[4] if len(side) > 4 else 1.0
        # flux of phase 0 per turn: every coil side adds its share of the fundamental at its slot
        linked = sum(share(side) * side[3] * complex(math.cos(p * math.radians(side[0] * 360.0 / rfm["slots"])),
                                                     math.sin(p * math.radians(side[0] * 360.0 / rfm["slots"])))
                     for side in rfm["sides"] if side[2] == 0)
        psi = abs(linked) / 2 * pole_flux
        angle, ni = excitation.electrical_angle_rad, excitation.amplitude
        beta = math.radians(parameters.get("sweep", {}).get("current_angle_deg", 0.0))
        torque = 1.5 * p * psi * ni * math.cos(beta) * (1 + 0.01 * math.sin(6 * angle))
        flux = tuple(psi * math.cos(angle - 2 * math.pi * k / phases) for k in range(phases))
        return FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=torque, flux_linkage_Wb=flux,
                           extras={"elements": 0, "warnings": [self.WARNING]})
