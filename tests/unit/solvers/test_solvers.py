"""T35: field solvers behind core.interfaces.FieldSolver."""

import json
import math
import os
import tempfile
import unittest

from emachine.core import interfaces, registry
from emachine.core.types import Excitation, GeometryRequest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BASELINE = os.path.join(ROOT, "tests", "regression", "baseline")
SLOW = os.environ.get("EMACHINE_SLOW") == "1" or os.environ.get("TFM_SLOW") == "1"


class RegistryTest(unittest.TestCase):
    def test_registered(self):
        self.assertIn("elmer3d", registry.names("solver"))
        self.assertIn("analytic", registry.names("solver"))
        self.assertIn("tfm.sector3d", registry.names("geometry"))
        self.assertIsInstance(registry.create("solver", "analytic"), interfaces.FieldSolver)
        self.assertIsInstance(registry.create("geometry", "tfm.sector3d"), interfaces.GeometryBuilder)


class AnalyticTest(unittest.TestCase):
    def test_t35_3_same_as_the_textbook_estimate(self):
        from emachine.solvers.analytic import parameters_mesh
        with open(os.path.join(BASELINE, "elmer_case_reference_2.5deg.json")) as f:
            parameters = json.load(f)["parameters"]
        solver = registry.create("solver", "analytic")
        ni, angle = 300.0, 0.7
        sample = solver.solve(parameters_mesh(parameters), Excitation(0.0, electrical_angle_rad=angle, amplitude=ni))
        st, ro = parameters["stator"], parameters["rotor"]
        p, r = st["pole_pairs"], st["air_gap_radius"] * 1e-3
        magnet = ro["magnet_thickness"] * 1e-3
        gap = abs(ro.get("inner_diameter", ro["outer_diameter"]) / 2 - st["air_gap_radius"]) * 1e-3
        flux = (parameters["analysis"]["magnet_remanence_T"] * magnet / (magnet + gap + 1e-9) * 0.6
                * st["leg_width"] * 1e-3 * st["tooth_span"] * math.pi * r / p * p)
        cogging = 0.15 * p * flux * ni * (1.2 - st["tooth_span"])
        self.assertAlmostEqual(sample.torque_Nm, p * flux * ni * math.sin(angle) ** 2 + cogging * math.sin(2 * angle)
                               + 0.3 * cogging * math.sin(6 * angle), places=12)
        self.assertAlmostEqual(sample.flux_linkage_Wb[0], flux * math.cos(angle) - 2e-9 * ni * math.sin(angle), places=15)


class AnalyticRadialFluxTest(unittest.TestCase):
    """T41: the stand-in for a radial flux surface PM machine (all phases in one solution)."""

    def setUp(self):
        from emachine.spec import load_spec
        from emachine.solvers.analytic import parameters_mesh
        spec = load_spec(os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"))
        with open(os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")) as f:
            values = json.load(f)
        machine = registry.create("machine", "rfm/pmsm")
        self.d = machine.derive(spec, values)
        self.mesh = parameters_mesh(machine.geometry(spec, values).parameters)
        self.solver = registry.create("solver", "analytic")

    def test_flux_follows_the_rotor_and_torque_the_flux(self):
        ni, p = self.d["ampere_turns_peak"], self.d["pole_pairs"]
        psi = self.solver.solve(self.mesh, Excitation(0.0, electrical_angle_rad=0.0, amplitude=0.0)).flux_linkage_Wb[0]
        # Field solution of the same machine (T41-3): 1.76 mWb per turn; the estimate is about 17 % high
        self.assertAlmostEqual(psi / 1.76e-3, 1.0, delta=0.25)
        for angle in (0.3, 1.0, 2.5):
            sample = self.solver.solve(self.mesh, Excitation(0.0, electrical_angle_rad=angle, amplitude=ni))
            self.assertAlmostEqual(sample.flux_linkage_Wb[0], psi * math.cos(angle), delta=1e-6 * psi)
            self.assertAlmostEqual(sample.torque_Nm / (1.5 * p * psi * ni), 1.0, delta=0.02)
            self.assertEqual(len(sample.flux_linkage_Wb), 3)


@unittest.skipUnless(SLOW, "slow test, set EMACHINE_SLOW=1")
class ElmerCaseTest(unittest.TestCase):
    def test_t35_1_case_file_unchanged(self):
        from emachine.solvers.elmer.sector3d import convert_mesh, write_case
        with open(os.path.join(BASELINE, "elmer_case_reference_2.5deg.json")) as f:
            ref = json.load(f)
        with open(os.path.join(BASELINE, "elmer_case_reference_2.5deg.sif")) as f:
            expected = f.read().splitlines()[1:]          # first line: which program wrote it
        with tempfile.TemporaryDirectory() as tmp:
            mesh = registry.create("geometry", "tfm.sector3d").build(
                GeometryRequest("tfm.sector3d", ref["parameters"]), ref["angle_deg"], tmp)
            convert_mesh(tmp, mesh.meta)
            analysis = ref["analysis"]
            write_case(analysis, mesh.meta, tmp, analysis["coil_turns"] * ref["current_A"])
            with open(os.path.join(tmp, "case.sif")) as f:
                actual = f.read().splitlines()[1:]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
