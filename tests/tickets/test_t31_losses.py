"""T31: rotational stator core loss, rotor eddy-current loss, loaded-field core loss."""

import math
import os
import tempfile
import unittest

import numpy as np
from helpers import ROOT, coupled, machine_of

from emachine.physics import losses
from emachine.physics import thermal
from emachine.machines.tfm import design
from emachine.spec import SpecError, load_spec

SOMALOY = load_spec({})["materials"]["stator_core"]


def circle(n, bmaj, bmin, harmonic=1, elements=1):
    t = 2 * math.pi * np.arange(n) / n
    b = np.zeros((elements, n, 3))
    b[:, :, 0] = bmaj * np.cos(harmonic * t)
    b[:, :, 1] = bmin * np.sin(harmonic * t)
    return b


class EllipseTest(unittest.TestCase):
    def test_t31_1_axes_of_harmonics(self):
        b = circle(48, 1.2, 0.3) + circle(48, 0.1, 0.0, harmonic=3)
        bmaj, bmin = losses.harmonic_ellipses(b)
        self.assertAlmostEqual(bmaj[0, 0], 1.2)
        self.assertAlmostEqual(bmin[0, 0], 0.3)
        self.assertAlmostEqual(bmaj[0, 2], 0.1)
        self.assertAlmostEqual(bmin[0, 2], 0.0)
        self.assertAlmostEqual(bmaj[0, 1], 0.0)
        # A tilted ellipse in 3D has the same axes.
        rotation = np.array([[0.36, 0.48, -0.8], [-0.8, 0.6, 0.0], [0.48, 0.64, 0.6]])
        bmaj2, bmin2 = losses.harmonic_ellipses(circle(48, 1.2, 0.3) @ rotation.T)
        self.assertAlmostEqual(bmaj2[0, 0], 1.2)
        self.assertAlmostEqual(bmin2[0, 0], 0.3)

    def test_t31_2_rotational_hysteresis(self):
        rot = SOMALOY["rotational"]
        self.assertAlmostEqual(float(losses.rotational_hysteresis_per_cycle(rot, 0.0)), 0.0)
        # Mid-range: rotation loses about twice the alternating hysteresis loss (Guo et al. 2003, 2004).
        ratio = losses.rotational_hysteresis_per_cycle(rot, 1.0) / SOMALOY["k_hysteresis"]
        self.assertGreater(ratio, 1.5)
        self.assertLess(ratio, 2.2)
        # Towards saturation the rotational hysteresis loss falls again.
        values = losses.rotational_hysteresis_per_cycle(rot, np.linspace(0.2, 2.0, 10))
        self.assertLess(values[-1], values.max())

    def test_t31_3_element_loss_alternating_and_circular(self):
        f = 300.0
        alt_h, alt_e, alt_x = losses.stator_element_coefficients(SOMALOY, circle(48, 1.0, 0.0))
        expected = SOMALOY["k_hysteresis"] * f + SOMALOY["k_eddy"] * f ** 2 + SOMALOY["k_anomalous"] * f ** 1.5
        self.assertAlmostEqual((alt_h * f + alt_e * f ** 2 + alt_x * f ** 1.5)[0], expected)
        rot_h, rot_e, rot_x = losses.stator_element_coefficients(SOMALOY, circle(48, 1.0, 1.0))
        rot = SOMALOY["rotational"]
        expected = float(losses.rotational_hysteresis_per_cycle(rot, 1.0)) * f + rot["k_eddy"] * f ** 2
        self.assertAlmostEqual((rot_h * f + rot_e * f ** 2 + rot_x * f ** 1.5)[0], expected)
        # Without rotational data the circle counts as alternating on its major axis.
        plain = dict(SOMALOY, rotational=None)
        h, e, x = losses.stator_element_coefficients(plain, circle(48, 1.0, 1.0))
        self.assertAlmostEqual(h[0], alt_h[0])


