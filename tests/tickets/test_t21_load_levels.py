"""T21: reuse of field solutions across current density."""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.pipeline import evaluate
from emachine.optimization import nsga2
from emachine.spec import SpecError, load_spec

THREE = os.path.join(ROOT, "examples/tfm_three_phase.json")
SCRIPT = ["-m", "emachine", "optimize"]


def spec_with(levels=3, staged=False, change=None):
    with open(THREE) as f:
        user = json.load(f)
    user["fidelity"] = {"load_levels": levels, "staged": staged}
    if change:
        change(user)
    return load_spec(user)


def some_design(spec, density=3.0):
    values = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
    values.update({"tooth_span": 0.6, "pole_pairs": 18, "slot_height_mm": 10.0, "yoke_height_mm": 4.0,
                   "magnet_thickness_mm": 2.0, "rotor_iron_mm": 3.0, "bridge_height_mm": 2.5,
                   "current_density_A_mm2": density})
    return design.clip(spec, values)


def counting():
    calls = []

    def counted_stand_in(parameters, positions, rundir, jobs, shift=0.0):
        calls.append(parameters["analysis"]["coil_current_A"])
        return evaluate.analytic_stand_in(parameters, positions, rundir, jobs, shift)
    return calls, counted_stand_in


class LoadLevelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_t21_1_levels(self):
        spec = spec_with(3)
        self.assertEqual(evaluate.load_levels(spec, some_design(spec)), [1.0, 5.5, 10.0])
        self.assertEqual(evaluate.load_levels(spec_with(2), some_design(spec)), [1.0, 10.0])
        self.assertIsNone(evaluate.load_levels(spec_with(0), some_design(spec)))

        def fixed(user):
            user["variables"]["current_density_A_mm2"] = 4.0
        self.assertIsNone(evaluate.load_levels(spec_with(3, change=fixed), some_design(spec)))
        with self.assertRaises(SpecError):
            spec_with(1)
        with self.assertRaises(SpecError):
            spec_with(9)

    def test_t21_2_between_levels_equals_direct_for_a_linear_machine(self):
        direct_spec, level_spec = spec_with(0), spec_with(3)
        for density in (1.0, 3.0, 5.5, 8.2, 10.0):
            values = some_design(direct_spec, density)
            direct = evaluate.evaluate(direct_spec, values, os.path.join(self.tmp.name, "direct"), evaluate.analytic_stand_in)
            reused = evaluate.evaluate(level_spec, values, os.path.join(self.tmp.name, "levels"), evaluate.analytic_stand_in)
            for key in ("torque_Nm", "loss_W", "ripple"):
                self.assertAlmostEqual(reused["objectives"][key] / direct["objectives"][key], 1.0, delta=1e-6, msg=key)
            self.assertAlmostEqual(reused["winding"]["required_bus_voltage_V"] / direct["winding"]["required_bus_voltage_V"],
                                   1.0, delta=1e-6)
            self.assertEqual(reused["analysis"]["interpolated"], density not in (1.0, 5.5, 10.0))
            self.assertFalse(direct["analysis"]["interpolated"])

    def test_t21_3_second_current_density_is_free(self):
        spec = spec_with(3)
        calls, analysis = counting()
        first = evaluate.evaluate(spec, some_design(spec, 3.0), self.tmp.name, analysis)
        self.assertEqual(len(calls), 3)
        self.assertEqual(first["analysis"]["positions_solved"], 36)
        second = evaluate.evaluate(spec, some_design(spec, 7.0), self.tmp.name, analysis)
        self.assertEqual(len(calls), 3)
        self.assertEqual(second["analysis"]["positions_solved"], 0)
        self.assertTrue(second["analysis"]["field_solution_reused"])
        self.assertGreater(second["objectives"]["torque_Nm"], first["objectives"]["torque_Nm"])
        # Another geometry is solved again.
        other = dict(some_design(spec, 3.0), magnet_thickness_mm=3.0)
        evaluate.evaluate(spec, other, self.tmp.name, analysis)
        self.assertEqual(len(calls), 6)

    def test_t21_4_further_designs_of_a_geometry(self):
        spec = spec_with(3)
        calls, analysis = counting()
        values = some_design(spec, 3.7)                 # between two points of the grid 1, 2.8, 4.6, ... 10
        records = evaluate.evaluate_geometry(spec, values, self.tmp.name, analysis, siblings=6)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(records), 7)
        self.assertEqual(records[0]["values"], values)
        densities = [r["values"]["current_density_A_mm2"] for r in records[1:]]
        np.testing.assert_allclose(densities, np.linspace(1.0, 10.0, 6))
        for record in records[1:]:
            self.assertTrue(record["analysis"]["sibling"])
            self.assertEqual({k: v for k, v in record["values"].items() if k != "current_density_A_mm2"},
                             {k: v for k, v in values.items() if k != "current_density_A_mm2"})
        torques = [r["objectives"]["torque_Nm"] for r in records[1:]]
        self.assertEqual(torques, sorted(torques))
        # A current density on the grid, or close to a grid point, is not handed back twice.
        self.assertEqual(len(evaluate.evaluate_geometry(spec, some_design(spec, 3.0), self.tmp.name, analysis, siblings=6)), 6)
        on_grid = evaluate.evaluate_geometry(spec, some_design(spec, 10.0), self.tmp.name, analysis, siblings=6)
        self.assertEqual(len(on_grid), 6)
        # With the feature off there are no further designs.
        self.assertEqual(len(evaluate.evaluate_geometry(spec_with(0), values, self.tmp.name, analysis, siblings=6)), 1)

    def test_staged_levels_stop_only_when_every_current_density_fails(self):
        def strict(user):
            user["limits"]["max_winding_temp_C"] = 30.0        # ambient is 25 C: only the lowest currents pass
        spec = spec_with(3, staged=True, change=strict)
        calls, analysis = counting()
        hot = evaluate.evaluate_geometry(spec, some_design(spec, 10.0), os.path.join(self.tmp.name, "a"), analysis, siblings=0)
        self.assertTrue(hot[0]["analysis"]["stopped_early"])
        self.assertEqual(hot[0]["analysis"]["positions_solved"], 18)        # three levels, first stage only
        calls.clear()
        mixed = evaluate.evaluate_geometry(spec, some_design(spec, 10.0), os.path.join(self.tmp.name, "b"), analysis, siblings=6)
        self.assertFalse(mixed[0]["analysis"]["stopped_early"])             # a sibling at low current is within the limits
        self.assertEqual(mixed[0]["analysis"]["positions_solved"], 36)
        self.assertTrue(any(r["violation"] == 0 for r in mixed[1:]))


