"""B01: saturation with nonlinear B-H curves."""

import json
import math
import os
import shutil
import tempfile
import unittest

import numpy as np

from helpers import slow

from emachine.machines.tfm import design  # noqa: F401
from emachine.pipeline import evaluate  # noqa: F401
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import SpecError, load_spec

from emachine.cli.solve import load_settings
from emachine.io.process import StageError
from emachine.pipeline import sweep
from emachine.solvers.elmer import materials
from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS

MU0 = 4e-7 * math.pi
LINEAR = {"materials": {"stator_core": {"saturation_T": None}, "rotor_iron": {"saturation_T": None}}}


class CurveTest(unittest.TestCase):
    def test_b01_1_generated_curve(self):
        fine = materials.bh_table(500.0, 1.9, b_max=0.02, step=0.001)
        b, h = fine[1]
        self.assertAlmostEqual(b / (MU0 * h), 500.0, delta=5.0)              # initial permeability
        table = materials.bh_table(500.0, 1.9)
        self.assertEqual(table[0], (0.0, 0.0))
        bs = np.array([p[0] for p in table])
        hs = np.array([p[1] for p in table])
        self.assertTrue(np.all(np.diff(hs) > 0))
        slope = np.diff(bs) / np.diff(hs)                                    # differential permeability
        self.assertTrue(np.all(np.diff(slope) < 0))                          # ever harder to magnetise
        high = slope[bs[1:] > 3.5]
        self.assertTrue(np.all(np.abs(high / MU0 - 1) < 0.05))
        # polarisation approaches the saturation value
        self.assertAlmostEqual(bs[-1] - MU0 * hs[-1], 1.9, delta=0.01)
        with self.assertRaises(ValueError):
            materials.bh_table(1.0, 1.9)

    def test_b01_2_measured_curve(self):
        analysis = {"stator_core_bh_curve": [[100, 0.2], [1000, 1.0], [10000, 1.6]], "stator_core_mu_r": 500,
                    "stator_core_saturation_T": 1.9}
        self.assertEqual(materials.material_curve(analysis, "stator_core"), [(0.0, 0.0), (0.2, 100.0), (1.0, 1000.0), (1.6, 10000.0)])
        analysis["stator_core_bh_curve"] = [[100, 0.2], [1000, 0.1], [10000, 1.6]]
        with self.assertRaises(StageError):
            materials.material_curve(analysis, "stator_core")
        self.assertIsNone(materials.material_curve({"rotor_iron_bh_curve": None, "rotor_iron_saturation_T": None, "rotor_iron_mu_r": 1000}, "rotor_iron"))
        generated = materials.material_curve({"rotor_iron_bh_curve": None, "rotor_iron_saturation_T": 2.1, "rotor_iron_mu_r": 1000}, "rotor_iron")
        self.assertEqual(generated, materials.bh_table(1000, 2.1))

    def test_b01_3_material_section(self):
        linear = materials.material_block(4, "stator core", 500.0)
        self.assertIn("Relative Permeability = 500", linear)
        self.assertNotIn("H-B Curve", linear)
        nonlinear = materials.material_block(4, "stator core", 500.0, materials.bh_table(500.0, 1.9))
        self.assertIn('H-B Curve = Variable "dummy"', nonlinear)
        self.assertNotIn("Relative Permeability", nonlinear)
        self.assertEqual(nonlinear.count("\n      "), len(materials.bh_table(500.0, 1.9)))
        self.assertTrue(nonlinear.rstrip().endswith("End"))

    def test_b01_4_specification(self):
        spec = load_spec({})
        self.assertEqual(spec["materials"]["stator_core"]["saturation_T"], 1.9)
        params = design.to_parameters(spec, REFERENCE_DESIGN)
        self.assertEqual(params["analysis"]["stator_core_saturation_T"], 1.9)
        self.assertEqual(params["analysis"]["rotor_iron_saturation_T"], 2.1)
        linear = design.to_parameters(load_spec(LINEAR), REFERENCE_DESIGN)
        self.assertIsNone(linear["analysis"]["stator_core_saturation_T"])
        curve = [[200, 0.3], [2000, 1.1], [20000, 1.7]]
        measured = design.to_parameters(load_spec({"materials": {"stator_core": {"bh_curve": curve}}}), REFERENCE_DESIGN)
        self.assertEqual(measured["analysis"]["stator_core_bh_curve"], curve)
        for bad in ([[200, 0.3], [100, 1.1], [20000, 1.7]], [[200, 0.3]], "steep", [[200, 0.3], [2000, "x"], [3000, 1.5]]):
            with self.assertRaises(SpecError, msg=str(bad)) as ctx:
                load_spec({"materials": {"stator_core": {"bh_curve": bad}}})
            self.assertIn("materials.stator_core.bh_curve", str(ctx.exception))
        with self.assertRaises(SpecError):
            load_spec({"materials": {"stator_core": {"saturation_T": 9.0}}})
        with self.assertRaises(SpecError):
            load_spec({"materials": {"rotor_iron": {"mu_r": 1.0}}})

    def test_pipeline_settings_accept_material_keys(self):
        params = design.to_parameters(load_spec({}), REFERENCE_DESIGN)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.json")
            with open(path, "w") as f:
                json.dump(params, f)
            _, analysis = load_settings(path)
        self.assertEqual(analysis["stator_core_saturation_T"], 1.9)
        self.assertIsNone(ANALYSIS_DEFAULTS["stator_core_saturation_T"])   # the pipeline alone stays linear

    def test_b01_5_flux_density_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = os.path.join(tmp, "core.npz")
            np.savez_compressed(core, centroid=np.zeros((4, 3)), volume=np.full(4, 1e-6),
                                b=np.tile([2.0, 0.0, 0.0], (4, 1)), periodicity=18)

            def analyse(parameters, positions, rundir, jobs):
                angle = math.pi * np.arange(positions) / positions
                return {"torque_Nm": np.sin(angle) ** 2, "flux_per_turn_Wb": 1e-4 * np.cos(angle), "core_field_files": [core]}

            def violation(overrides):
                record = evaluate.evaluate(load_spec(overrides), REFERENCE_DESIGN, tmp, analyse, use_cache=False)
                return record["constraints"]["core_flux_density"], record["analysis"]["core_material"]

            self.assertEqual(violation({}), (0.0, "saturating"))
            v, kind = violation(LINEAR)
            self.assertEqual(kind, "linear")
            self.assertAlmostEqual(v, 2.0 / 1.8 - 1.0, places=12)
            v, _ = violation({"limits": {"max_core_flux_density_T": 1.5}})
            self.assertAlmostEqual(v, 2.0 / 1.5 - 1.0, places=12)
            v, _ = violation(dict(LINEAR, limits={"max_core_flux_density_T": 2.5}))
            self.assertEqual(v, 0.0)