class SeriesTest(unittest.TestCase):
    def _files(self, tmp, half, rotor=True):
        """Two stator elements with B = (cos, sin) * (1, 0.5); rotor iron with a field that turns
        once per period in the rotor frame, magnets with a constant field."""
        n = 12 if half else 24
        period = 20.0                                    # electrical period in degrees (periodicity 18)
        files = []
        for k in range(n):
            angle = k * period / 24
            t = 2 * math.pi * angle / period
            data = {"centroid": np.array([[0.04, 0.0, 0.0], [0.04, 0.001, 0.0]]), "volume": np.array([1e-9, 1e-9]),
                    "b": np.array([[math.cos(t), 0.5 * math.sin(t), 0.0]] * 2), "periodicity": 18,
                    "angle_deg": angle}
            if rotor:
                phis = np.radians(np.array([2.0, 6.0, 12.0, 16.0]))         # rotor frame, inside the sector
                phi = phis + math.radians(angle)
                centre = np.column_stack([0.05 * np.cos(phi), 0.05 * np.sin(phi), np.zeros(4)])
                back = np.column_stack([0.05 * np.cos(phis), 0.05 * np.sin(phis), np.zeros(4)])
                # Elements one pole pitch apart (2 and 12 deg, 6 and 16 deg) see the reversed field. The
                # symmetry of the machine, b(x, t + T/2) = -b(x - pitch, t), then allows only even
                # harmonics in the rotor frame: the iron sees 0.2 T at twice the electrical frequency.
                sign = np.array([1.0, 1.0, -1.0, -1.0])
                ripple = np.array([0.2, 0.0, 0.2, 0.0]) * math.cos(2 * t)
                b = np.column_stack([ripple * sign, np.full(4, 0.8) * sign, np.zeros(4)])
                data.update(rotor_centroid=back, rotor_volume=np.full(4, 1e-9), rotor_b=b,
                            rotor_kind=np.array([0, 2, 0, 2], dtype=np.int8),
                            rotor_eddy_width_m=np.array([0.003, 0.003, 0.008]))
                del centre
            path = os.path.join(tmp, f"c{k}.npz")
            np.savez(path, **data)
            files.append(path)
        return files

    def test_t31_5_half_period_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            full_v, full_b = losses.stator_series(self._files(tmp, half=False))
        with tempfile.TemporaryDirectory() as tmp:
            half_v, half_b = losses.stator_series(self._files(tmp, half=True))
        self.assertEqual(full_b.shape, (2, 24, 3))
        np.testing.assert_allclose(half_b, full_b, atol=1e-12)
        np.testing.assert_allclose(half_v, full_v)

    def test_t31_6_rotor_series_and_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            full = losses.rotor_series(self._files(tmp, half=False))
        with tempfile.TemporaryDirectory() as tmp:
            half = losses.rotor_series(self._files(tmp, half=True))
        np.testing.assert_allclose(half[2], full[2], atol=1e-12)
        np.testing.assert_array_equal(half[1], full[1])
        bmaj, _ = losses.harmonic_ellipses(full[2])
        iron, magnet = full[1] == 0, full[1] == 2
        np.testing.assert_allclose(bmaj[iron, 1], 0.2, atol=1e-12)          # iron: 0.2 T at 2 f
        np.testing.assert_allclose(bmaj[iron, 0], 0.0, atol=1e-12)
        np.testing.assert_allclose(bmaj[magnet], 0.0, atol=1e-12)           # magnets: constant field
        spectra = losses.rotor_spectra(full)
        volume = 2 * 1e-9 * 18
        self.assertAlmostEqual(spectra["rotor_iron_spectrum"][1], volume * 0.04)
        self.assertAlmostEqual(spectra["rotor_iron_width_m"], 0.003)
        self.assertAlmostEqual(spectra["rotor_iron_b_dc_T"], 0.8)
        self.assertEqual(sum(spectra["magnet_spectrum"]), 0.0)
        # Low frequency, linear material: the thin-plate formula.
        materials = {"rotor_iron": {"conductivity_S_m": 1e7, "density_kg_m3": 7850.0, "mu_r": 1.0}}
        loss = losses.rotor_loss(spectra, 1.0, materials)["rotor_iron"]
        expected = math.pi ** 2 * 0.003 ** 2 * 1e7 / 6 * volume * 0.04 * 2 ** 2
        self.assertAlmostEqual(float(loss) / expected, 1.0, places=6)

    def test_t31_7_skin_effect_and_permeability(self):
        self.assertAlmostEqual(float(losses.skin_factor(1e-4)), 1.0)
        self.assertAlmostEqual(float(losses.skin_factor(0.5)), 1.0, places=2)
        self.assertAlmostEqual(float(losses.skin_factor(100.0)), 0.03)
        values = losses.skin_factor(np.linspace(0.01, 30, 200))
        self.assertTrue(np.all(np.diff(values) <= 1e-12))
        # Froehlich-Kennelly material: initial permeability at zero field, falling with saturation.
        steel = {"mu_r": 2000.0, "saturation_T": 2.0}
        self.assertAlmostEqual(losses.incremental_mu_r(steel, 0.0), 2000.0, delta=1.0)
        self.assertLess(losses.incremental_mu_r(steel, 1.5), losses.incremental_mu_r(steel, 0.5))
        self.assertEqual(losses.incremental_mu_r({"mu_r": 1.05}, 1.0), 1.05)
        curve = {"bh_curve": [[100, 0.5], [300, 1.0], [1000, 1.5]]}
        self.assertAlmostEqual(losses.incremental_mu_r(curve, 1.2), 0.5 / 700 / losses.MU0)

    def test_t31_8_noise_floor_is_removed(self):
        rng = np.random.default_rng(3)
        n = 24
        t = 2 * math.pi * np.arange(n) / n
        b = np.zeros((50, n, 3))
        b[:, :, 0] = 0.3 * np.cos(t)
        noisy = b + rng.normal(0, 0.01, b.shape)
        series = (np.full(50, 1e-9), np.zeros(50, dtype=np.int64), noisy, np.array([0.003, 0.003, 0.008]))
        spectrum = np.array(losses.rotor_spectra(series)["rotor_iron_spectrum"])
        # Fundamental kept, the floor of the higher harmonics removed (on average).
        self.assertAlmostEqual(spectrum[0] / (50e-9 * 0.09), 1.0, delta=0.05)
        self.assertLess(spectrum[5:].sum(), 0.1 * spectrum[0] * 0.01)

    def test_t31_9_coefficients_and_loss_at(self):
        spec = load_spec({"materials": {"rotor_iron": {"conductivity_S_m": 1e7}}})
        with tempfile.TemporaryDirectory() as tmp:
            c = losses.iron_loss_coefficients(spec, self._files(tmp, half=True))
        for name in losses.COEFFICIENTS + losses.SPECTRA:
            self.assertIn(name, c)
        stator, rotor = losses.loss_at(c, 300.0, spec["materials"])
        self.assertAlmostEqual(float(stator), c["a_h"] * 300 + c["a_e"] * 300 ** 2 + c["a_x"] * 300 ** 1.5)
        self.assertAlmostEqual(float(rotor), float(sum(losses.rotor_loss(c, 300.0, spec["materials"]).values())))
        self.assertGreater(float(rotor), 0.0)
        # Old cached load levels without the new data still work.
        stator, rotor = losses.loss_at({"a_h": 1.0, "a_e": 0.0}, 10.0, spec["materials"])
        self.assertEqual((float(stator), float(rotor)), (10.0, 0.0))
        # Without conductivity there is no rotor loss.
        quiet = load_spec({"materials": {"rotor_iron": {"conductivity_S_m": None}, "magnet": {"conductivity_S_m": None}}})
        self.assertEqual(float(losses.loss_at(c, 300.0, quiet["materials"])[1]), 0.0)


