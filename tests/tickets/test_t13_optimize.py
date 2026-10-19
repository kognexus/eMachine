"""T13: optimization command and report (dry-run workflow tests)."""

import csv
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from helpers import ROOT

from emachine.spec import load_spec

SCRIPT = ["-m", "emachine", "optimize"]
SPEC = os.path.join(ROOT, "examples/tfm_single_phase.json")


def run(rundir, *extra):
    return subprocess.run([sys.executable, *SCRIPT, "--spec", SPEC, "--run", rundir, "--dry-run",
                           "--population", "12", *extra], capture_output=True, text=True, cwd=ROOT)


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


class OptimizeDryRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rundir = os.path.join(cls.tmp.name, "whole")
        began = time.time()
        cls.result = run(cls.rundir, "--generations", "5")
        cls.seconds = time.time() - began

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t13_1_outputs(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout[-1500:] + self.result.stderr[-1500:])
        self.assertLess(self.seconds, 60)
        for name in ("pareto.csv", "all_designs.csv", "report.md", "state.json",
                     "designs/highest_torque.json", "designs/lowest_loss.json", "designs/best_compromise.json"):
            self.assertTrue(os.path.isfile(os.path.join(self.rundir, name)), name)
        with open(os.path.join(self.rundir, "report.md")) as f:
            report = f.read()
        self.assertIn("Dry run", report)
        for text in ("2.0 to 10.0 mm", "4 to 32", "12.0 to 48.0 V", "15.0 A"):     # limits come from the specification
            self.assertIn(text, report)

    def test_t13_2_front_respects_limits(self):
        spec = load_spec(SPEC)
        lim = spec["limits"]
        rows = read(os.path.join(self.rundir, "pareto.csv"))
        self.assertGreater(len(rows), 0)
        lo, hi = lim["iron_thickness_mm"]
        for row in rows:
            self.assertLessEqual(float(row["peak_current_A"]), lim["max_current_A"] + 1e-6)
            self.assertLessEqual(float(row["bus_voltage_needed_V"]), lim["bus_voltage_V"][1] + 1e-6)
            self.assertTrue(lim["pole_pairs"][0] <= int(row["pole_pairs"]) <= lim["pole_pairs"][1])
            for key in ("leg_width_mm", "yoke_height_mm", "core_thickness_mm", "bridge_height_mm", "rotor_iron_mm"):
                self.assertTrue(lo - 1e-6 <= float(row[key]) <= hi + 1e-6, f"{key} = {row[key]}")
            self.assertLessEqual(float(row["winding_C"]), lim["max_winding_temp_C"] + 1e-6)
        torques = [float(r["torque_Nm"]) for r in rows]
        self.assertEqual(torques, sorted(torques, reverse=True))

    def test_t13_3_resume_gives_same_result(self):
        rundir = os.path.join(self.tmp.name, "resumed")
        first = run(rundir, "--generations", "2")
        self.assertEqual(first.returncode, 0, first.stderr[-800:])
        with open(os.path.join(rundir, "state.json")) as f:
            self.assertEqual(json.load(f)["generation"], 2)
        second = run(rundir, "--generations", "5")
        self.assertEqual(second.returncode, 0, second.stderr[-800:])
        self.assertEqual(read(os.path.join(rundir, "pareto.csv")), read(os.path.join(self.rundir, "pareto.csv")))

    def test_pick_file_is_a_valid_parameter_file(self):
        with open(os.path.join(self.rundir, "designs", "best_compromise.json")) as f:
            params = json.load(f)
        self.assertEqual(set(params), {"stator", "rotor", "mesh", "analysis", "design", "machine", "summary"})  # last two since T16
        self.assertAlmostEqual(params["rotor"]["outer_diameter"], 80.0, places=9)
        self.assertAlmostEqual(params["stator"]["slot_width"] + 2 * params["stator"]["leg_width"], 23.0, places=9)
        self.assertGreaterEqual(params["analysis"]["coil_turns"], 1)
        self.assertLessEqual(params["analysis"]["coil_current_A"], 15.0 + 1e-9)
        sys.path.insert(0, ROOT)
        from emachine.cli.solve import load_settings
        path = os.path.join(self.tmp.name, "pick.json")
        with open(path, "w") as f:
            json.dump(params, f)
        load_settings(path)                 # accepted by the pipeline's settings check

    def test_all_designs_table(self):
        rows = read(os.path.join(self.rundir, "all_designs.csv"))
        with open(os.path.join(self.rundir, "state.json")) as f:
            state = json.load(f)
        self.assertEqual(len(rows), len(state["archive"]))
        self.assertTrue(any(r["feasible"] == "True" for r in rows))


if __name__ == "__main__":
    unittest.main()
