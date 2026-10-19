"""Flux barriers with magnets in their middle (PM-assisted SynRM, PMaSynRM)."""

from emachine.core.types import Variable

from .flux_barrier import FluxBarrier


class FluxBarrierPM(FluxBarrier):
    name = "flux_barrier_pm"
    ticket = "B08"

    def variables(self, spec):
        # magnet in the middle of each barrier: its width across the q axis
        return super().variables(spec) + [Variable("magnet_width_mm", 1.0, max(1.0, 0.3 * spec["machine"]["outer_diameter_mm"]),
                                                   unit="mm")]
