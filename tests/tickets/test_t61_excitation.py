"""T61: excitation per principle: Clarke/dq torque, SRM flux map and dynamics, skew, waveforms."""

import math
import unittest

import numpy as np
from helpers import ROOT  # noqa: F401

from emachine.physics import drive as D


class SynchronousTest(unittest.TestCase):
    def test_t61_1_flux_torque_of_ideal_machine(self):
        # psi = psi_pm cos(theta) per phase, current in quadrature: T = 3/2 p psi I
        p, psi, amp = 5, 0.01, 20.0
        for th in np.linspace(0, 2 * math.pi, 7):
            flux = [psi * math.cos(th - 2 * math.pi * k / 3) for k in range(3)]
            i = D.phase_currents(amp, th, math.pi / 2, 1)
            self.assertAlmostEqual(abs(float(D.flux_torque(flux, i, p))), 1.5 * p * psi * amp, places=9)

    def test_t61_1_sequence(self):
        psi0 = [math.cos(-2 * math.pi * k / 3) for k in range(3)]
        step = math.radians(30)
        fwd = [math.cos(step - 2 * math.pi * k / 3) for k in range(3)]
        back = [math.cos(-step - 2 * math.pi * k / 3) for k in range(3)]
        self.assertEqual(D.sequence_from_flux(psi0, fwd, step), 1)
        self.assertEqual(D.sequence_from_flux(psi0, back, step), -1)

    def test_t61_3_skew_removes_harmonic(self):
        n = 72
        th = math.pi * np.arange(n) / n                       # half a period
        torque = 1.0 + 0.2 * np.cos(6 * th)
        sk = D.skewed(torque - 1.0, math.radians(60), antiperiodic=False) + 1.0
        self.assertLess(np.ptp(sk), 1e-9 + 1e-6)
        self.assertAlmostEqual(D.skew_factor(1, math.radians(30)), math.sin(math.radians(15)) / math.radians(15), places=12)

    def test_t61_waveforms_voltage(self):
        # flux psi cos, no resistance: v = -omega psi sin -> amplitude omega N psi
        n, f, psi = 24, 50.0, 0.01
        th = math.pi * np.arange(n) / n
        flux = np.stack([psi * np.cos(th - 2 * math.pi * k / 3) for k in range(3)], axis=1)
        w = D.phase_waveforms(flux, np.zeros_like(flux), 10.0, 0.0, f)
        self.assertAlmostEqual(np.max(np.abs(w["voltage_V"][:, 0])), 2 * math.pi * f * 10 * psi, delta=1e-6)
        self.assertAlmostEqual(np.max(np.abs(w["line_voltage_V"][:, 0])), math.sqrt(3) * 2 * math.pi * f * 10 * psi, delta=1e-6)


class SRMTest(unittest.TestCase):
    def setUp(self):
        self.nr, self.l0, self.l1 = 8, 2e-6, 1e-6
        th = np.linspace(0, math.pi / self.nr, 41)
        ni = np.linspace(10, 2000, 40)
        flux = np.array([[(self.l0 + self.l1 * math.cos(self.nr * t)) * x for x in ni] for t in th])
        tor = np.array([[-0.5 * x * x * self.l1 * self.nr * math.sin(self.nr * t) for x in ni] for t in th])
        self.map = D.SRMPhaseMap(th, ni, flux, tor, self.nr)

    def test_t61_2_map_mirror(self):
        self.assertAlmostEqual(self.map.flux_at(-0.1, 200), self.map.flux_at(0.1, 200), places=12)
        self.assertAlmostEqual(self.map.torque_at(-0.1, 200), -self.map.torque_at(0.1, 200), places=12)
        self.assertAlmostEqual(self.map.ni_at(0.1, self.map.flux_at(0.1, 300)), 300, delta=1e-6)

    def test_t61_2_energy_balance(self):
        r = D.srm_simulate(self.map, 20, 0.0, 48, 1000, -0.3, -0.2, 14, 3)
        i, psi = r["current_A"], r["flux_Wb"]
        electrical = float(np.sum(np.diff(psi) * 0.5 * (i[1:] + i[:-1])))
        mechanical = float(np.mean(r["phase_torque_Nm"]) * self.map.pitch)
        self.assertAlmostEqual(mechanical, electrical, delta=0.03 * abs(electrical))

    def test_t61_2_rms_limit(self):
        b = D.srm_best(self.map, 20, 0.1, 48, 1000, 3, 7.42, 42)
        self.assertLessEqual(b["rms_current_A"], 7.42 * 1.02)
        self.assertGreater(b["mean_torque_Nm"], 0)


if __name__ == "__main__":
    unittest.main()
