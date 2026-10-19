"""T71: rotor magnet slots (pockets over the side walls) and Halbach segments for the gear TFM."""

import copy
import json
import os
import unittest

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.spec import SpecError, load_spec

with open(os.path.join(ROOT, "examples", "user_tr48.json")) as _f:
    USER = json.load(_f)
with open(os.path.join(ROOT, "examples", "user_tr48_design.json")) as _f:
    USER_DESIGN = json.load(_f)


def spec_with(**machine):
    user = copy.deepcopy(USER)
    user["machine"].update(machine)
    user["variables"] = {}
    return load_spec(user)


def rotor_volumes(rotor):
    """Total magnet volume and magnet count of a rotor parameter dictionary (Gmsh)."""
    import gmsh
    from emachine.machines.tfm.geometry.parameters import DEFAULTS
    from emachine.machines.tfm.geometry.rotors import build_rotor
    from emachine.machines.tfm.geometry.shapes import occ
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        parts, names, info = build_rotor(dict(DEFAULTS["rotor"], **rotor), 0.0)
        occ.synchronize()
        magnets = [tag for (_, tag), name in zip(parts, names) if name.startswith("magnet")]
        return sum(occ.getMass(3, tag) for tag in magnets), len(magnets), info
    finally:
        gmsh.finalize()


class OptionsTest(unittest.TestCase):
    def test_t71_1_halbach_segments(self):
        spec = spec_with()
        self.assertEqual(spec["machine"]["halbach_segments"], 2)
        rotor = design.to_parameters(spec, USER_DESIGN)["rotor"]
        self.assertEqual(rotor["segments_per_pole"], 2)
        spec = spec_with(halbach_segments=4)
        self.assertEqual(design.to_parameters(spec, USER_DESIGN)["rotor"]["segments_per_pole"], 4)
        with self.assertRaises(SpecError):
            spec_with(halbach_segments=4, rotor="surface")
        with self.assertRaises(SpecError):
            spec_with(halbach_segments=1)

    def test_t71_2_pockets(self):
        spec = spec_with(rotor_magnet_slots=True)
        names = [v["name"] for v in design.variables(spec)]
        self.assertIn("magnet_overhang_mm", names)
        values = dict(USER_DESIGN, magnet_overhang_mm=1.0)
        params = design.to_parameters(spec, values)
        rotor, slot = params["rotor"], params["stator"]["slot_width"]
        self.assertEqual(rotor["magnet_rows"], 2)
        self.assertFalse(rotor["alternate_rows"])          # the staggered walls face opposite poles already
        self.assertAlmostEqual(rotor["row_gap"], slot - 2.0)
        self.assertAlmostEqual(design.from_parameters(spec, params)["magnet_overhang_mm"], 1.0)
        # A pocket that reaches half the slot closes the web: one row again.
        full = design.to_parameters(spec, dict(USER_DESIGN, magnet_overhang_mm=slot / 2))["rotor"]
        self.assertEqual(full["magnet_rows"], 1)

    def test_t71_3_pockets_need_staggered_teeth(self):
        with self.assertRaises(SpecError):
            spec_with(rotor_magnet_slots=True, ring_staggered_teeth=False)
        with self.assertRaises(SpecError):
            spec_with(rotor_magnet_slots=True, rotor="spoke")

    def test_t71_4_old_specification_unchanged(self):
        spec = load_spec(copy.deepcopy(USER))
        params = design.to_parameters(spec, USER_DESIGN)
        self.assertEqual(params["rotor"]["magnet_rows"], 1)
        self.assertNotIn("skew_steps", params["rotor"])
        self.assertNotIn("ring_tip_overhang", params["stator"])
        self.assertNotIn("magnet_overhang_mm", [v["name"] for v in design.variables(spec)])


@slow
class GeometryTest(unittest.TestCase):
    def test_t71_5_pocket_magnet_volume(self):
        spec = spec_with(rotor_magnet_slots=True)
        full, n_full, _ = rotor_volumes(design.to_parameters(spec, dict(USER_DESIGN, magnet_overhang_mm=2.5))["rotor"])
        pockets, n_pockets, info = rotor_volumes(design.to_parameters(spec, dict(USER_DESIGN, magnet_overhang_mm=1.0))["rotor"])
        self.assertEqual(n_pockets, 2 * n_full)
        # Row of 9 mm against two pockets of 2 + 1 mm: the magnet volume scales with the axial length.
        self.assertAlmostEqual(pockets / full, 6.0 / 9.0, delta=1e-6)
        self.assertEqual([round(r["shift_deg"], 9) for r in info["rows"]], [0.0, 0.0])

    def test_t71_6_halbach_four_segments(self):
        spec = spec_with(halbach_segments=4)
        volume4, n4, info = rotor_volumes(design.to_parameters(spec, USER_DESIGN)["rotor"])
        volume2, n2, _ = rotor_volumes(design.to_parameters(spec_with(), USER_DESIGN)["rotor"])
        self.assertEqual(n4, 2 * n2)
        self.assertAlmostEqual(volume4 / volume2, 1.0, delta=1e-9)
        angles = sorted({round(m["beta_deg"], 6) for m in info["magnets"].values()})
        self.assertEqual(angles, [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])


if __name__ == "__main__":
    unittest.main()
