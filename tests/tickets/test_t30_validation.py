"""T30: validation against published TFM prototypes (emachine validate and its case files)."""

import json
import math
import os
import unittest

import numpy as np
from helpers import ROOT, slow

from emachine.analysis import validation as validate

GUO = os.path.join(ROOT, "examples", "validation", "guo2006", "case.json")


class HelperTest(unittest.TestCase):
    def test_t30_1_fundamental_and_phases(self):
        x = np.arange(24) * 2 * math.pi / 24
        amplitude, phase = validate.fundamental(0.3 * np.cos(x - 0.4) + 0.05 * np.cos(3 * x))
        self.assertAlmostEqual(amplitude, 0.3, places=9)
        self.assertAlmostEqual(phase, 0.4, places=9)
        # sin^2 of three phases 120 degrees apart sums to 1.5: the ripple-free case.
        total = validate.all_phases(np.sin(x) ** 2, 3)
        np.testing.assert_allclose(total, 1.5, atol=1e-12)
        # The 6th harmonic adds up over three phases, the 2nd cancels.
        np.testing.assert_allclose(validate.all_phases(np.sin(6 * x), 3), 3 * np.sin(6 * x), atol=1e-12)
        np.testing.assert_allclose(validate.all_phases(np.sin(2 * x), 3), 0.0, atol=1e-12)
        with self.assertRaises(ValueError):
            validate.all_phases(np.ones(10), 3)

    def test_t30_2_resistance_of_guo_coil(self):
        with open(GUO) as f:
            case = json.load(f)
        r20, radius = validate.coil_resistance(case["params"], case["operating"], 20.0)
        # Coil from radius 20.5 (window 19.5 + clearance 1) to 39 mm: mean turn radius 29.75 mm.
        self.assertAlmostEqual(radius * 1000, 29.75)
        expected = 125 * 2 * math.pi * 0.02975 * 1.72e-8 / (math.pi * 0.000625 ** 2)
        self.assertAlmostEqual(r20, expected)
        self.assertLess(abs(r20 / 0.305 - 1), 0.15)        # measured 0.305 ohm

    def test_t30_3_case_file(self):
        with open(GUO) as f:
            case = json.load(f)
        st, ro = case["params"]["stator"], case["params"]["rotor"]
        # Radial build of the paper: bore 9.5 + yoke 10 + window 20.5 = stator radius 40; gap 1; rotor 41..47.
        self.assertAlmostEqual(st["air_gap_radius"] - st["slot_height"] - st["yoke_height"], 9.5)
        self.assertAlmostEqual(ro["inner_diameter"] / 2 - st["air_gap_radius"], 1.0)
        self.assertAlmostEqual(ro["outer_diameter"] / 2, 47.0)
        # Stack 31 mm per phase (93 / 3), magnets 9 mm axially, arc 12 of 18 degrees.
        self.assertAlmostEqual(2 * st["leg_width"] + st["slot_width"], 31.0)
        self.assertAlmostEqual((ro["stack_length"] - ro["row_gap"]) / 2, 9.0)
        self.assertAlmostEqual(ro["magnet_arc_ratio"] * 180 / st["pole_pairs"], 12.0, places=2)
        self.assertEqual(ro["poles"], 2 * st["pole_pairs"])
        keys = {"emf_constant_Vs", "cogging_all_phases_peak_Nm", "inductance_mean_H", "torque_em_mean_Nm"}
        self.assertTrue(keys <= {p["key"] for p in case["published"]})

    def test_t30_4_comparison_rows(self):
        rows = validate.compare_rows({"emf_constant_Vs": 0.25, "inductance_mean_H": 0.0065},
                                     [{"key": "emf_constant_Vs", "value": 0.244, "label": "k", "kind": "m"},
                                      {"key": "inductance_mean_H", "scale": 1000, "value": 6.53, "label": "L", "kind": "m"},
                                      {"key": "missing", "value": 1.0, "label": "x", "kind": "m"}])
        self.assertEqual([r["label"] for r in rows], ["k", "L"])
        self.assertAlmostEqual(rows[0]["error"], 0.25 / 0.244 - 1)
        self.assertAlmostEqual(rows[1]["computed"], 6.5)


    def test_t30_5_excess_loss_term(self):
        from emachine.physics import losses
        material = {"k_hysteresis": 0.1402, "alpha": 1.548, "k_eddy": 1.233e-5}
        base = losses.iron_loss_density(material, 300.0, 1.0)
        self.assertAlmostEqual(base, 0.1402 * 300 + 1.233e-5 * 300 ** 2)
        with_excess = losses.iron_loss_density(dict(material, k_anomalous=3.645e-4), 300.0, 1.0)
        self.assertAlmostEqual(with_excess - base, 3.645e-4 * 300 ** 1.5)

    def test_t30_6_claw_pole_case(self):
        with open(os.path.join(ROOT, "examples", "validation", "guo_clawpole", "case.json")) as f:
            case = json.load(f)
        st = case["params"]["stator"]
        self.assertTrue(st["claw_full_discs"])
        # Radial build: shaft 9 = 40 - window 11 - claw 10 - yoke 10; stack 31 = 2 x 7 + 17.
        self.assertAlmostEqual(st["air_gap_radius"] - st["slot_height"] - st["claw_root_height"] - st["yoke_height"], 9.0)
        self.assertAlmostEqual(2 * st["leg_width"] + st["slot_width"], 31.0)
        # Gap between neighbouring claws 4.2 mm at r = 40 (1st sub-airgap).
        pitch = 2 * math.pi * st["air_gap_radius"] / (2 * st["pole_pairs"])
        self.assertAlmostEqual(pitch * (1 - st["tooth_span"]), 4.2, delta=0.02)        # 4.2 is rounded
        r20, radius = validate.coil_resistance(case["params"], case["operating"], 20.0)
        self.assertAlmostEqual(radius * 1000, 40 - (11 + 10 - 0.5 - 3))       # coil at the bottom of the window
        self.assertLess(abs(r20 / 0.225 - 1), 0.15)        # measured 0.225 ohm


