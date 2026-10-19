"""Radial flux synchronous reluctance machine ("rfm/synrm"): flux barriers, with or without magnets."""

from emachine.core.registry import register
from emachine.spec.loader import number

from .base import RadialFlux
from .rotors.flux_barrier import FluxBarrier
from .rotors.flux_barrier_pm import FluxBarrierPM


@register("machine", "rfm/synrm")
class RadialFluxSynRM(RadialFlux):
    """Torque from the difference of the d and q inductances of a rotor with flux barriers (SynRM),
    helped by magnets in the barriers with the layout flux_barrier_pm (PMaSynRM)."""

    principle = "synrm"
    ROTORS = (FluxBarrier, FluxBarrierPM)

    def extra_options(self):
        return {"barriers": 3}

    def validate(self, spec):
        super().validate(spec)
        number(spec, "machine.barriers", low=1, high=6, integer=True)
