"""T34: the specification asks the registered machine for its section."""

import os
import unittest

from emachine.spec import SpecError, load_spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MachineSectionTest(unittest.TestCase):
    def test_default_is_tfm_pmsm(self):
        spec = load_spec({})
        self.assertEqual((spec["machine"]["flux_path"], spec["machine"]["principle"]), ("tfm", "pmsm"))
        self.assertEqual(spec["machine"]["stator"], "ui_core")         # TFM option from the plugin
        self.assertEqual(spec["machine"]["rotor"], "halbach")          # first rotor layout of the machine

    def test_old_spec_files_load_as_tfm(self):
        spec = load_spec(os.path.join(ROOT, "examples", "user_tr48.json"))
        self.assertEqual(spec["machine"]["flux_path"], "tfm")
        self.assertTrue(spec["machine"]["ring_staggered_teeth"])

    def test_unknown_machine(self):
        with self.assertRaises(SpecError) as raised:
            load_spec({"machine": {"flux_path": "lfm", "principle": "pmsm"}})
        self.assertIn("lfm/pmsm", str(raised.exception))

    def test_machine_options_validated_by_the_plugin(self):
        with self.assertRaises(SpecError):
            load_spec({"machine": {"stator_type": "ui", "ring_arched_valleys": True}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"stator_type": "x"}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"no_such_option": 1}})

    def test_common_keys_still_checked(self):
        with self.assertRaises(SpecError):
            load_spec({"machine": {"rotor_placement": "sideways"}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"bore_diameter_mm": 90.0}})


if __name__ == "__main__":
    unittest.main()