@slow
class ClawDiscTest(unittest.TestCase):
    def test_t30_7_discs_with_l_claws(self):
        import gmsh
        from emachine.machines.tfm.geometry import sector as mesher
        with open(os.path.join(ROOT, "examples", "validation", "guo_clawpole", "case.json")) as f:
            stator = json.load(f)["params"]["stator"]
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        try:
            parts, names, _ = mesher.build_stator(dict(mesher.DEFAULTS["stator"], **stator))
            mesher.occ.synchronize()
            core = [t for (_, t), n in zip(parts, names) if n == "tfm_core"]

            def iron(r, angle_deg, z):
                a = math.radians(angle_deg)
                return any(gmsh.model.isInside(3, t, [r * math.cos(a), r * math.sin(a), z]) for t in core)

            pitch = 180.0 / stator["pole_pairs"]
            disc = -(stator["slot_width"] / 2 + stator["leg_width"] / 2)      # middle of the -axial disc
            # Claw level (r 35): the -axial disc has a rim tooth under its own claw (even pole positions),
            # none where the claw of the other disc reaches across (odd positions) or between claws.
            self.assertTrue(iron(35.0, 0.0, disc))
            self.assertFalse(iron(35.0, pitch, disc))
            self.assertFalse(iron(35.0, pitch / 2, disc))
            # Below the claws (r 25) the disc is continuous.
            for angle in (0.0, pitch / 2, pitch):
                self.assertTrue(iron(25.0, angle, disc), angle)
            # The claw head of the +axial disc (odd positions) crosses the coil window to 2.65 mm from the
            # -axial disc.
            tip = -stator["slot_width"] / 2 + stator["claw_tip_gap"]
            self.assertTrue(iron(35.0, pitch, tip + 0.5))
            self.assertFalse(iron(35.0, pitch, tip - 0.5))
        finally:
            gmsh.finalize()


if __name__ == "__main__":
    unittest.main()
