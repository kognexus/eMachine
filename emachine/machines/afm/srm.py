"""Axial flux switched reluctance machine ("afm/srm")."""

from emachine.core.registry import register

from ..base import SwitchedReluctance
from .base import AxialFlux
from .rotors.salient import Salient


@register("machine", "afm/srm")
class AxialFluxSRM(SwitchedReluctance, AxialFlux):
    """Salient poles on stator and rotor discs, concentrated coils, no magnets."""

    ROTORS = (Salient,)
