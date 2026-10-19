"""T36: the pipeline with fake machines, geometry builders and solvers (dependency injection)."""

import math
import tempfile
import unittest

import numpy as np

import os
import sys

from emachine.core import registry

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # tests/
from fakes import FakeBuilder, FakeMachine, FakeSolver  # noqa: E402
from emachine.pipeline import evaluate, sweep
from emachine.spec import load_spec


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.saved = registry.snapshot()
        registry.register("geometry", "fake.geometry")(FakeBuilder)
        registry.register("solver", "fake")(FakeSolver)
        registry.register("machine", "test/fake")(FakeMachine)
        FakeSolver.calls = []

    def tearDown(self):
        registry.restore(self.saved)

    def test_t36_1_sweep_angles_currents_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = sweep.sweep({"stator": {"pole_pairs": 4}, "analysis": {}}, 6, tmp, jobs=3,
                                 ampere_turns_peak=40.0, core_field=False, geometry="fake.geometry", solver="fake")
        np.testing.assert_allclose(result["rotor_angle_deg"], 45.0 * np.arange(6) / 6)
        expected_current = -40.0 * np.sin(np.pi * np.arange(6) / 6)
        np.testing.assert_allclose(result["ampere_turns"], expected_current)
        np.testing.assert_allclose(result["torque_Nm"], 2.0 * expected_current)
        self.assertEqual(result["warnings"], ["fake mesh"])
        self.assertEqual(len(FakeSolver.calls), 6)

    def test_sweep_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sweep.AnalysisError):
                sweep.sweep({"stator": {"pole_pairs": 4}, "analysis": {}}, 2, tmp, ampere_turns_peak=100.0,
                            core_field=False, geometry="fake.geometry", solver="fake")

    def test_t36_2_evaluation_of_a_fake_machine(self):
        spec = load_spec({"machine": {"family": "test", "topology": "fake"}, "objectives": ["max_torque", "min_losses"]})

        def analyse(parameters, positions, rundir, jobs, shift=0.0):
            angle = math.pi * (np.arange(positions) + shift) / positions
            return {"torque_Nm": 1.0 + 0.1 * np.sin(6 * angle), "flux_per_turn_Wb": 1e-3 * np.cos(angle),
                    "core_field_files": [], "elements": 1, "seconds": 0.0, "warnings": []}

        with tempfile.TemporaryDirectory() as tmp:
            bad = evaluate.evaluate(spec, {"width_mm": 1.5}, tmp, analyse=analyse, use_cache=False)
            good = evaluate.evaluate(spec, {"width_mm": 3.0}, tmp, analyse=analyse, use_cache=False)
        self.assertFalse(bad["analysed"])
        self.assertEqual(bad["violated_checks"][0]["name"], "width")
        self.assertTrue(good["analysed"])
        # All phases solved together: the machine torque is the solved torque, not three shifted copies.
        self.assertAlmostEqual(good["objectives"]["torque_Nm"], 1.0, places=9)
        self.assertGreater(good["losses"]["copper_W_per_phase"], 0.0)
        self.assertEqual(good["winding"]["conductor"], "round_wire")
        self.assertEqual(len(good["f"]), 2)


if __name__ == "__main__":
    unittest.main()
