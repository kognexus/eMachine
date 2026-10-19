"""T06: winding and electrical model."""

import math
import unittest

import numpy as np

from helpers import coil_winding, copper_loss, phase_resistance, turns_of

from emachine.physics import winding as electrical
from emachine.spec import load_spec

COIL = {  # 10 mm x 11 mm coil at 24 mm mean radius
    "coil_area_mm2": 110.0, "turn_length_mm": 2 * math.pi * 24.0,
    "ampere_turns_peak": 200.0, "ampere_turns_rms": 200.0 / math.sqrt(2),
    "electrical_frequency_Hz": 18 * 300.0 / 60.0,
}


def coil(spec):
    return coil_winding(spec, COIL["coil_area_mm2"], COIL["turn_length_mm"])


def choose_turns(spec, flux, temp_C):
    return turns_of(spec, coil(spec), flux, COIL["electrical_frequency_Hz"], COIL["ampere_turns_peak"], temp_C)


class ElectricalTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec({"winding": {"fill_factor": 0.5}})

    def test_t06_1_resistance(self):
        expected = 1.72e-8 * 10 ** 2 * (2 * math.pi * 0.024) / (110e-6 * 0.5)
        self.assertAlmostEqual(phase_resistance(self.spec, coil(self.spec), 10, 20.0), expected, delta=1e-12)

    def test_t06_2_resistance_at_temperature(self):
        cold = phase_resistance(self.spec, coil(self.spec), 10, 20.0)
        hot = phase_resistance(self.spec, coil(self.spec), 10, 100.0)
        self.assertAlmostEqual(hot / cold, 1 + 0.00393 * 80, places=12)

    def test_t06_3_induced_voltage_of_sinusoidal_flux(self):
        for n in (6, 12, 24):
            flux = 1e-4 * np.cos(electrical.electrical_angles(n))
            omega = 2 * math.pi * 90.0
            r1 = electrical.winding_resistance(self.spec["materials"]["copper"], coil(self.spec), 20.0)
            v = electrical.volts_per_turn(r1, COIL["electrical_frequency_Hz"], flux, 0.0)
            np.testing.assert_allclose(v, -omega * 1e-4 * np.sin(electrical.electrical_angles(n)), atol=1e-9)
        self.assertAlmostEqual(np.max(np.abs(v)), omega * 1e-4, delta=1e-3 * omega * 1e-4)

    def test_flux_slope_with_harmonics(self):
        a = electrical.electrical_angles(24)
        flux = np.cos(a) + 0.2 * np.cos(3 * a + 0.4)       # odd harmonics reverse over half a period
        np.testing.assert_allclose(electrical.flux_slope(flux), -np.sin(a) - 0.6 * np.sin(3 * a + 0.4), atol=1e-10)

    def test_t06_4_minimum_turns(self):
        flux = 1e-6 * np.cos(electrical.electrical_angles(12))
        result = choose_turns(self.spec, flux, 20.0)
        self.assertEqual(result["turns_min"], 14)             # 200 / 15 = 13.3
        self.assertTrue(result["feasible"])
        self.assertLessEqual(result["peak_current_A"], 15.0 + 1e-9)
        self.assertLessEqual(result["required_bus_voltage_V"], 48.0 + 1e-9)
        self.assertEqual(result["turns"], result["turns_max"])

    def test_t06_5_voltage_too_high(self):
        flux = 0.05 * np.cos(electrical.electrical_angles(12))   # 28 V per turn at 90 Hz
        result = choose_turns(self.spec, flux, 20.0)
        self.assertFalse(result["feasible"])
        self.assertGreater(result["violation"], 0)
        self.assertLess(result["turns_max"], result["turns_min"])
        self.assertGreater(result["required_bus_voltage_V"], 48.0)

    def test_t06_6_copper_loss_independent_of_turns(self):
        losses = []
        for turns in (14, 28):
            i_rms = COIL["ampere_turns_rms"] / turns
            losses.append(i_rms ** 2 * phase_resistance(self.spec, coil(self.spec), turns, 60.0))
        self.assertAlmostEqual(losses[0], losses[1], delta=1e-9)
        self.assertAlmostEqual(copper_loss(self.spec, coil(self.spec), COIL["ampere_turns_rms"], 60.0), losses[0], delta=1e-9)

    def test_t06_7_three_phase_voltage(self):
        spec3 = load_spec({"machine": {"phases": 3, "stack_length_mm": 75.0}})
        self.assertAlmostEqual(electrical.usable_phase_voltage(3, 48.0), 48.0 / math.sqrt(3), places=12)
        self.assertAlmostEqual(electrical.usable_phase_voltage(1, 48.0), 48.0, places=12)
        flux = 2e-4 * np.cos(electrical.electrical_angles(12))
        one = choose_turns(self.spec, flux, 20.0)
        three = choose_turns(spec3, flux, 20.0)
        self.assertLess(three["turns_max"], one["turns_max"])
        self.assertLessEqual(three["required_bus_voltage_V"], 48.0 + 1e-9)

    def test_current_and_density_are_consistent(self):
        flux = 1e-5 * np.cos(electrical.electrical_angles(12))
        r = choose_turns(self.spec, flux, 20.0)
        self.assertAlmostEqual(r["peak_current_A"] * r["turns"], 200.0, places=9)
        self.assertAlmostEqual(r["current_density_rms_A_mm2"], COIL["ampere_turns_rms"] / (110.0 * 0.5), places=9)
        self.assertAlmostEqual(r["rms_current_A"] ** 2 * r["resistance_ohm"],
                               copper_loss(self.spec, coil(self.spec), COIL["ampere_turns_rms"], 20.0), places=9)


if __name__ == "__main__":
    unittest.main()