@slow
class SaturationSolveTest(unittest.TestCase):
    """Field solutions of the reference design at 90 electrical degrees (5 mechanical degrees)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="tfm_b01_")
        cls.loads = [0.25, 0.5, 1.0, 2.0]
        cls.ni = design.derived(load_spec({}), design.clip(load_spec({}), REFERENCE_DESIGN))["ampere_turns_peak"]
        cls.rows = {}
        for name, overrides in (("linear", LINEAR), ("saturating", {}),
                                ("almost_linear", {"materials": {"stator_core": {"saturation_T": 1000.0},
                                                                 "rotor_iron": {"saturation_T": 1000.0}}})):
            spec = load_spec(overrides) if name != "almost_linear" else None
            if name == "almost_linear":      # beyond the range the specification accepts: set on the parameters
                params = design.to_parameters(load_spec(LINEAR), REFERENCE_DESIGN)
                params["analysis"].update({"stator_core_saturation_T": 1000.0, "rotor_iron_saturation_T": 1000.0})
                loads = [1.0]
            else:
                params = design.to_parameters(spec, REFERENCE_DESIGN)
                loads = cls.loads
            analysis = dict(ANALYSIS_DEFAULTS)
            analysis.update(params["analysis"])
            rows, failed = sweep.run_rows(params, analysis, [5.0] * len(loads), os.path.join(cls.tmp, name), jobs=6,
                                            currents=[-k * cls.ni for k in loads], core_field=True)
            assert not failed, failed
            cls.rows[name] = rows

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_b01_6_almost_linear_curve_matches_linear(self):
        linear = self.rows["linear"][2]
        curve = self.rows["almost_linear"][0]
        self.assertGreater(curve["nonlinear_iterations"], 0)
        self.assertAlmostEqual(curve["torque_Nm"] / linear["torque_Nm"], 1.0, delta=0.01)
        self.assertAlmostEqual(curve["flux_linkage_Wb"] / linear["flux_linkage_Wb"], 1.0, delta=0.01)

    def test_b01_7_load_sweep(self):
        per_at = []
        for k, lin, sat in zip(self.loads, self.rows["linear"], self.rows["saturating"]):
            self.assertGreater(sat["nonlinear_iterations"], 0)
            self.assertLessEqual(sat["nonlinear_iterations"], 40)
            self.assertEqual(lin["nonlinear_iterations"], 0)
            self.assertLessEqual(sat["torque_Nm"], lin["torque_Nm"] * 1.001)
            per_at.append(sat["torque_Nm"] / (k * self.ni))
            data = np.load(sat["core_field_file"])
            b = np.linalg.norm(data["b"], axis=1)
            order = np.argsort(b)
            share = np.cumsum(data["volume"][order]) / data["volume"].sum()
            self.assertLess(b[order][np.searchsorted(share, 0.95)], 2.0)
        # Torque per ampere-turn must not rise with load. A tolerance of 0.5 % allows for the small
        # load-independent torque (about 1 mNm of cogging and mesh noise) left at this position.
        for lower, higher in zip(per_at, per_at[1:]):
            self.assertLess(higher, lower * 1.005)
        self.assertLess(per_at[2], 0.995 * per_at[0])              # reference load: already lower
        self.assertLess(per_at[3], 0.95 * per_at[0])               # twice the reference load: clear saturation
        print("\nload sweep at 90 electrical degrees (load, linear torque, saturating torque, Newton iterations):")
        for k, lin, sat in zip(self.loads, self.rows["linear"], self.rows["saturating"]):
            print(f"  {k:4.2f}  {lin['torque_Nm']:.4f}  {sat['torque_Nm']:.4f}  {sat['nonlinear_iterations']}")


if __name__ == "__main__":
    unittest.main()
