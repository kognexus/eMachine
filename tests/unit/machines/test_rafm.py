"""T53: the radial-axial ("raxial") PMSM with a toroidal winding: the ARF-PMSM of Zhang et al. 2023."""

import json
import math
import os
import unittest

from helpers import ROOT

from emachine.machines import winding_layout as wl
from emachine.pipeline import design_space
from emachine.spec import SpecError, load_spec

SPEC = os.path.join(ROOT, "examples", "rafm_zhang2023.json")
DESIGN = os.path.join(ROOT, "examples", "rafm_zhang2023_design.json")


def paper():
    spec = load_spec(SPEC)
    with open(DESIGN) as f:
        return spec, json.load(f)


def failed(spec, values):
    return {c.name for c in design_space.checks(spec, values) if c.violation > 0}


class RadialAxialTest(unittest.TestCase):
    def test_t53_1_dimensions_of_the_paper(self):
        spec, values = paper()
        d = design_space.derived(spec, values)
        self.assertAlmostEqual(d["stator_radius"], 175.0)               # radial stator outside diameter 350
        self.assertAlmostEqual(d["core_length"], 80.0)                   # axial length of the stator core
        self.assertAlmostEqual(d["axial_length"], 112.0)                 # total axial length
        self.assertEqual((d["axial_magnet_r0"], d["axial_magnet_r1"]), (120.0, 150.0))   # axial stator 240 / 300
        self.assertEqual(d["radial_tooth_length"], 28.0)                 # radial-motor axial length
        self.assertEqual(failed(spec, values), set())

    def test_t53_2_toroidal_winding(self):
        layout = wl.toroidal(24, 10, 3)
        self.assertEqual([sum(1 for c in layout.coils if c.phase == m) for m in range(3)], [8, 8, 8])
        self.assertAlmostEqual(wl.toroidal_factor(layout), math.cos(math.radians(15)))
        spec, values = paper()
        description = design_space.machine_of(spec).winding_description(spec, values)
        self.assertEqual(description["label"], "toroidal")
        self.assertIn("k_w1 = 0.966", wl.text(description))

    def test_t53_3_masses_against_table_2(self):
        spec, values = paper()
        d = design_space.derived(spec, values)
        self.assertAlmostEqual(d["magnet_mass_kg"] / 2.24, 1.0, delta=0.10)
        self.assertAlmostEqual(d["copper_mass_kg"] / 6.80, 1.0, delta=0.10)
        self.assertAlmostEqual(d["core_mass_kg"] / 18.6, 1.0, delta=0.20)
        # rated current 7.3 A rms, 140 turns per coil: the design's current density gives these ampere-turns
        self.assertAlmostEqual(d["ampere_turns_rms"] / (140 * 7.3), 1.0, delta=0.01)
        # torque density of the paper: 245.5 Nm in pi R^2 L
        self.assertAlmostEqual(245.5 / (d["machine_volume_mm3"] * 1e-9) / 1e3, 17.45, delta=0.05)

    def test_t53_4_checks(self):
        spec, values = paper()
        self.assertIn("coil_axial", failed(spec, dict(values, coil_thickness_mm=19.0)))
        self.assertIn("coil_radial", failed(spec, dict(values, radial_tooth_height_mm=15.0)))
        self.assertIn("axial_tooth_width", failed(spec, dict(values, slot_width_mm=30.0)))
        self.assertIn("slot_opening", failed(spec, dict(values, slot_opening_mm=25.0)))

    def test_t53_names(self):
        spec = load_spec({"machine": {"flux_path": "raxial", "principle": "pmsm"}})
        self.assertEqual(spec["machine"]["flux_path"], "rafm")
        self.assertEqual(spec["winding"]["span"], "toroidal")
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rafm", "principle": "pmsm", "rotor_placement": "inner"}})


if __name__ == "__main__":
    unittest.main()