class OptimizerHookTest(unittest.TestCase):
    VARIABLES = [{"name": "a", "kind": "real", "low": 0.0, "high": 1.0},
                 {"name": "b", "kind": "real", "low": 0.0, "high": 1.0}]

    class Evaluator:
        def __init__(self, give):
            self.give, self.extra, self.asked = give, [], 0

        def __call__(self, designs):
            self.asked += len(designs)
            for x in designs:
                if self.give:                   # the same a with the best possible b, for free
                    self.extra.append(([x[0], 0.0], [x[0], 1 - x[0]], 0.0))
            return [([x[0], 1 - x[0] + x[1]], 0.0) for x in designs]

        def take_extra(self):
            extra, self.extra = self.extra, []
            return extra

    def test_t21_5_free_designs_join_the_population(self):
        with_extra = self.Evaluator(True)
        state = nsga2.optimize(self.VARIABLES, with_extra, population=8, generations=3, seed=4)
        self.assertEqual(len(state["population"]), 8)
        self.assertGreater(state["free_designs"], 0)
        self.assertEqual(len(state["archive"]), with_extra.asked + state["free_designs"])
        self.assertTrue(all(p["x"][1] == 0.0 for p in state["population"]))     # only the free designs are on the front

        plain = self.Evaluator(False)
        reference = nsga2.optimize(self.VARIABLES, plain, population=8, generations=3, seed=4)
        without_hook = nsga2.optimize(self.VARIABLES, lambda designs: [([x[0], 1 - x[0] + x[1]], 0.0) for x in designs],
                                      population=8, generations=3, seed=4)
        self.assertEqual([p["x"] for p in reference["population"]], [p["x"] for p in without_hook["population"]])
        self.assertNotIn("free_designs", reference)


