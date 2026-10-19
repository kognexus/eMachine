"""Transverse flux reluctance machine (no magnets, toothed iron rotor): known to the system, not solvable yet."""

from emachine.core.registry import register
from emachine.core.types import Variable

from ..base import NotSolvableYet
from .pmsm import TransverseFluxPMSM


@register("machine", "tfm/srm")
class TransverseFluxSRM(TransverseFluxPMSM):
    """The stators of the TFM with a rotor of iron teeth (rotor layout salient) instead of magnets."""
    principle = "srm"
    rotors = ("salient",)
    solvable = False
    ticket = "B12"

    def variables(self, spec):
        return [v for v in super().variables(spec) if not v.name.startswith("magnet")] + \
            [Variable("rotor_tooth_arc_el_deg", 54.0, 126.0, unit="el. deg")]

    @staticmethod
    def _complete(values):
        """The TFM dimensions need a magnet height; the iron rotor teeth take its place (same radial room)."""
        return dict(values, magnet_thickness_mm=values.get("magnet_thickness_mm", 2.0))

    def derive(self, spec, values):
        return super().derive(spec, self._complete(values))

    def checks(self, spec, values):
        return super().checks(spec, self._complete(values))

    def winding(self, spec, values):
        return super().winding(spec, self._complete(values))

    def thermal_network(self, spec, values):
        return super().thermal_network(spec, self._complete(values))

    def excitation(self, spec, values):
        return super().excitation(spec, self._complete(values))

    def geometry(self, spec, values, fidelity=None):
        raise NotSolvableYet("The tfm/srm machine has no rotor geometry yet: its variables and checks work, "
                             f"solving it is ticket {self.ticket}.")
