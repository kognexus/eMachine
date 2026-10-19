"""T72: step skew of the rotor magnets inside each phase."""

import unittest

from helpers import slow

from emachine.machines.tfm import design
from emachine.machines.tfm.geometry.rotors import eddy_widths
from emachine.spec import SpecError

from tickets.test_t71_rotor_magnet_slots import USER_DESIGN, rotor_volumes, spec_with


class OptionsTest(unittest.TestCase):
    def test_t72_1_parameters(self):
        spec = spec_with(rotor_skew_el_deg=20.0, rotor_skew_steps=2)
        rotor = design.to_parameters(spec, USER_DESIGN)["rotor"]
        self.assertEqual(rotor["skew_steps"], 2)
        self.assertAlmostEqual(rotor["skew_deg"], 20.0 / 24)        # mechanical
        with self.assertRaises(SpecError):
            spec_with(rotor_skew_el_deg=20.0)                       # one step cannot skew
        with self.assertRaises(SpecError):
            spec_with(rotor_skew_steps=0)

    def test_t72_2_eddy_width_of_a_slice(self):
        spec = spec_with(rotor_skew_el_deg=20.0, rotor_skew_steps=3)
        rotor = design.to_parameters(spec, USER_DESIGN)["rotor"]
        plain = design.to_parameters(spec_with(), USER_DESIGN)["rotor"]
        # Halbach segment 2.4 mm wide; a third of the 9 mm row is 3 mm: the segment stays the narrower.
        self.assertAlmostEqual(eddy_widths(rotor)[2], eddy_widths(plain)[2])
        rotor["skew_steps"] = 5                                     # 1.8 mm slices are narrower than the segment
        self.assertAlmostEqual(eddy_widths(rotor)[2], 9.0 / 5 / 1000)


@slow
class GeometryTest(unittest.TestCase):
    def test_t72_3_slices(self):
        spec = spec_with(rotor_skew_el_deg=20.0, rotor_skew_steps=2)
        volume, count, info = rotor_volumes(design.to_parameters(spec, USER_DESIGN)["rotor"])
        plain, plain_count, plain_info = rotor_volumes(design.to_parameters(spec_with(), USER_DESIGN)["rotor"])
        self.assertEqual(count, 2 * plain_count)
        self.assertAlmostEqual(volume / plain, 1.0, delta=1e-9)
        shifts = [r["shift_deg"] for r in info["rows"]]
        self.assertAlmostEqual(shifts[0], -10.0 / 24)
        self.assertAlmostEqual(shifts[1], 10.0 / 24)
        # Without skew the magnet names are those of earlier runs (no slice suffix).
        self.assertTrue(all("_row0_" in name for name in plain_info["magnets"]))
        self.assertTrue(all("_row0s" in name for name in info["magnets"]))


if __name__ == "__main__":
    unittest.main()
