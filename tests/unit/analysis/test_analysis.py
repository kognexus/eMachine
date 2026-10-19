"""T38: analysis modules (efficiency map, validation) on the interfaces."""

import json
import math
import os
import subprocess
import sys
import unittest

import numpy as np

from emachine.analysis import effmap
from emachine.core import registry
from emachine.spec import load_spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def levels(ni_values, samples=12):
    angle = np.pi * np.arange(samples) / samples
    return [{"ampere_turns_peak": ni, "torque_Nm": list(np.full(samples, 2e-3 * ni)),
             "flux_per_turn_Wb": list(2e-4 * np.cos(angle)), "a_h": 0.02, "a_e": 3e-5} for ni in ni_values]


class MapTest(unittest.TestCase):
    def test_t38_1_phase_sum_only_for_shifted_phases(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from fakes import FakeMachine
        saved = registry.snapshot()
        try:
            registry.register("machine", "test/fake")(FakeMachine)
            spec = load_spec({"machine": {"family": "test", "topology": "fake"}})
            fake = effmap.Machine(spec, {"width_mm": 3.0}, levels([0.0, 300.0]), 40)
            self.assertFalse(fake.phase_sum)
            self.assertAlmostEqual(float(fake.torque([300.0])[0]), 0.6)          # all phases solved: no x3
        finally:
            registry.restore(saved)
        from emachine.machines.tfm import design
        from emachine.machines.tfm.reference import REFERENCE_DESIGN
        spec = load_spec({"machine": {"phases": 3, "phase_spacing_mm": 1.0}})
        tfm = effmap.Machine(spec, design.clip(spec, REFERENCE_DESIGN), levels([0.0, 300.0]), 40)
        self.assertTrue(tfm.phase_sum)
        self.assertAlmostEqual(float(tfm.torque([300.0])[0]), 1.8)            # three shifted phases


class ValidationTest(unittest.TestCase):
    def test_t38_2_validation_reproduces_t31(self):
        case = os.path.join(ROOT, "examples", "validation", "guo2006", "case.json")
        if not os.path.isdir(os.path.join(ROOT, "examples", "validation", "guo2006", "raw", "load")):
            self.skipTest("no saved fields of the validation run")
        result = subprocess.run([sys.executable, "-m", "emachine", "validate", case, "--variant", "base",
                                 "--losses-only"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        with open(os.path.join(ROOT, "examples", "validation", "guo2006", "results.json")) as f:
            r = json.load(f)
        self.assertAlmostEqual(r["rotor_loss_load_W"], 59.86, delta=0.01)
        self.assertAlmostEqual(r["core_loss_load_W"], 94.45, delta=0.01)
        self.assertAlmostEqual(r["efficiency_motor"], 0.8458, delta=1e-4)


if __name__ == "__main__":
    unittest.main()


class MtpaTest(unittest.TestCase):
    def test_t40_mtpa_of_a_salient_machine(self):
        from emachine.analysis.mtpa import best_current_angle
        # T = 1.5 p (psi_m i_q + (L_d - L_q) i_d i_q), i_d = -I sin(b), i_q = I cos(b): IPM with L_q > L_d.
        p, psi, ld, lq, i = 4, 0.05, 1e-3, 3e-3, 20.0

        def torque(beta_deg):
            b = math.radians(beta_deg)
            idd, iq = -i * math.sin(b), i * math.cos(b)
            return 1.5 * p * (psi * iq + (ld - lq) * idd * iq)

        angle, best = best_current_angle(torque)
        b = (lq - ld) * i                                  # analytic MTPA angle
        expected = math.degrees(math.asin((-psi + math.sqrt(psi ** 2 + 8 * b ** 2)) / (4 * b)))
        self.assertAlmostEqual(angle, expected, delta=0.1)
        self.assertGreaterEqual(best, torque(0.0))
        self.assertAlmostEqual(best_current_angle(lambda a: math.cos(math.radians(a)))[0], 0.0, delta=0.1)
