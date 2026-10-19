"""T07: electromagnetic analysis API."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.physics import winding as electrical
from emachine.pipeline import sweep
from emachine.spec import load_spec

#: The field analysis of the TFM sector with Elmer, as the pipeline builds it.
analyse = sweep.field_analysis("tfm.sector3d", "elmer3d")

REFERENCE = {
    "pole_pairs": 18, "tooth_span": 0.7, "leg_width_mm": 5.0, "slot_height_mm": 14.0,
    "yoke_height_mm": 5.0, "magnet_thickness_mm": 2.0, "current_density_A_mm2": 5.0,
    "rotor_iron_mm": 2.7, "bridge_height_mm": 3.0,
}


class EmUnitTest(unittest.TestCase):
    def test_t07_1_current_waveform(self):
        i = sweep.drive_current(200.0, 12)
        self.assertEqual(len(i), 12)
        self.assertAlmostEqual(i[0], 0.0, places=12)
        self.assertAlmostEqual(i[6], -200.0, places=12)       # 90 electrical degrees
        self.assertTrue(np.all(i <= 1e-12))                    # one sign over the half period

    def test_t07_2_sweep_angles(self):
        a = sweep.sweep_angles(18, 12)
        self.assertEqual(len(a), 12)
        self.assertEqual(a[0], 0.0)
        self.assertAlmostEqual(a[1] - a[0], 10.0 / 12, places=12)
        self.assertAlmostEqual(a[-1], 10.0 * 11 / 12, places=12)


@slow
class EmAnalysisTest(unittest.TestCase):
    """Coarse analyses of the reference design, run once for all tests of this class."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="tfm_t07_")
        # Linear materials: these tests check the solver chain against linear theory
        # (torque = ampere-turns * flux slope). Saturation is tested in test_b01_saturation.py.
        cls.spec = load_spec({"materials": {"stator_core": {"saturation_T": None}, "rotor_iron": {"saturation_T": None}}})
        cls.params = design.to_parameters(cls.spec, REFERENCE)
        cls.derived = design.derived(cls.spec, design.clip(cls.spec, REFERENCE))
        cls.n = 6
        cls.noload = analyse(cls.params, cls.n, os.path.join(cls.tmp, "noload"), jobs=6, ampere_turns_peak=0.0)
        cls.loaded = analyse(cls.params, cls.n, os.path.join(cls.tmp, "loaded"), jobs=6)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_t07_3_no_load_flux(self):
        flux = self.noload["flux_per_turn_Wb"]
        peak = abs(flux[0])
        self.assertEqual(len(flux), self.n)
        self.assertGreater(flux[0], 0)
        self.assertLess(abs(flux[3]), 0.03 * peak)                       # 90 electrical degrees
        for k in (1, 2):                                                 # antisymmetric about 90 degrees
            self.assertLess(abs(flux[k] + flux[self.n - k]), 0.03 * peak)
        self.assertLess(abs(self.noload["torque_Nm"][0]), 0.05 * np.max(np.abs(self.noload["torque_Nm"])) + 0.02)

    def test_t07_4_loaded_torque_matches_flux_slope(self):
        p = self.derived["pole_pairs"]
        slope = electrical.flux_slope(self.noload["flux_per_turn_Wb"])[3] * p    # Wb per mechanical radian
        expected = self.loaded["ampere_turns"][3] * slope
        actual = self.loaded["torque_Nm"][3]
        self.assertGreater(actual, 0)
        self.assertAlmostEqual(actual / expected, 1.0, delta=0.05)
        self.assertAlmostEqual(self.loaded["ampere_turns_peak"], self.derived["ampere_turns_peak"], places=9)

    def test_t07_5_core_field_files(self):
        files = self.loaded["core_field_files"]
        self.assertEqual(len(files), self.n)
        for path in files:
            data = np.load(path)
            b = np.linalg.norm(data["b"], axis=1)
            self.assertEqual(len(b), len(data["volume"]))
            self.assertTrue(np.all(np.isfinite(b)))
            self.assertGreaterEqual(b.min(), 0.0)
            # The core material is linear, so small corner regions exceed real saturation (ticket B01).
            # The bulk of the core must stay in a physical range.
            order = np.argsort(b)
            share = np.cumsum(data["volume"][order]) / data["volume"].sum()
            self.assertLess(b[order][np.searchsorted(share, 0.95)], 2.0)
            self.assertLess(b.max(), 3.5)
            volume_mm3 = data["volume"].sum() * 1e9 * int(data["periodicity"])
            self.assertAlmostEqual(volume_mm3 / self.loaded["core_volume_mm3"], 1.0, delta=0.01)

    def test_t07_6_command_line_pipeline(self):
        with open(os.path.join(ROOT, "examples/params/motor_matched.json")) as f:
            params = json.load(f)
        params["analysis"].update({"positions": 4, "coil_current_A": 5.0})
        path = os.path.join(self.tmp, "matched4.json")
        with open(path, "w") as f:
            json.dump(params, f)
        run = subprocess.run([sys.executable, "-m", "emachine", "solve", "--params", path, "--run", os.path.join(self.tmp, "cli"),
                              "--jobs", "4"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout[-1500:] + run.stderr[-1500:])
        with open(os.path.join(self.tmp, "cli", "results.csv")) as f:
            rows = f.read().splitlines()
        header = rows[0].split(",")
        first = dict(zip(header, rows[1].split(",")))
        self.assertEqual(float(first["rotor_angle_deg"]), 0.0)
        self.assertAlmostEqual(float(first["flux_linkage_Wb"]) / 8.40e-3, 1.0, delta=0.02)


if __name__ == "__main__":
    unittest.main()
