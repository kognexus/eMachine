"""T58: drive-based evaluation: turns from the voltage, AWG and strands from the fill, the study's drive data."""

import math
import unittest

import helpers  # noqa: F401  (puts the project on the path)

from emachine.physics import drive as D

COPPER = {"resistivity_20C_ohm_m": 1.72e-8, "temp_coefficient_per_K": 0.00393}
DRIVE = {"rated_current_A": 10.5, "peak_current_A": 42.0}


class VoltageTest(unittest.TestCase):
    def test_t58_1_voltage_of_pm_flux(self):
        # pure magnet flux of amplitude psi per turn, no current: |v| = omega N psi
        psi, n, f = 2e-3, 12.0, 166.7
        flux = [psi * math.cos(0.0), psi * math.cos(-2 * math.pi / 3), psi * math.cos(2 * math.pi / 3)]
        v = D.voltage_amplitude(flux, [0.0, 0.0, 0.0], n, 0.1, f, 0.0, 0.0, 1)
        self.assertAlmostEqual(v, 2 * math.pi * f * n * psi, places=6)

    def test_t58_1_resistive_drop(self):
        i = D.phase_currents(10.0, 0.0, 0.0, 1)
        v = D.voltage_amplitude([0.0, 0.0, 0.0], i, 10.0, 0.2, 100.0, 0.0, 0.0, 1)
        self.assertAlmostEqual(v, 2.0, places=6)


class WindingTest(unittest.TestCase):
    def test_t58_2_fill_in_range(self):
        for side in (10.0, 25.0, 60.0):
            for turns in (5, 20, 80):
                wire = D.choose_conductor(side, turns, (0.5, 0.7))
                if wire is None:
                    continue
                self.assertGreaterEqual(wire["fill"], 0.5 - 1e-9)
                self.assertLessEqual(wire["fill"], 0.7 + 1e-9)
                self.assertAlmostEqual(wire["fill"], turns * wire["conductor_area_mm2"] / side, places=9)

    def test_t58_2_no_wire_gives_none(self):
        # 2000 turns in 10 mm2: even AWG 32 overfills -> nothing within the range
        self.assertIsNone(D.choose_conductor(10.0, 2000, (0.5, 0.7)))

    def test_t58_2_fewer_paths_first(self):
        options = D.winding_options(8, 12.2)
        n_c, a = options[0]
        self.assertEqual(a, 1)
        self.assertEqual(n_c, 12)

    def test_t58_2_winding_design(self):
        w = D.winding_design(12.0, 8, 30.0, 120.0, COPPER, DRIVE, 100.0)
        self.assertIsNotNone(w)
        self.assertLessEqual(w["n_eff"], 12.0)
        self.assertTrue(0.5 <= w["fill"] <= 0.7)
        # copper loss at fixed N_eff and fill does not depend on the paths
        r = w["resistance_ohm"]
        expected = (COPPER["resistivity_20C_ohm_m"] * (1 + 0.00393 * 80) * 120e-3 * 8 * w["n_eff"] ** 2
                    / (w["fill"] * 30e-6))
        self.assertAlmostEqual(r, expected, delta=1e-6 * expected)


if __name__ == "__main__":
    unittest.main()
