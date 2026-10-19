"""T70: objective max_efficiency and the pick highest_efficiency."""

import math
import tempfile
import unittest

import numpy as np

import helpers  # noqa: F401  (puts the project on the path)

from emachine.cli.optimize import choose_picks
from emachine.pipeline import evaluate
from emachine.spec import SpecError, load_spec



def stand_in(parameters, positions, rundir, jobs):
    angle = math.pi * np.arange(positions) / positions
    return {"torque_Nm": 0.3 + 0.05 * np.sin(angle) ** 2, "flux_per_turn_Wb": 1e-4 * np.cos(angle),
            "core_field_files": []}


class ObjectiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.user = {"limits": {"max_torque_ripple_percent": None}, "fidelity": {"staged": False}}

    def tearDown(self):
        self.tmp.cleanup()

    def values(self, spec):
        from emachine.pipeline import design_space as design
        from emachine.machines.tfm.reference import REFERENCE_DESIGN
        return design.clip(spec, REFERENCE_DESIGN)

    def test_t70_1_spec_accepts_efficiency(self):
        spec = load_spec(dict(self.user, objectives=["max_efficiency", "max_torque"]))
        self.assertEqual(spec["objectives"], ["max_efficiency", "max_torque"])
        with self.assertRaises(SpecError):
            load_spec(dict(self.user, objectives=["max_effiency"]))

    def test_t70_2_objective_vector(self):
        spec = load_spec(dict(self.user, objectives=["max_efficiency", "max_torque", "min_losses"]))
        record = evaluate.evaluate(spec, self.values(spec), self.tmp.name, stand_in)
        self.assertTrue(record["analysed"])
        eff = record["objectives"]["efficiency"]
        self.assertAlmostEqual(eff, record["efficiency"], places=12)
        self.assertGreater(eff, 0.0)
        self.assertEqual(record["f"], [-eff, -record["objectives"]["torque_Nm"], record["objectives"]["loss_W"]])

    def test_t70_3_cache_follows_the_objectives(self):
        first = load_spec(dict(self.user, objectives=["max_torque", "min_losses"]))
        values = self.values(first)
        record = evaluate.evaluate(first, values, self.tmp.name, stand_in)
        self.assertFalse(record["cache_hit"])
        second = load_spec(dict(self.user, objectives=["max_efficiency"]))
        again = evaluate.evaluate(second, values, self.tmp.name, stand_in)
        self.assertTrue(again["cache_hit"])
        self.assertEqual(again["f"], [-record["efficiency"]])

    def test_t70_4_highest_efficiency_pick(self):
        front = [{"objectives": {"torque_Nm": 1.0, "loss_W": 5.0, "efficiency": 0.7}, "f": [-0.7, -1.0]},
                 {"objectives": {"torque_Nm": 0.5, "loss_W": 1.0, "efficiency": 0.8}, "f": [-0.8, -0.5]}]
        picks = choose_picks(front)
        self.assertIs(picks["highest_efficiency"], front[1])
        self.assertIs(picks["highest_torque"], front[0])
        old = [{"objectives": {"torque_Nm": 1.0, "loss_W": 5.0, "ripple": 0.1}, "f": [-1.0, 5.0]}]
        self.assertNotIn("highest_efficiency", choose_picks(old))


if __name__ == "__main__":
    unittest.main()
