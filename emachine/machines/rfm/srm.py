"""Radial flux switched reluctance machine ("rfm/srm")."""

from emachine.core.registry import register

from ..base import SwitchedReluctance
from .base import RadialFlux
from .rotors.salient import Salient


@register("machine", "rfm/srm")
class RadialFluxSRM(SwitchedReluctance, RadialFlux):
    """Salient stator and rotor poles, concentrated coils, no magnets; currents switched per phase."""

    ROTORS = (Salient,)
