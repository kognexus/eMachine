"""T22: claw-pole stator in the parametric model, and the grid of stator types."""

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import FEATURESCRIPT, ROOT, slow

from emachine.machines.tfm import design
from emachine.pipeline import evaluate
from emachine.machines.tfm import checks
from emachine.machines.tfm.cad import sheet as onshape
from emachine.spec import load_spec

THREE = os.path.join(ROOT, "examples/tfm_three_phase.json")


def cp_spec(change=None):
    with open(THREE) as f:
        user = json.load(f)
    user["machine"]["stator"] = "claw_pole"
    if change:
        change(user)
    return load_spec(user)


def cp_design(spec, **changes):
    values = {"pole_pairs": 18, "tooth_span": 0.65, "leg_width_mm": 2.0, "slot_height_mm": 10.0, "yoke_height_mm": 3.0,
              "magnet_thickness_mm": 2.5, "current_density_A_mm2": 5.0, "rotor_iron_mm": 3.0,
              "claw_root_height_mm": 3.0, "claw_tip_gap_mm": 1.5}
    values.update(changes)
    return design.clip(spec, values)


class ClawPoleModelTest(unittest.TestCase):
    def setUp(self):
        self.spec = cp_spec()
        self.values = cp_design(self.spec)

    def test_t22_4_variables_parameters_and_sheet(self):
        names = [v["name"] for v in design.variables(self.spec)]
        self.assertIn("claw_root_height_mm", names)
        self.assertIn("claw_tip_gap_mm", names)
        self.assertNotIn("bridge_height_mm", names)
        parameters = design.to_parameters(self.spec, self.values)
        stator, rotor = parameters["stator"], parameters["rotor"]
        self.assertEqual(stator["core_type"], "cp")
        self.assertEqual((stator["claw_root_height"], stator["claw_tip_gap"]), (3.0, 1.5))
        self.assertEqual(stator["claw_tip_height"], 2.0)                 # not below the minimum iron thickness
        self.assertEqual((rotor["magnet_rows"], rotor["alternate_rows"]), (1, False))   # the claws span the width
        self.assertEqual(design.from_parameters(self.spec, parameters), self.values)
        d = design.derived(self.spec, self.values)
        # Outer radius = rotor iron + magnet + air gap + claws + coil window + yoke + what is left inside.
        self.assertAlmostEqual(d["stator_radius"], 40.0 - 3.0 - 2.5 - 0.5)
        self.assertAlmostEqual(d["stator_far_radius"], d["stator_radius"] - (3.0 + 10.0 + 3.0))
        self.assertAlmostEqual(d["coil_height"], 10.0 - 2 * 0.5)
        self.assertAlmostEqual(d["coil_r0"], d["stator_far_radius"] + 3.0 + 0.5)
        self.assertEqual(checks.violations(checks.check(self.spec, self.values)), [])

        with open(os.path.join(FEATURESCRIPT, "tfm_stator.fs")) as f:
            labels = set(re.findall(r'annotation\s*\{\s*"Name"\s*:\s*"([^"]+)"', f.read()))
        rows = {r["field"]: r for s in onshape.sheet(parameters) if "stator" in s["title"] for r in s["rows"]}
        for field in ("Claw root height", "Claw tip height", "Claw tip gap"):
            self.assertIn(field, rows)
            self.assertIn(field, labels)
        self.assertEqual(rows["Core structure"]["text"], "Claw-pole (CP) core")
        self.assertIn(rows["Core structure"]["text"], labels)
        self.assertNotIn("I-bridge height", rows)
        sheet_checks = {r["field"]: r["value"] for s in onshape.sheet(parameters) if "Checks" in s["title"] for r in s["rows"]}
        self.assertAlmostEqual(sheet_checks["Innermost diameter (inner end of the stator cores)"], 2 * d["stator_far_radius"])

    def test_claws_must_stay_apart(self):
        wide = cp_design(self.spec, tooth_span=0.95, claw_root_height_mm=10.0, pole_pairs=32)
        names = [c.name for c in checks.violations(checks.check(self.spec, wide))]
        self.assertIn("claw_overlap", names)
        # Frames may merge at their inner ends: that is not a violation for a claw-pole stator.
        deep = cp_design(self.spec, tooth_span=0.8, slot_height_mm=14.0)
        names = [c.name for c in checks.violations(checks.check(self.spec, deep))]
        self.assertNotIn("core_overlap", names)

    def test_stand_in_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = evaluate.evaluate(self.spec, self.values, tmp, evaluate.analytic_stand_in)
        self.assertTrue(record["analysed"])
        self.assertGreater(record["thermal"]["winding_C"], 25.0)


