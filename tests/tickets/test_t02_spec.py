"""T02: design specification file."""

import os
import unittest

from helpers import ROOT

from emachine.spec import DEFAULTS, SpecError, load_spec


class SpecTest(unittest.TestCase):
    def test_t02_1_example_file(self):
        spec = load_spec(os.path.join(ROOT, "examples/tfm_single_phase.json"))
        self.assertEqual(spec["machine"]["rotor_placement"], "outer")
        self.assertEqual(spec["machine"]["stator"], "ui_core")
        self.assertEqual(spec["machine"]["outer_diameter_mm"], 80.0)
        self.assertEqual(spec["machine"]["stack_length_mm"], 23.0)
        self.assertEqual(spec["limits"]["iron_thickness_mm"], [2.0, 10.0])
        self.assertEqual(spec["limits"]["pole_pairs"], [4, 32])
        self.assertEqual(spec["limits"]["bus_voltage_V"], [12.0, 48.0])
        self.assertEqual(spec["limits"]["max_current_A"], 15.0)

    def test_t02_2_empty_uses_defaults(self):
        """An empty spec is the default machine (tfm/pmsm): the common defaults, the TFM options with
        their defaults, and the TFM ring coil."""
        from emachine.machines.tfm.options import OPTIONS
        spec = load_spec({})
        self.assertEqual(set(spec), set(DEFAULTS))
        for section, default in DEFAULTS.items():
            if not isinstance(default, dict):
                self.assertEqual(spec[section], default, section)
                continue
            for key, value in default.items():
                expected = "ring" if (section, key) == ("winding", "span") else value
                self.assertEqual(spec[section][key], expected, f"{section}.{key}")
        added = {k: v for k, v in spec["machine"].items() if k not in DEFAULTS["machine"]}
        self.assertEqual(added, dict(OPTIONS, rotor="halbach"))

    def test_t02_3_unknown_key(self):
        with self.assertRaises(SpecError) as ctx:
            load_spec({"machine": {"colour": "red"}})
        self.assertIn("machine.colour", str(ctx.exception))
        with self.assertRaises(SpecError) as ctx:
            load_spec({"gearbox": {}})
        self.assertIn("gearbox", str(ctx.exception))

    def test_t02_4_phases(self):
        with self.assertRaises(SpecError):
            load_spec({"machine": {"phases": 2}})
        self.assertEqual(load_spec({"machine": {"phases": 3}})["machine"]["phases"], 3)

    def test_t02_5_min_above_max(self):
        with self.assertRaises(SpecError) as ctx:
            load_spec({"limits": {"pole_pairs": [10, 4]}})
        self.assertIn("limits.pole_pairs", str(ctx.exception))

    def test_t02_6_variable_overrides(self):
        spec = load_spec({"variables": {"tooth_arc_el_deg": [108, 144], "magnet_thickness_mm": 3}})
        self.assertEqual(spec["variables"]["tooth_arc_el_deg"], [108, 144])
        # T50: the old name is read and converted to electrical degrees
        self.assertEqual(load_spec({"variables": {"tooth_span": [0.6, 0.8]}})["variables"], {"tooth_arc_el_deg": [108.0, 144.0]})
        self.assertEqual(spec["variables"]["magnet_thickness_mm"], 3)
        with self.assertRaises(SpecError):
            load_spec({"variables": {"tooth_span": [0.9, 0.6]}})

    def test_t02_7_unsupported_stator(self):
        with self.assertRaises(SpecError) as ctx:
            load_spec({"machine": {"stator_type": "c"}})
        self.assertIn("B02", str(ctx.exception))
        with self.assertRaises(SpecError):
            load_spec({"machine": {"stator_type": "banana"}})

    def test_other_invalid_values(self):
        for bad in ({"machine": {"configuration": "sideways"}},
                    {"machine": {"air_gap_mm": 0}},
                    {"limits": {"max_current_A": -1}},
                    {"objectives": ["max_power"]},
                    {"objectives": []},
                    {"winding": {"fill_factor": 1.5}},
                    {"fidelity": {"level": "ultra"}},
                    {"machine": {"phases": 3}, "fidelity": {"positions": 8}},
                    {"materials": {"magnet": {"remanence_T": "strong"}}}):
            with self.assertRaises(SpecError, msg=str(bad)):
                load_spec(bad)

    def test_custom_fidelity_level(self):
        spec = load_spec({"fidelity": {"level": "mine", "levels": {"mine": {"gap_cell_factor": 1.5}}}})
        self.assertEqual(spec["fidelity"]["levels"]["mine"], {"gap_cell_factor": 1.5, "size_max_mm": 6.0})
        self.assertIn("fine", spec["fidelity"]["levels"])
        with self.assertRaises(SpecError):
            load_spec({"fidelity": {"levels": {"mine": {"cell": 1}}}})

    def test_nested_material_override_keeps_other_defaults(self):
        spec = load_spec({"materials": {"stator_core": {"mu_r": 300}}})
        self.assertEqual(spec["materials"]["stator_core"]["mu_r"], 300)
        self.assertEqual(spec["materials"]["stator_core"]["alpha"], 1.548)          # SOMALOY 500 (T31)
        self.assertEqual(spec["materials"]["magnet"]["remanence_T"], 1.3)


if __name__ == "__main__":
    unittest.main()
