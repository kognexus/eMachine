"""T32-1: data types of emachine.core."""

import unittest

from emachine.core import types


class TypesTest(unittest.TestCase):
    def test_variable(self):
        v = types.Variable("pole_pairs", 8, 30, kind="int")
        self.assertEqual(v.clip(40.2), 30)
        self.assertEqual(v.clip(10.4), 10)
        self.assertEqual(types.Variable("x", 0.0, 1.0).clip(0.25), 0.25)
        with self.assertRaises(ValueError):
            types.Variable("x", 2.0, 1.0)
        with self.assertRaises(ValueError):
            types.Variable("x", 0.0, 1.0, kind="complex")

    def test_check(self):
        low = types.Check.at_least("slot_width", 3.0, 2.0)
        high = types.Check.at_most("outer_radius", 41.0, 40.0)
        self.assertTrue(low.ok)
        self.assertFalse(high.ok)
        self.assertAlmostEqual(high.violation, 1.0 / 40.0)
        self.assertEqual(low.violation, 0.0)
        self.assertEqual(high.as_dict(), {"name": "outer_radius", "value": 41.0, "limit": 40.0, "sense": "<=",
                                          "violation": 1.0 / 40.0})
        # Small limits are scaled by 1, not by the limit.
        self.assertAlmostEqual(types.Check.at_least("gap", 0.1, 0.5).violation, 0.4)

    def test_operating_point_and_currents(self):
        op = types.OperatingPoint(speed_rpm=1500.0, current_peak_A=10.0, current_angle_deg=30.0)
        self.assertAlmostEqual(op.electrical_frequency_Hz(pole_pairs=4), 100.0)
        currents = types.phase_currents(10.0, electrical_angle_deg=0.0, current_angle_deg=0.0, phases=3)
        self.assertEqual(len(currents), 3)
        self.assertAlmostEqual(sum(currents), 0.0, places=12)

    def test_sweep_helpers(self):
        plan = types.ExcitationPlan(mode="single_phase_shifted", phases=3, electrical_period_deg=20.0)
        samples = [types.FieldSample(rotor_angle_deg=a, torque_Nm=1.0 + a, flux_linkage_Wb=(0.1 * a,))
                   for a in (0.0, 1.0, 2.0)]
        sweep = types.Sweep(samples=samples, plan=plan)
        self.assertEqual(list(sweep.angles()), [0.0, 1.0, 2.0])
        self.assertEqual(list(sweep.torque()), [1.0, 2.0, 3.0])
        self.assertEqual(list(sweep.flux(0)), [0.0, 0.1, 0.2])
        with self.assertRaises(ValueError):
            types.ExcitationPlan(mode="half", phases=3, electrical_period_deg=20.0)

    def test_losses_and_evaluation(self):
        losses = types.Losses(copper_W=3.0, stator_core_W=2.0, rotor_W=0.5)
        self.assertEqual(losses.total_W, 5.5)
        e = types.Evaluation(objectives={"torque_Nm": 1.0}, constraints={"temperature": 0.0})
        self.assertTrue(e.feasible)
        self.assertFalse(types.Evaluation(objectives={}, constraints={"temperature": 0.2}).feasible)


if __name__ == "__main__":
    unittest.main()
