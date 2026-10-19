"""T09: loss model."""

import math
import os
import tempfile
import unittest

import numpy as np

from helpers import coil_winding, copper_loss, phase_resistance

from emachine.physics import losses
from emachine.spec import load_spec

COIL = {"coil_area_mm2": 110.0, "turn_length_mm": 2 * math.pi * 24.0,
        "ampere_turns_peak": 200.0, "ampere_turns_rms": 200.0 / math.sqrt(2),
        "electrical_frequency_Hz": 100.0}


class LossTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec({"winding": {"fill_factor": 0.5}})

    def test_t09_1_copper_loss(self):
        expected = 1.72e-8 * (2 * math.pi * 0.024) * (200.0 / math.sqrt(2)) ** 2 / (110e-6 * 0.5)
        coil = coil_winding(self.spec, COIL["coil_area_mm2"], COIL["turn_length_mm"])
        self.assertAlmostEqual(copper_loss(self.spec, coil, COIL["ampere_turns_rms"], 20.0), expected, delta=1e-9)
        r = phase_resistance(self.spec, coil, 20, 20.0)
        self.assertAlmostEqual((COIL["ampere_turns_rms"] / 20) ** 2 * r, expected, delta=1e-9)

    def _synthetic_files(self, tmp, frequency_positions=12):
        """1000 elements of 1 mm3 with a uniform field B = 1 T * cos(angle) along x."""
        rng = np.random.default_rng(0)
        centroid = rng.uniform(0, 0.01, (1000, 3))
        files = []
        for k in range(frequency_positions):
            b = np.zeros((1000, 3))
            b[:, 0] = math.cos(math.pi * k / frequency_positions)
            path = os.path.join(tmp, f"core{k}.npz")
            np.savez_compressed(path, centroid=centroid, volume=np.full(1000, 1e-9), b=b, periodicity=1)
            files.append(path)
        return files

    def test_t09_2_uniform_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = losses.iron_loss(self.spec, COIL, self._synthetic_files(tmp))
        # A purely alternating field (axis ratio 0): only the alternating loss counts (T31).
        m = self.spec["materials"]["stator_core"]
        per_kg = m["k_hysteresis"] * 100 + m["k_eddy"] * 100 ** 2 + m["k_anomalous"] * 100 ** 1.5
        mass = 1000 * 1e-9 * 7450
        self.assertAlmostEqual(result["iron_loss_W"] / (per_kg * mass), 1.0, delta=1e-6)
        self.assertAlmostEqual(result["core_b_max_T"], 1.0, places=12)
        self.assertAlmostEqual(result["core_b_p95_T"], 1.0, places=12)
        self.assertAlmostEqual(result["core_mass_kg"], mass, places=12)

    def test_t09_3_frequency_dependence(self):
        material = self.spec["materials"]["stator_core"]
        only_h = dict(material, k_eddy=0.0, k_anomalous=0.0)
        only_e = dict(material, k_hysteresis=0.0, k_anomalous=0.0)
        self.assertAlmostEqual(losses.iron_loss_density(only_h, 200, 1.2) / losses.iron_loss_density(only_h, 100, 1.2), 2.0)
        self.assertAlmostEqual(losses.iron_loss_density(only_e, 200, 1.2) / losses.iron_loss_density(only_e, 100, 1.2), 4.0)
        self.assertAlmostEqual(losses.iron_loss_density(only_e, 100, 2.0) / losses.iron_loss_density(only_e, 100, 1.0), 4.0)
        self.assertAlmostEqual(losses.iron_loss_density(only_h, 100, 2.0) / losses.iron_loss_density(only_h, 100, 1.0),
                               2 ** material["alpha"])

    def test_t09_4_resample_identity(self):
        rng = np.random.default_rng(1)
        points = rng.uniform(0, 1, (700, 3))
        values = rng.uniform(0, 1, 700)
        np.testing.assert_array_equal(losses.resample_nearest(points, points, values), values)

    def test_t09_5_resample_shifted_and_different_counts(self):
        rng = np.random.default_rng(2)
        grid = np.stack(np.meshgrid(*[np.arange(10.0)] * 3, indexing="ij"), axis=-1).reshape(-1, 3)   # spacing 1
        values = rng.uniform(0, 1, len(grid))
        shifted = grid + 0.01
        order = rng.permutation(len(grid))
        np.testing.assert_array_equal(losses.resample_nearest(grid, shifted[order], values[order]), values)
        fewer = order[:900]                       # the other position has fewer elements
        out = losses.resample_nearest(grid, shifted[fewer], values[fewer])
        self.assertEqual(out.shape, (1000,))
        kept = np.zeros(1000, dtype=bool)
        kept[fewer] = True
        np.testing.assert_array_equal(out[kept], values[kept])

    def test_peak_is_taken_over_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            centroid = np.array([[0.0, 0, 0], [1.0, 0, 0]])
            files = []
            for k, (b0, b1) in enumerate([(0.2, 1.5), (0.9, 0.1), (0.5, 0.7)]):
                path = os.path.join(tmp, f"c{k}.npz")
                np.savez_compressed(path, centroid=centroid[::-1] if k == 1 else centroid, volume=np.array([1e-6, 2e-6]),
                                    b=np.array([[b0, 0, 0], [0, b1, 0]])[::-1] if k == 1 else np.array([[b0, 0, 0], [0, b1, 0]]),
                                    periodicity=18)
                files.append(path)
            volume, peak = losses.core_peak_field(files)
        np.testing.assert_allclose(peak, [0.9, 1.5])
        np.testing.assert_allclose(volume, [18e-6, 36e-6])


if __name__ == "__main__":
    unittest.main()
