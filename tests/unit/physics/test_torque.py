"""T33-4: machine torque from per-phase sweeps, ripple metrics."""

import math
import unittest

import numpy as np

from emachine.physics import torque


class TorqueTest(unittest.TestCase):
    def test_three_phases_half_and_full_period(self):
        n = 24
        half = np.pi * np.arange(n) / n
        phase = np.sin(half) ** 2                         # repeats every half period
        np.testing.assert_allclose(torque.machine_torque(phase, 3), 1.5, atol=1e-12)
        full = 2 * np.pi * np.arange(n) / n
        np.testing.assert_allclose(torque.machine_torque(np.sin(full) ** 2, 3, period="full"), 1.5, atol=1e-12)

    def test_two_and_one_phase(self):
        n = 24
        half = np.pi * np.arange(n) / n
        np.testing.assert_allclose(torque.machine_torque(np.sin(half) ** 2, 2), 1.0, atol=1e-12)
        np.testing.assert_allclose(torque.machine_torque(np.sin(half), 1), np.sin(half))

    def test_bad_sampling(self):
        with self.assertRaises(ValueError):
            torque.machine_torque(np.ones(10), 3)

    def test_metrics(self):
        m = torque.metrics([1.0, 2.0, 3.0])
        self.assertEqual((m["mean"], m["peak_to_peak"], m["ripple"]), (2.0, 2.0, 1.0))
        self.assertEqual(torque.metrics([0.0, 0.0])["ripple"], math.inf)


if __name__ == "__main__":
    unittest.main()
