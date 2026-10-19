"""T04: geometric feasibility and limit checks."""

import random
import time
import unittest

import helpers  # noqa: F401

from emachine.machines.tfm import design
from emachine.machines.tfm import checks
from emachine.spec import load_spec

REFERENCE = {
    "pole_pairs": 18, "tooth_span": 0.7, "leg_width_mm": 5.0, "slot_height_mm": 14.0,
    "yoke_height_mm": 5.0, "magnet_thickness_mm": 2.0, "current_density_A_mm2": 5.0,
    "rotor_iron_mm": 2.7, "bridge_height_mm": 3.0,
}


def failed(spec, values):
    return {r.name for r in checks.violations(checks.check(spec, values))}


class FeasibilityTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec({})

    def test_t04_1_reference_is_feasible(self):
        results = checks.check(self.spec, REFERENCE)
        self.assertEqual(checks.violations(results), [])
        self.assertTrue(checks.is_feasible(results))

    def test_t04_2_users_motor_has_hub_collision(self):
        # 35 mm pole-face radius: rotor iron + magnet = 40 - 35 - 0.5 gap = 4.5 mm
        users = dict(REFERENCE, tooth_span=0.8, slot_height_mm=17.0, yoke_height_mm=5.0,
                     magnet_thickness_mm=2.0, rotor_iron_mm=2.5, bridge_height_mm=5.0)
        d = design.derived(self.spec, users)
        self.assertAlmostEqual(d["stator_radius"], 35.0, places=9)
        self.assertAlmostEqual(d["stator_far_radius"], 13.0, places=9)
        self.assertIn("core_overlap", failed(self.spec, users))

    def test_t04_3_thin_leg(self):
        spec = load_spec({"variables": {"leg_width_mm": [1.0, 10.0]}})
        self.assertIn("iron_leg_min", failed(spec, dict(REFERENCE, leg_width_mm=1.5)))
        self.assertNotIn("iron_leg_min", failed(spec, dict(REFERENCE, leg_width_mm=2.0)))

    def test_t04_4_slot_too_narrow(self):
        spec = load_spec({"variables": {"leg_width_mm": [2.0, 11.4]}})
        self.assertIn("slot_width", failed(spec, dict(REFERENCE, leg_width_mm=10.5)))  # slot = 23 - 21 = 2 mm

    def test_t04_5_bore_clearance(self):
        spec = load_spec({"machine": {"bore_diameter_mm": 40.0}, "variables": {"slot_height_mm": [4, 30]}})
        self.assertIn("bore_clearance", failed(spec, dict(REFERENCE, slot_height_mm=25.0)))

    def test_t04_6_violation_is_monotonic(self):
        spec = load_spec({"variables": {"leg_width_mm": [0.1, 10.0]}})
        previous = -1.0
        for leg in (1.9, 1.5, 1.0, 0.5):
            v = next(r.violation for r in checks.check(spec, dict(REFERENCE, leg_width_mm=leg))
                     if r.name == "iron_leg_min")
            self.assertGreater(v, previous)
            previous = v
        spans = [next(r.violation for r in checks.check(self.spec, dict(REFERENCE, slot_height_mm=17.0, tooth_span=s))
                      if r.name == "core_overlap") for s in (0.75, 0.8, 0.85, 0.9)]
        self.assertEqual(spans, sorted(spans))
        self.assertGreater(spans[-1], spans[0])

    def test_t04_7_speed(self):
        rng = random.Random(0)
        variables = design.variables(self.spec)
        samples = [{v["name"]: (rng.randint(v["low"], v["high"]) if v["kind"] == "int" else rng.uniform(v["low"], v["high"]))
                    for v in variables} for _ in range(200)]
        began = time.time()
        count = 0
        for _ in range(50):
            for s in samples:
                checks.check(self.spec, s)
                count += 1
        self.assertEqual(count, 10000)
        self.assertLess(time.time() - began, 10.0)

    def test_iron_limits_apply_to_core_thickness(self):
        # 4 pole pairs at 35 mm radius: pole pitch 27.5 mm, core thickness far above 10 mm
        self.assertIn("iron_core_thickness_max", failed(self.spec, dict(REFERENCE, pole_pairs=4, tooth_span=0.9)))
        # 32 pole pairs: pole pitch 3.4 mm, core thickness below 2 mm at span 0.5
        self.assertIn("iron_core_thickness_min", failed(self.spec, dict(REFERENCE, pole_pairs=32, tooth_span=0.5)))

    def test_inrunner_checks(self):
        spec = load_spec({"machine": {"configuration": "inrunner", "stator_type": "u", "rotor_type": "surface",
                                      "outer_diameter_mm": 120.0, "stack_length_mm": 40.0}})
        good = {"pole_pairs": 16, "tooth_span": 0.7, "leg_width_mm": 8.0, "slot_height_mm": 20.0,
                "yoke_height_mm": 8.0, "magnet_thickness_mm": 4.0, "current_density_A_mm2": 4.0, "magnet_arc_ratio": 0.85}
        self.assertEqual(failed(spec, good), set())
        # U-cores alone sit two pole pitches apart at the pole faces and cannot touch each other.
        self.assertNotIn("core_overlap", failed(spec, dict(good, pole_pairs=32, tooth_span=0.95)))
        # With I-bridges in between, a span of 0.95 leaves less than the minimum gap.
        spec_ui = load_spec({"machine": {"configuration": "inrunner", "stator_type": "ui", "rotor_type": "surface",
                                         "outer_diameter_mm": 120.0, "stack_length_mm": 40.0}})
        self.assertIn("core_overlap", failed(spec_ui, dict(good, bridge_height_mm=3.0, tooth_span=0.95)))
        self.assertNotIn("core_overlap", failed(spec_ui, dict(good, bridge_height_mm=3.0, tooth_span=0.7)))

    def test_some_random_designs_are_feasible(self):
        rng = random.Random(3)
        variables = design.variables(self.spec)
        feasible = 0
        for _ in range(2000):
            s = {v["name"]: (rng.randint(v["low"], v["high"]) if v["kind"] == "int" else rng.uniform(v["low"], v["high"]))
                 for v in variables}
            feasible += checks.is_feasible(checks.check(self.spec, s))
        self.assertGreater(feasible, 20)  # the design space is not empty


if __name__ == "__main__":
    unittest.main()
