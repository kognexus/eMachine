"""T55: the quasi-3D field model of the raxial machine (radial section and axial slices)."""

import json
import math
import os
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.pipeline import design_space
from emachine.spec import load_spec

SPEC = os.path.join(ROOT, "examples", "rafm_zhang2023.json")
DESIGN = os.path.join(ROOT, "examples", "rafm_zhang2023_design.json")


def paper():
    spec = load_spec(SPEC)
    with open(DESIGN) as f:
        return spec, json.load(f)


class RequestTest(unittest.TestCase):
    def test_t55_request(self):
        spec, values = paper()
        request = design_space.geometry(spec, values)
        p = request.parameters["rafm"]
        self.assertEqual(request.kind, "rafm.quasi3d")
        self.assertEqual(len(p["coils"]), 24)
        self.assertEqual([s["radius"] for s in p["slices"]], [125.0, 135.0, 145.0])
        self.assertAlmostEqual(sum(s["depth"] for s in p["slices"]), 30.0)
        # the drive of the sweep is that of all phases together (i_d = 0 from position 0)
        self.assertEqual(request.parameters["sweep"]["mode"], "all_phases")


@slow
class FieldTest(unittest.TestCase):
    """48 positions over half an electrical period: the cogging period of 24 slots / 20 poles is
    30 electrical degrees, 8 positions per cogging period."""

    @classmethod
    def setUpClass(cls):
        from emachine.pipeline.sweep import sweep
        cls.spec, cls.values = paper()
        cls.d = design_space.derived(cls.spec, cls.values)
        request = design_space.geometry(cls.spec, cls.values)
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda name, ni: sweep(request.parameters, 48, os.path.join(tmp, name), ampere_turns_peak=ni,
                                         core_field=False, geometry="rafm.quasi3d")
            cls.no_load = run("no_load", 0.0)
            cls.loaded = run("loaded", 140 * 7.3 * math.sqrt(2))     # the paper's rated current, 140 turns per coil
        psi = cls.no_load["flux_per_turn_Wb"]
        theta = np.arange(48) * math.pi / 48
        cls.psi1 = math.hypot(2 / 48 * float(np.sum(psi * np.cos(theta))), 2 / 48 * float(np.sum(psi * np.sin(theta))))

    def test_t55_flux_peak_at_position_0(self):
        psi = self.no_load["flux_per_turn_Wb"]
        self.assertGreater(psi[0], 0.99 * max(abs(psi)))

    def test_t55_cogging_has_no_mean(self):
        """The periodic boundaries of the slices couple: no net torque at no load."""
        self.assertLess(abs(float(np.mean(self.no_load["torque_Nm"]))), 0.05)

    def test_t55_torque_matches_flux(self):
        expected = 1.5 * 10 * self.psi1 * 140 * 7.3 * math.sqrt(2)
        self.assertAlmostEqual(float(np.mean(self.loaded["torque_Nm"])) / expected, 1.0, delta=0.03)

    def test_t55_1_emf_against_the_paper(self):
        emf = 2 * math.pi * 20 * 140 * self.psi1 / math.sqrt(2)
        self.assertAlmostEqual(emf / 147.0, 1.0, delta=0.15)

    def test_t55_2_torque_against_the_paper(self):
        self.assertAlmostEqual(float(np.mean(self.loaded["torque_Nm"])) / 245.5, 1.0, delta=0.15)


if __name__ == "__main__":
    unittest.main()
