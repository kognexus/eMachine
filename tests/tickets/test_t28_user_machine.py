"""T28: the user's 48-pole toothed-ring outrunner in the specification, and the ParaView view script."""

import json
import os
import unittest

from helpers import ROOT

from emachine.machines.tfm import design
from emachine.machines.tfm import checks
from emachine.machines.tfm.cad import sheet as onshape
from emachine.spec import SpecError, load_spec

SPEC = os.path.join(ROOT, "examples", "user_tr48.json")
DESIGN = os.path.join(ROOT, "examples", "user_tr48_design.json")
EXPORT = os.path.join(ROOT, "runs", "user_tr48", "paraview")
MAP = os.path.join(ROOT, "runs", "user_tr48", "map")

#: Field values of the user's Onshape dialogs (2026-10-15); pole count of the rotor as decided (48).
DIALOG_STATOR = {"Core structure": "Toothed ring (Fig. 17)", "Air-gap radius": 35.0, "Pole pairs": 24,
                 "Inner stator (outer rotor)": True, "Number of phases": 3, "Phase spacing": 0.1,
                 "Tooth span / pole pitch": 0.8, "Leg width": 2.0, "Slot width": 5.0, "Slot height": 10.0,
                 "Yoke height": 5.0, "Ring tooth height": 8.0, "Arched valleys between teeth": True,
                 "Coil height": 8.0, "Coil clearance": 1.0,
                 "Staggered teeth (back wall one pole pitch later)": True}


class SpecificationTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(SPEC)
        with open(DESIGN) as f:
            self.values = design.clip(self.spec, json.load(f))

    def test_t28_1_dialog_values_and_feasibility(self):
        parameters = design.to_parameters(self.spec, self.values)
        rows = {r["field"]: r["value"] for r in onshape.stator_rows(parameters["stator"], 3, 0.1)}
        for field, value in DIALOG_STATOR.items():
            with self.subTest(field=field):
                if isinstance(value, float):
                    self.assertAlmostEqual(rows[field], value, places=9)
                else:
                    self.assertEqual(rows[field], value)
        rotor = parameters["rotor"]
        self.assertEqual((rotor["poles"], rotor["magnet_rows"], rotor["type"]), (48, 1, "halbach"))
        self.assertAlmostEqual(rotor["inner_diameter"], 70.6)
        self.assertAlmostEqual(rotor["outer_diameter"], 80.0)
        self.assertAlmostEqual(rotor["magnet_thickness"], 2.0)
        recovered = design.from_parameters(self.spec, parameters)
        for name, value in self.values.items():
            self.assertAlmostEqual(recovered[name], value, places=9, msg=name)
        self.assertEqual(checks.violations(checks.check(self.spec, self.values)), [])

    def test_aligned_teeth_get_two_magnet_rows(self):
        with open(SPEC) as f:
            user = json.load(f)
        user["machine"]["ring_staggered_teeth"] = False
        rotor = design.to_parameters(load_spec(user), self.values)["rotor"]
        self.assertEqual((rotor["magnet_rows"], rotor["alternate_rows"], rotor["row_gap"]), (2, True, 5.0))

    def test_tooth_height_check(self):
        tall = dict(self.values, ring_tooth_height_mm=9.5)
        names = [c.name for c in checks.violations(checks.check(self.spec, tall))]
        self.assertIn("ring_tooth_height", names)

    def test_t28_2_ring_options_need_the_toothed_ring(self):
        with open(SPEC) as f:
            user = json.load(f)
        user["machine"]["stator_type"] = "ui"
        user["variables"].pop("ring_tooth_height_mm")
        with self.assertRaises(SpecError):
            load_spec(user)


class ViewScriptTest(unittest.TestCase):
    def test_t28_3_inputs_of_the_view_script(self):
        from emachine.io import paraview_views as views
        if not (os.path.isdir(EXPORT) and os.path.isdir(MAP)):
            self.skipTest("the export and map of runs/user_tr48 are not there yet")
        self.assertEqual(views.check_inputs(EXPORT, MAP), [])
        arrays = views.vtu_arrays(views.first_step_file(EXPORT))
        for name in ("B", "B_magnitude", "material"):
            self.assertIn(name, arrays)
        self.assertIn("material", views.vtu_arrays(os.path.join(EXPORT, "full_ring.vtu")))


if __name__ == "__main__":
    unittest.main()