class SpecAndThermalTest(unittest.TestCase):
    def test_t31_10_spec_options(self):
        spec = load_spec({"materials": {"stator_core": {"rotational": None}, "rotor_housing": {"conductivity_S_m": 3.5e7}}})
        self.assertIsNone(spec["materials"]["stator_core"]["rotational"])
        self.assertEqual(spec["materials"]["rotor_housing"]["conductivity_S_m"], 3.5e7)
        self.assertEqual(spec["materials"]["stator_core"]["rotational"] is None, True)
        with self.assertRaises(SpecError):
            load_spec({"materials": {"magnet": {"conductivity_S_m": -1}}})
        with self.assertRaises(SpecError):
            load_spec({"materials": {"stator_core": {"rotational": {"a1": 0}}}})

    def test_t31_11_rotor_loss_heats_the_rotor(self):
        spec = load_spec(os.path.join(ROOT, "examples", "user_tr48.json"))
        import json
        with open(os.path.join(ROOT, "examples", "user_tr48_design.json")) as f:
            values = design.clip(spec, json.load(f))
        rise = thermal.response(machine_of(spec).thermal_network(spec, values), ("winding", "core", "rotor"))
        self.assertEqual(len(rise["rotor"]), 3)
        # Per watt, rotor loss heats the magnets more than stator iron loss does.
        self.assertGreater(rise["rotor"][2], rise["rotor"][1])
        base = coupled(spec, values, 5.0)
        hot = coupled(spec, values, 5.0, rotor_loss_W=5.0)
        self.assertGreater(hot["magnet_C"], base["magnet_C"])


class PipelineTest(unittest.TestCase):
    def test_t31_12_rotor_eddy_dimensions(self):
        from emachine.machines.tfm.geometry.rotors.eddy import eddy_widths
        rotor = {"configuration": "outrunner", "type": "halbach", "inner_diameter": 70.6, "outer_diameter": 80.0,
                 "shaft_diameter": 30.0, "stack_length": 9.0, "poles": 48, "magnet_thickness": 2.0,
                 "magnet_arc_ratio": 0.85, "segments_per_pole": 2, "fc_magnet_height": 12.0, "fc_magnet_width": 4.0,
                 "magnet_rows": 1, "row_gap": 0.0, "alternate_rows": False}
        widths = eddy_widths(rotor) * 1000
        self.assertAlmostEqual(widths[0], 40.0 - 35.3 - 2.0)
        self.assertAlmostEqual(widths[2], math.pi * 70.6 / 48 / 2)


if __name__ == "__main__":
    unittest.main()
