"""Radial flux permanent magnet synchronous machine ("rfm/pmsm"): surface or interior magnets."""

from emachine.core.registry import register
from emachine.core.types import Check

from .base import RadialFlux
from .rotors.interior import Interior
from .rotors.surface import Surface


@register("machine", "rfm/pmsm")
class RadialFluxPMSM(RadialFlux):
    """Magnets on (surface, T41) or in (interior, B06) the rotor; sinusoidal currents in all phases."""

    principle = "pmsm"
    ROTORS = (Surface, Interior)

    def principle_checks(self, spec, values, d):
        try:
            self.layout(spec, values)
            return []
        except ValueError:
            return [Check.at_least("balanced_winding", 0.0, 1.0)]