class CommandTest(unittest.TestCase):
    def test_t21_6_dry_run_with_load_levels(self):
        with open(THREE) as f:
            user = json.load(f)
        user["fidelity"] = {"load_levels": 3}
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = os.path.join(tmp, "spec.json")
            with open(spec_file, "w") as f:
                json.dump(user, f)
            rundir = os.path.join(tmp, "run")
            result = subprocess.run([sys.executable, *SCRIPT, "--spec", spec_file, "--run", rundir, "--dry-run",
                                     "--population", "12", "--generations", "3"], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
            with open(os.path.join(rundir, "pareto.csv")) as f:
                rows = list(csv.DictReader(f))
            with open(os.path.join(rundir, "all_designs.csv")) as f:
                everything = list(csv.DictReader(f))
            with open(os.path.join(rundir, "report.md")) as f:
                report = f.read()
            with open(os.path.join(rundir, "state.json")) as f:
                state = json.load(f)
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertLessEqual(float(row["ripple_percent"]), 20.0 + 1e-9)
            self.assertLessEqual(float(row["bus_voltage_needed_V"]), 48.0 + 1e-6)
        self.assertGreater(state["free_designs"], 0)
        self.assertEqual(len(everything), len(state["archive"]))
        self.assertGreater(sum(r["interpolated"] == "True" for r in everything), 0)
        self.assertIn("solved at 3 current densities", report)
        # Resuming re-reads every design, the free ones included, from the cache.
        self.assertIn("rotor positions solved", result.stdout)


@slow
class FieldLevelsTest(unittest.TestCase):
    def test_t21_7_and_8_interpolation_against_direct_solutions(self):
        direct_spec = spec_with(0)
        with tempfile.TemporaryDirectory() as tmp:
            lines = []
            worst = {}
            for levels in (3, 2):
                level_spec = spec_with(levels)
                worst[levels] = [0.0, 0.0]
                for density in (3.25, 7.75):
                    values = some_design(direct_spec, density)
                    direct = evaluate.evaluate(direct_spec, values, tmp)
                    reused = evaluate.evaluate(level_spec, values, tmp)
                    self.assertTrue(direct["analysed"] and reused["analysed"], direct.get("reason") or reused.get("reason"))
                    self.assertTrue(reused["analysis"]["interpolated"])
                    torque = reused["objectives"]["torque_Nm"] / direct["objectives"]["torque_Nm"] - 1.0
                    ripple = 100 * (reused["objectives"]["ripple"] - direct["objectives"]["ripple"])
                    loss = reused["objectives"]["loss_W"] / direct["objectives"]["loss_W"] - 1.0
                    worst[levels] = [max(worst[levels][0], abs(torque)), max(worst[levels][1], abs(ripple))]
                    lines.append(f"  {levels} levels, {density} A/mm2: direct {direct['objectives']['torque_Nm']:.4f} Nm, "
                                 f"ripple {100 * direct['objectives']['ripple']:.1f} %; interpolated torque {100 * torque:+.2f} %, "
                                 f"ripple {ripple:+.2f} points, loss {100 * loss:+.2f} %")
            print("\nT21 interpolation against direct field solutions:\n" + "\n".join(lines))
            self.assertLess(worst[3][0], 0.02)
            self.assertLess(worst[3][1], 3.0)


if __name__ == "__main__":
    unittest.main()
