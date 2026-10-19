"""Fake machine, geometry builder and field solver for tests of the pipeline and the analyses."""

import math

from emachine.core import interfaces
from emachine.core.types import (Check, ExcitationPlan, FieldSample, GeometryRequest, Mesh, ThermalNetwork,
                                 Variable, Winding)


class FakeBuilder(interfaces.GeometryBuilder):
    def build(self, request, rotor_angle_deg, workdir):
        return Mesh(path="", regions={}, meta={"parameters": request.parameters, "warnings": ["fake mesh"]})


class FakeSolver(interfaces.FieldSolver):
    calls = []

    def __init__(self, settings=None, core_field=False):
        self.settings = settings

    def solve(self, mesh, excitation, workdir):
        FakeSolver.calls.append((excitation.rotor_angle_deg, excitation.ampere_turns[0]))
        if excitation.ampere_turns[0] < -50.0:
            raise RuntimeError("solver failed")
        return FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=2.0 * excitation.ampere_turns[0],
                           flux_linkage_Wb=(1e-4,), extras={"core_volume_mm3": 1.0, "solver_iterations": 3,
                                                           "nonlinear_iterations": 0, "elements": 10})


class FakeMachine(interfaces.Machine):
    """All phases solved together, no current-density variable, no TFM keys at all."""
    flux_path, principle = "test", "fake"

    def options(self):
        return {"size": 1.0}

    def variables(self, spec):
        return [Variable("width_mm", 1.0, 5.0)]

    def derive(self, spec, values):
        return {"pole_pairs": 4, "electrical_frequency_Hz": 100.0, "ampere_turns_peak": 200.0,
                "ampere_turns_rms": 200.0 / math.sqrt(2), "width": values["width_mm"]}

    def checks(self, spec, values):
        return [Check.at_least("width", values["width_mm"], 2.0)]

    def geometry(self, spec, values, fidelity=None):
        return GeometryRequest("fake.geometry", {"stator": {"pole_pairs": 4}, "analysis": {"coil_current_A": 200.0}})

    def winding(self, spec, values):
        return Winding(phases=3, turns=None, coil_area_mm2=100.0, mean_turn_length_mm=200.0, fill_factor=0.5)

    def thermal_network(self, spec, values):
        return ThermalNetwork(conductances=(("winding", "core", 1.0), ("core", "rotor", 0.5),
                                            ("core", "ambient", 0.5), ("rotor", "ambient", 0.2)), ambient_C=25.0)

    def excitation(self, spec, values):
        return ExcitationPlan(mode="all_phases", phases=3, electrical_period_deg=90.0, positions=6)