class GridTest(unittest.TestCase):
    def test_t22_5_grid_of_two_types(self):
        with tempfile.TemporaryDirectory() as tmp, open(THREE) as f:
            user = json.load(f)
            for kind in ("u", "cp"):
                user["machine"]["stator"] = kind            # old codes are read under the new key (T43)
                spec_file = os.path.join(tmp, kind + ".json")
                with open(spec_file, "w") as out:
                    json.dump(user, out)
                result = subprocess.run([sys.executable, "-m", "emachine", "optimize", "--spec", spec_file,
                                         "--run", os.path.join(tmp, "runs", kind), "--dry-run", "--population", "12",
                                         "--generations", "2"], capture_output=True, text=True, cwd=ROOT)
                self.assertEqual(result.returncode, 0, result.stdout[-1200:] + result.stderr[-1200:])
            result = subprocess.run([sys.executable, "-m", "emachine", "compare", "--runs",
                                     os.path.join(tmp, "runs"), "--note", "z=needs a rotor of its own"],
                                    capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout[-1200:] + result.stderr[-1200:])
            with open(os.path.join(tmp, "runs", "grid.md")) as f:
                grid = f.read()
        self.assertIn("| U-core |", grid)
        self.assertIn("| Claw pole |", grid)
        self.assertIn("| Z-core | not run: needs a rotor of its own |", grid)
        self.assertIn("claw_root_height_mm", grid)
        self.assertEqual(len(re.findall(r"^\| (U-core|Claw pole) \| (highest torque|best compromise|lowest loss) \|",
                                        grid, flags=re.M)), 12)       # six rows in the design table, six in the type-specific table


@slow
class ClawPoleFieldTest(unittest.TestCase):
    def test_t22_1_2_3_geometry_mesh_and_field(self):
        from emachine.pipeline import sweep
        from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS
        spec = cp_spec()
        values = cp_design(spec)
        d = design.derived(spec, values)
        parameters = design.to_parameters(spec, values)
        analysis = dict(ANALYSIS_DEFAULTS)
        analysis.update(parameters["analysis"])
        analysis.update({"coil_turns": 1})
        fluxes, torques = [], []
        with tempfile.TemporaryDirectory() as tmp:
            for k, fraction in enumerate((0.0, 0.5, 1.0)):                     # aligned, quadrature, next pole
                angle = fraction * 180.0 / values["pole_pairs"]
                row = sweep.solve_position(parameters, analysis, angle, os.path.join(tmp, f"p{k}"), current=0.0)
                fluxes.append(row["flux_linkage_Wb"])
                torques.append(row["torque_Nm"])
                if k == 0:
                    with open(os.path.join(tmp, "p0", "sector.regions.json")) as f:
                        meta = json.load(f)
        regions = meta["regions"]
        periodicity = meta["sector"]["periodicity"]
        self.assertEqual(periodicity, values["pole_pairs"])
        coil = sum(r["volume_mm3"] for r in regions.values() if r["kind"] == "coil") * periodicity
        expected = math.pi * (d["coil_r1"] ** 2 - d["coil_r0"] ** 2) * d["coil_width"]
        self.assertAlmostEqual(coil / expected, 1.0, delta=0.01)
        core = sum(r["volume_mm3"] for r in regions.values() if r["side"] == "stator" and r["kind"] == "core") * periodicity
        # Bounds from the outline of the Onshape feature: frames alone, and frames plus links without overlap.
        hw, t = d["phase_width"] / 2, d["core_thickness"]
        zc, zt, gap = d["claw_root_height"], d["claw_tip_height"], d["claw_tip_gap"]
        frame = (2 * hw * d["stator_height"] - d["slot_width"] * d["slot_height"]
                 - 0.5 * (zc + zt) * 0 - (d["slot_width"] * zc - 0.5 * (zc + zt) * (d["slot_width"] - gap))) * t
        link = 2 * math.pi * (d["stator_far_radius"] + d["yoke_height"] / 2) / (2 * values["pole_pairs"]) \
            * d["leg_width"] * d["yoke_height"]
        frames = 2 * values["pole_pairs"] * frame
        self.assertGreater(core, 0.9 * frames)
        self.assertLess(core, 1.02 * (frames + 2 * values["pole_pairs"] * link * 1.5))
        # No load: the coil flux reverses over one pole pitch and passes through zero in between.
        self.assertGreater(abs(fluxes[0]), 5e-6)
        self.assertAlmostEqual(fluxes[2] / fluxes[0], -1.0, delta=0.05)
        self.assertLess(abs(fluxes[1]), 0.15 * abs(fluxes[0]))
        self.assertTrue(all(np.isfinite(torques)))
        print(f"\\nT22: claw pole, no load: flux per turn {fluxes[0] * 1e6:.1f}, {fluxes[1] * 1e6:.1f}, {fluxes[2] * 1e6:.1f} uWb; "
              f"core volume {core:.0f} mm3 (frames {frames:.0f}), coil {coil:.0f} mm3")


if __name__ == "__main__":
    unittest.main()


