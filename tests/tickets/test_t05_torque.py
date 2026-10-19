"""T05: torque metrics for one and three phases."""

import math
import unittest

import numpy as np

import helpers  # noqa: F401

from emachine.physics import torque


def angles(n):
    return np.pi * np.arange(n) / n   # electrical angle over half a period


class TorqueTest(unittest.TestCase):
    def test_t05_1_single_phase_sin2(self):
        m = torque.metrics(torque.machine_torque(np.sin(angles(12)) ** 2, 1))
        self.assertAlmostEqual(m["mean"], 0.5, places=12)
        self.assertAlmostEqual(m["ripple"], 2.0, places=12)

    def test_t05_2_three_phase_sin2_is_constant(self):
        total = torque.machine_torque(np.sin(angles(12)) ** 2, 3)
        m = torque.metrics(total)
        self.assertAlmostEqual(m["mean"], 1.5, places=12)
        self.assertLess(m["ripple"], 1e-12)

    def test_t05_3_cogging_fundamental_cancels(self):
        a = angles(12)
        phase = np.sin(a) ** 2 + 0.8 * np.sin(2 * a + 0.3)   # one cycle per half period
        total = torque.machine_torque(phase, 3)
        self.assertLess(torque.metrics(total)["peak_to_peak"], 1e-12)
        self.assertAlmostEqual(total.mean(), 1.5, places=12)

    def test_t05_4_third_harmonic_survives(self):
        a = angles(24)
        phase = np.sin(a) ** 2 + 0.1 * np.sin(6 * a)          # three cycles per half period
        total = torque.machine_torque(phase, 3)
        np.testing.assert_allclose(total, 1.5 + 0.3 * np.sin(6 * a), atol=1e-12)

    def test_t05_5_three_phases_need_multiple_of_three(self):
        with self.assertRaises(ValueError):
            torque.machine_torque(np.ones(8), 3)
        with self.assertRaises(ValueError):
            torque.machine_torque(np.ones(9), 2)

    def test_t05_6_zero_mean(self):
        m = torque.metrics(np.sin(2 * angles(12)))
        self.assertEqual(m["ripple"], math.inf)
        self.assertAlmostEqual(m["mean"], 0.0, places=12)
        self.assertEqual(torque.metrics(-np.ones(6))["ripple"], math.inf)

    def test_input_is_not_modified(self):
        phase = np.sin(angles(12)) ** 2
        copy = phase.copy()
        torque.machine_torque(phase, 3)
        torque.machine_torque(phase, 1)[0] = 99.0
        np.testing.assert_array_equal(phase, copy)


if __name__ == "__main__":
    unittest.main()
