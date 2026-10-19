"""T14: bore diameter as a macro input."""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT

from emachine.machines.tfm import design
from emachine.machines.tfm import checks
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import SpecError, load_spec

INRUNNER = {"configuration": "inrunner", "stator_type": "u", "rotor_type": "surface",
            "outer_diameter_mm": 120.0, "stack_length_mm": 40.0}
INRUNNER_DESIGN = {"pole_pairs": 16, "tooth_span": 0.7, "leg_width_mm": 8.0, "slot_height_mm": 10.0,
                   "yoke_height_mm": 6.0, "magnet_thickness_mm": 3.0, "current_density_A_mm2": 4.0,
                   "magnet_arc_ratio": 0.85}


def failed(spec, values):
    return {r.name for r in checks.violations(checks.check(spec, values))}


class BoreTest(unittest.TestCase):
    def test_t14_1_outrunner_bore(self):
        small = load_spec({"machine": {"bore_diameter_mm": 20.0}})
        self.assertEqual(failed(small, REFERENCE_DESIGN), set())
        d = design.derived(small, design.clip(small, REFERENCE_DESIGN))
        self.assertAlmostEqual(d["inner_diameter"], 2 * 15.8, places=9)
        large = load_spec({"machine": {"bore_diameter_mm": 40.0}, "variables": {"slot_height_mm": [4.0, 16.0]}})
        self.assertIn("bore_clearance", failed(large, REFERENCE_DESIGN))

    def test_t14_2_inrunner_bore_is_the_shaft(self):
        small = load_spec({"machine": dict(INRUNNER, bore_diameter_mm=30.0)})
        self.assertEqual(failed(small, INRUNNER_DESIGN), set())
        params = design.to_parameters(small, INRUNNER_DESIGN)
        self.assertEqual(params["rotor"]["shaft_diameter"], 30.0)
        self.assertEqual(design.derived(small, design.clip(small, INRUNNER_DESIGN))["inner_diameter"], 30.0)
        large = load_spec({"machine": dict(INRUNNER, bore_diameter_mm=90.0), "variables": {"slot_height_mm": [4.0, 12.0]}})
        self.assertEqual(design.to_parameters(large, INRUNNER_DESIGN)["rotor"]["shaft_diameter"], 90.0)
        self.assertIn("iron_rotor_min", failed(large, INRUNNER_DESIGN))

    def test_t14_3_slot_range_follows_bore(self):
        def slot_high(bore):
            spec = load_spec({"machine": {"bore_diameter_mm": bore}})
            return next(v["high"] for v in design.variables(spec) if v["name"] == "slot_height_mm")
        self.assertLess(slot_high(50.0), slot_high(10.0))
        self.assertAlmostEqual(slot_high(50.0), 40.0 - 25.0 - 0.5 - 1.5 - 4.0, places=9)

    def test_t14_4_optimization_respects_bore(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(ROOT, "examples/tfm_single_phase.json")) as f:
                spec = json.load(f)
            spec["machine"]["bore_diameter_mm"] = 30.0
            spec_file = os.path.join(tmp, "spec.json")
            with open(spec_file, "w") as f:
                json.dump(spec, f)
            run = subprocess.run([sys.executable, "-m", "emachine", "optimize", "--spec", spec_file,
                                  "--run", os.path.join(tmp, "run"), "--dry-run", "--population", "12",
                                  "--generations", "4"], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(run.returncode, 0, run.stdout[-800:] + run.stderr[-800:])
            with open(os.path.join(tmp, "run", "pareto.csv")) as f:
                rows = list(csv.DictReader(f))
            with open(os.path.join(tmp, "run", "report.md")) as f:
                report = f.read()
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertGreaterEqual(float(row["inner_diameter_mm"]), 30.0 - 1e-6)
        self.assertIn("| Bore diameter | 30 mm |", report)

    def test_t14_5_no_room(self):
        with self.assertRaises(SpecError) as ctx:
            design.variables(load_spec({"machine": {"bore_diameter_mm": 78.0}}))
        self.assertIn("no room", str(ctx.exception))
        with self.assertRaises(SpecError):
            load_spec({"machine": {"bore_diameter_mm": 80.0}})


if __name__ == "__main__":
    unittest.main()