class PoleShiftTest(unittest.TestCase):
    def spec(self, shift, kind="ui"):
        with open(THREE) as f:
            user = json.load(f)
        user["machine"].update({"stator_type": kind, "pole_shift_el_deg": shift})
        return load_spec(user)

    def test_pole_shift_mapping(self):
        values = {"pole_pairs": 18, "tooth_span": 0.6, "leg_width_mm": 2.0, "slot_height_mm": 10.0,
                  "yoke_height_mm": 4.0, "magnet_thickness_mm": 2.0, "current_density_A_mm2": 5.0,
                  "rotor_iron_mm": 3.0, "bridge_height_mm": 2.5}
        plain = design.to_parameters(self.spec(0.0), values)
        self.assertNotIn("pole_shift_deg", plain["stator"])
        shifted = design.to_parameters(self.spec(30.0), values)
        self.assertAlmostEqual(shifted["stator"]["pole_shift_deg"], 30.0 / 18)      # electrical to mechanical
        self.assertEqual(checks.violations(checks.check(self.spec(30.0), design.clip(self.spec(30.0), values))), [])
        odd = dict(values, pole_pairs=17)
        names = [c.name for c in checks.violations(checks.check(self.spec(30.0), design.clip(self.spec(30.0), odd)))]
        self.assertIn("pole_shift_needs_even_pole_pairs", names)
        from emachine.spec import SpecError
        with self.assertRaises(SpecError):
            self.spec(30.0, "cp")
        rows = {r["field"]: r for s in onshape.sheet(dict(shifted, machine={"phases": 3, "phase_spacing_mm": 1.0}))
                if "stator" in s["title"] for r in s["rows"]}
        self.assertEqual(rows["Number of phases"]["text"], "3")
        self.assertEqual(rows["Phase spacing"]["text"], "1.000 mm")
        self.assertEqual(rows["Pole shift angle"]["text"], "1.6667 deg")


@slow
class GeometryOfAllTypesTest(unittest.TestCase):
    def test_t22_6_all_six_core_types_build(self):
        base = {"air_gap_radius": 34.0, "pole_pairs": 18, "inner_stator": True, "tooth_span": 0.6, "leg_width": 2.0,
                "slot_width": 5.0, "slot_height": 8.0, "yoke_height": 3.0, "bridge_height": 2.5, "claw_root_height": 3.0,
                "claw_tip_height": 2.0, "claw_tip_gap": 1.5, "mid_leg_width": 4.0, "z_tooth_height": 4.0,
                "z_tooth_width": 3.0, "z_slot_gap": 1.0, "z_rotor_gap": 3.0, "coil_height": 6.0, "coil_clearance": 0.5}
        volumes = {}
        with tempfile.TemporaryDirectory() as tmp:
            for kind in ("u", "ui", "cp", "c", "e", "z"):
                params = os.path.join(tmp, kind + ".json")
                with open(params, "w") as f:
                    json.dump({"stator": dict(base, core_type=kind)}, f)
                result = subprocess.run([sys.executable, "-m", "emachine", "mesh", "--params", params,
                                         "--stator-only", "--out", os.path.join(tmp, kind + ".step")],
                                        capture_output=True, text=True, cwd=tmp)
                self.assertEqual(result.returncode, 0, kind + ": " + result.stdout[-600:] + result.stderr[-600:])
                self.assertTrue(os.path.getsize(os.path.join(tmp, kind + ".step")) > 1000)
                found = dict(re.findall(r"volume\s+(tfm_\w+)\s+\d+ solids\s+([\d.]+)", result.stdout))
                volumes[kind] = {k: float(v) for k, v in found.items()}
            # The analysis mesher refuses the types it cannot analyse, with a reason.
            refused = subprocess.run([sys.executable, "-m", "emachine", "mesh", "--params",
                                      os.path.join(tmp, "z.json"), "--no-mesh"], capture_output=True, text=True, cwd=tmp)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("--stator-only", refused.stderr + refused.stdout)
        # Closed forms: the U-core ring, and the coils.
        t = 0.6 * math.pi * 34.0 / 18
        height, half_w = 8.0 + 3.0, 4.5
        u_core = 18 * (2 * half_w * height - 5.0 * 8.0) * t
        self.assertAlmostEqual(volumes["u"]["tfm_core"] / u_core, 1.0, delta=0.02)       # pole-face trim removes a sliver
        coil = math.pi * ((34.0 - 8.0 + 0.5 + 6.0) ** 2 - (34.0 - 8.0 + 0.5) ** 2) * 4.0
        self.assertAlmostEqual(volumes["u"]["tfm_coil"] / coil, 1.0, delta=0.005)
        self.assertAlmostEqual(volumes["e"]["tfm_coil"] / (2 * coil), 1.0, delta=0.005)  # two coils
        self.assertGreater(volumes["ui"]["tfm_core"], volumes["u"]["tfm_core"])
        self.assertAlmostEqual(volumes["c"]["tfm_core"] / volumes["u"]["tfm_core"], 1.0, delta=0.15)
        self.assertGreater(volumes["z"]["tfm_core"], volumes["u"]["tfm_core"])
        self.assertGreater(volumes["cp"]["tfm_core"], volumes["ui"]["tfm_core"])
