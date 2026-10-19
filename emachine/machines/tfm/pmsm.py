"""Transverse flux permanent magnet synchronous machine ("tfm/pmsm")."""

from emachine.core.interfaces import Machine
from emachine.core.registry import register
from emachine.core.types import ExcitationPlan, GeometryRequest, Variable, Winding
from emachine.spec import copper_fill

from .. import winding_layout
from . import checks, design, options, thermal


@register("machine", "tfm/pmsm")
class TransverseFluxPMSM(Machine):
    """
    Transverse flux machine with permanent magnets: one ring coil per phase in U, UI, claw-pole or
    toothed-ring cores (machine.stator); Halbach, surface, spoke or axial-ring rotors
    (machine.rotor); phases stacked axially and magnetically independent.
    """

    flux_path = "tfm"
    principle = "pmsm"
    rotors = options.ROTORS
    winding_spans = ("ring",)
    ticket = "T34"

    def options(self):
        return dict(options.OPTIONS)

    def validate(self, spec):
        options.validate(spec)

    def variables(self, spec):
        return [Variable(v["name"], v["low"], v["high"], v["kind"]) for v in design.variables(spec)]

    def derive(self, spec, values):
        return design.derived(spec, values)

    def checks(self, spec, values):
        return checks.check(spec, values)

    def geometry(self, spec, values, fidelity=None):
        return GeometryRequest(kind="tfm.sector3d", parameters=design.to_parameters(spec, values, fidelity))

    def winding(self, spec, values):
        d = design.derived(spec, values)
        w = spec["winding"]
        return Winding(phases=spec["machine"]["phases"], turns=w["turns"], coil_area_mm2=d["coil_area_mm2"],
                       mean_turn_length_mm=d["turn_length_mm"], fill_factor=copper_fill(spec),
                       conductor=w["conductor"], coil_height_mm=d["coil_height"], coil_width_mm=d["coil_width"])

    def thermal_network(self, spec, values):
        return thermal.network(spec, values, design.derived(spec, values))

    def winding_description(self, spec, values):
        return winding_layout.describe("ring", None, 0, 1, spec["machine"]["phases"], None)

    def excitation(self, spec, values):
        d = design.derived(spec, values)
        return ExcitationPlan(mode="single_phase_shifted", phases=spec["machine"]["phases"],
                              electrical_period_deg=360.0 / d["pole_pairs"],
                              positions=int(spec["fidelity"]["positions"]))
