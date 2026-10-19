"""T01: project layout and test harness."""

import os
import re
import subprocess
import sys
import unittest

from helpers import ROOT, slow


class LayoutTest(unittest.TestCase):
    def test_t01_2_paths(self):
        from emachine.solvers.elmer import ELMER_GRID, ELMER_SOLVER
        self.assertTrue(os.path.isfile(ELMER_SOLVER), ELMER_SOLVER)
        self.assertTrue(os.path.isfile(ELMER_GRID), ELMER_GRID)

    @slow
    def test_t01_3_default_geometry_regression(self):
        """Sector volumes of the default machine, validated against the Onshape feature."""
        out = subprocess.run([sys.executable, "-m", "emachine", "mesh", "--demo", "--no-mesh"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        volumes = {}
        for name, value in re.findall(r"volume\s+(\S+)\s+\d+ solids\s+([\d.]+) mm", out):
            key = name.replace("_coilshell", "")
            volumes[key] = volumes.get(key, 0.0) + float(value)
        for key, expected in (("stator_tfm_core", 8493.9), ("stator_tfm_coil", 6616.2),
                              ("rotor_back_iron", 21135.1)):
            self.assertAlmostEqual(volumes[key] / expected, 1.0, delta=1e-3, msg=key)


if __name__ == "__main__":
    unittest.main()
