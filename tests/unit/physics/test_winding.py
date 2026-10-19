"""T33-1: winding and electrical model from explicit quantities."""

import math
import unittest

import numpy as np

from emachine.physics import winding

COPPER = {"resistivity_20C_ohm_m": 1.72e-8, "temp_coefficient_per_K": 0.00393}


class WindingTest(unittest.TestCase):
    def test_resistance(self):
        r1 = winding.one_turn_resistance(COPPER, copper_area_mm2=50.0, turn_length_mm=200.0, temp_C=20.0)
        self.assertAlmostEqual(r1, 1.72e-8 * 0.2 / 50e-6)
        hot = winding.one_turn_resistance(COPPER, 50.0, 200.0, 120.0)
        self.assertAlmostEqual(hot / r1, 1 + 0.00393 * 100)
        self.assertAlmostEqual(winding.resistance(r1, 30), r1 * 900)
        # Copper loss at fixed ampere-turns does not depend on the turns.
        self.assertAlmostEqual(winding.copper_loss(r1, 100.0), r1 * 1e4)

    def test_flux_slope_and_current_shape(self):
        n = 24
        angle = winding.electrical_angles(n)
        slope = winding.flux_slope(np.cos(angle))
        np.testing.assert_allclose(slope, -np.sin(angle), atol=1e-12)
        np.testing.assert_allclose(winding.current_shape(n), -np.sin(angle))

    def test_usable_phase_voltage(self):
        self.assertEqual(winding.usable_phase_voltage(1, 48.0), 48.0)
        self.assertAlmostEqual(winding.usable_phase_voltage(3, 48.0), 48.0 / math.sqrt(3))

    def test_choose_turns(self):
        # 0.5 V per turn, 200 ampere-turns, 48 V bus, 15 A: voltage allows 55 turns, current needs 14.
        out = winding.choose_turns(volts_per_turn_peak=0.5, ampere_turns_peak=200.0, bus_voltage_V=(12.0, 48.0),
                                   max_current_A=15.0, phases=3, one_turn_resistance_ohm=1e-3,
                                   copper_area_mm2=40.0)
        self.assertEqual((out["turns_min"], out["turns_max"], out["turns"]), (14, 55, 55))
        self.assertTrue(out["feasible"])
        self.assertAlmostEqual(out["resistance_ohm"], 1e-3 * 55 ** 2)
        self.assertAlmostEqual(out["wire_area_mm2"], 40.0 / 55)
        # Not enough voltage for the current limit: infeasible, violation from the bus voltage.
        tight = winding.choose_turns(5.0, 200.0, (12.0, 48.0), 15.0, 3, 1e-3, 40.0)
        self.assertFalse(tight["feasible"])
        self.assertAlmostEqual(tight["violation"], 14 * 5.0 * math.sqrt(3) / 48.0 - 1)
        # Fixed turns and a layer cap (strip coil).
        fixed = winding.choose_turns(0.5, 200.0, (12.0, 48.0), 15.0, 3, 1e-3, 40.0, fixed_turns=20, layer_cap=18)
        self.assertEqual(fixed["turns"], 20)
        self.assertAlmostEqual(fixed["violation"], 20 / 18 - 1)


if __name__ == "__main__":
    unittest.main()
