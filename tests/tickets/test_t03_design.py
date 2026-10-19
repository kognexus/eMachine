"""T03: design vector to motor parameters."""

import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.spec import SpecError, load_spec


def random_values(spec, rng):
    values = {}
    for var in design.variables(spec):
        if var["kind"] == "int":
            values[var["name"]] = rng.randint(var["low"], var["high"])
        else:
            values[var["name"]] = rng.uniform(var["low"], var["high"])
    return values


REFERENCE = {  # a buildable outrunner with I-bridges, close to the user's corrected motor
    "pole_pairs": 18, "tooth_arc_el_deg": 126.0, "leg_width_mm": 5.0, "slot_height_mm": 14.0,
    "yoke_height_mm": 5.0, "magnet_thickness_mm": 2.0, "current_density_A_mm2": 5.0,
    "rotor_iron_mm": 2.7, "bridge_height_mm": 3.0,
}


class DesignTest(unittest.TestCase):
    def test_t03_1_outrunner_outer_diameter(self):
        spec = load_spec({"machine": {"configuration": "outrunner", "outer_diameter_mm": 80}})
        rng = random.Random(1)
        for _ in range(50):
            params = design.to_parameters(spec, random_values(spec, rng))
            self.assertAlmostEqual(params["rotor"]["outer_diameter"], 80.0, places=9)
            self.assertTrue(params["stator"]["inner_stator"])
            gap = params["rotor"]["inner_diameter"] / 2 - params["stator"]["air_gap_radius"]
            self.assertAlmostEqual(gap, spec["machine"]["air_gap_mm"], places=9)

    def test_t03_2_inrunner_outer_diameter(self):
        spec = load_spec({"machine": {"configuration": "inrunner", "outer_diameter_mm": 120,
                                      "rotor_type": "surface", "stator_type": "u"}})
        rng = random.Random(2)
        for _ in range(50):
            params = design.to_parameters(spec, random_values(spec, rng))
            s = params["stator"]
            self.assertAlmostEqual(2 * (s["air_gap_radius"] + s["slot_height"] + s["yoke_height"]), 120.0, places=9)
            self.assertFalse(s["inner_stator"])
            gap = s["air_gap_radius"] - params["rotor"]["outer_diameter"] / 2
            self.assertAlmostEqual(gap, spec["machine"]["air_gap_mm"], places=9)

    def test_t03_3_single_phase_stack(self):
        spec = load_spec({"machine": {"stack_length_mm": 23, "phases": 1}})
        rng = random.Random(3)
        for _ in range(20):
            s = design.to_parameters(spec, random_values(spec, rng))["stator"]
            self.assertAlmostEqual(s["slot_width"] + 2 * s["leg_width"], 23.0, places=9)

    def test_t03_4_three_phase_stack(self):
        spec = load_spec({"machine": {"stack_length_mm": 75, "phases": 3, "phase_spacing_mm": 3}})
        self.assertAlmostEqual(design.phase_width(spec), 23.0, places=9)
        params = design.to_parameters(spec, random_values(spec, random.Random(4)))
        self.assertAlmostEqual(params["rotor"]["stack_length"], 23.0, places=9)
        self.assertAlmostEqual(params["rotor"]["row_gap"], params["stator"]["slot_width"], places=9)

    def test_t03_5_round_trip(self):
        for overrides in ({}, {"machine": {"configuration": "inrunner", "rotor_type": "surface", "stator_type": "u",
                                           "outer_diameter_mm": 120}},
                          {"machine": {"rotor_type": "flux_concentrating"}}):
            spec = load_spec(overrides)
            rng = random.Random(5)
            for _ in range(20):
                values = design.clip(spec, random_values(spec, rng))
                back = design.from_parameters(spec, design.to_parameters(spec, values))
                self.assertEqual(set(back), set(values))
                for name in values:
                    self.assertAlmostEqual(back[name], values[name], places=9, msg=name)

    def test_t03_6_bounds_from_limits(self):
        spec = load_spec({"limits": {"iron_thickness_mm": [2.5, 7.0], "pole_pairs": [6, 20]}})
        by_name = {v["name"]: v for v in design.variables(spec)}
        self.assertEqual((by_name["yoke_height_mm"]["low"], by_name["yoke_height_mm"]["high"]), (2.5, 7.0))
        self.assertEqual((by_name["leg_width_mm"]["low"], by_name["leg_width_mm"]["high"]), (2.5, 7.0))
        self.assertEqual((by_name["pole_pairs"]["low"], by_name["pole_pairs"]["high"]), (6, 20))
        self.assertEqual(by_name["pole_pairs"]["kind"], "int")

    def test_integer_rounding_and_clipping(self):
        spec = load_spec({})
        values = dict(REFERENCE, pole_pairs=17.6, tooth_arc_el_deg=900.0)
        clipped = design.clip(spec, values)
        self.assertEqual(clipped["pole_pairs"], 18)
        self.assertIsInstance(clipped["pole_pairs"], int)
        self.assertEqual(clipped["tooth_arc_el_deg"], 171.0)
        self.assertEqual(design.clip(spec, dict(REFERENCE, pole_pairs=99))["pole_pairs"], 32)

    def test_variable_override_and_fixing(self):
        spec = load_spec({"variables": {"tooth_arc_el_deg": [108, 144], "magnet_thickness_mm": 3}})
        by_name = {v["name"]: v for v in design.variables(spec)}
        self.assertEqual((by_name["tooth_arc_el_deg"]["low"], by_name["tooth_arc_el_deg"]["high"]), (108, 144))
        self.assertEqual((by_name["magnet_thickness_mm"]["low"], by_name["magnet_thickness_mm"]["high"]), (3, 3))
        with self.assertRaises(SpecError):
            design.variables(load_spec({"variables": {"wheel_size": 3}}))

    def test_stack_too_short(self):
        with self.assertRaises(SpecError):
            design.variables(load_spec({"machine": {"stack_length_mm": 6.0}}))

    def test_ampere_turns_follow_current_density(self):
        spec = load_spec({})
        d = design.derived(spec, design.clip(spec, REFERENCE))
        expected = 5.0 * d["coil_area_mm2"] * spec["winding"]["fill_factor"]
        self.assertAlmostEqual(d["ampere_turns_rms"], expected, places=9)
        params = design.to_parameters(spec, REFERENCE)
        self.assertAlmostEqual(params["analysis"]["coil_current_A"], expected * 2 ** 0.5, places=9)
        self.assertEqual(params["analysis"]["coil_turns"], 1)

    @slow
    def test_t03_7_mesher_accepts_designs(self):
        spec = load_spec({})
        rng = random.Random(7)
        designs = [REFERENCE]
        for _ in range(2):
            v = random_values(spec, rng)
            v.update(tooth_span=0.55, slot_height_mm=10.0, pole_pairs=rng.randint(8, 16))
            designs.append(v)
        with tempfile.TemporaryDirectory() as tmp:
            for i, values in enumerate(designs):
                path = os.path.join(tmp, f"design{i}.json")
                with open(path, "w") as f:
                    json.dump(design.to_parameters(spec, values), f)
                run = subprocess.run([sys.executable, "-m", "emachine", "mesh", "--params", path, "--no-mesh"],
                                     cwd=tmp, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout[-800:] + run.stderr[-800:])
                volumes = [float(v) for v in re.findall(r"solids\s+([\d.]+) mm", run.stdout)]
                self.assertTrue(volumes and all(v > 0 for v in volumes))


if __name__ == "__main__":
    unittest.main()
