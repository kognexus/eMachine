"""T39: the command line `emachine`."""

import csv
import glob
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)


class CliTest(unittest.TestCase):
    def test_t39_1_help_list_unknown(self):
        result = run("-m", "emachine", "--help")
        self.assertEqual(result.returncode, 0)
        for command in ("optimize", "map", "export", "validate", "list"):
            self.assertIn(command, result.stdout)
        listing = run("-m", "emachine", "list")
        self.assertIn("tfm/pmsm   solvable", listing.stdout)
        self.assertIn("interior (B06)", listing.stdout)
        self.assertIn("nsga2, random", listing.stdout)
        self.assertEqual(run("-m", "emachine", "teleport").returncode, 2)
        self.assertIn("--spec", run("-m", "emachine", "optimize", "--help").stdout)

    def test_t41_1_radial_flux_optimization_dry_run(self):
        """The same command optimizes a radial flux machine: no change to pipeline or optimizer."""
        with tempfile.TemporaryDirectory() as tmp:
            result = run("-m", "emachine", "optimize", "--spec", os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"),
                         "--run", tmp, "--dry-run", "--population", "6", "--generations", "1")
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])
            with open(os.path.join(tmp, "all_designs.csv")) as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(any(r["feasible"] == "True" for r in rows), rows[:2])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "designs", "best_compromise.json")))

    def test_t39_3_old_spec_files_load(self):
        from emachine.spec import load_spec
        for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*.json"))):
            if path.endswith("_design.json") or os.path.basename(path).startswith(("rfm_", "rafm_")):
                continue
            with self.subTest(spec=os.path.basename(path)):
                spec = load_spec(path)
                self.assertEqual((spec["machine"]["flux_path"], spec["machine"]["principle"]), ("tfm", "pmsm"))


if __name__ == "__main__":
    unittest.main()
