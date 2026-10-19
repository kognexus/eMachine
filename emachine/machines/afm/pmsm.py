"""Axial flux permanent magnet synchronous machine ("afm/pmsm")."""

from emachine.core.registry import register

from .base import AxialFlux
from .rotors.surface import Surface


@register("machine", "afm/pmsm")
class AxialFluxPMSM(AxialFlux):
    """Yokeless or single-sided axial flux machine with magnets on the rotor discs."""

    principle = "pmsm"
    ROTORS = (Surface,)
