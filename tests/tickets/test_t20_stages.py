"""T20: rotor positions in two stages."""

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.pipeline import evaluate
from emachine.spec import load_spec

THREE = os.path.join(ROOT, "examples/tfm_three_phase.json")
SCRIPT = ["-m", "emachine", "optimize"]


def spec_with(change=None):
    with open(THREE) as f:
        user = json.load(f)
    if change:
        change(user)
    return load_spec(user)


def some_design(spec, **changes):
    values = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
    values.update({"tooth_span": 0.6, "pole_pairs": 18, "slot_height_mm": 10.0, "yoke_height_mm": 4.0,
                   "magnet_thickness_mm": 2.0, "rotor_iron_mm": 3.0, "bridge_height_mm": 2.5,
                   "current_density_A_mm2": 3.0})
    values.update(changes)
    return design.clip(spec, values)


class Rough:
    """Stand-in with a sixth-harmonic torque term that both stages see, and one only the second stage sees."""

    def __init__(self, cosine=0.2, sine=0.3, with_shift=True):
        self.cosine, self.sine, self.calls, self.positions = cosine, sine, [], 0
        if not with_shift:
            self.__call__ = None

    def run(self, parameters, positions, rundir, jobs, shift=0.0):
        self.calls.append((positions, shift))
        self.positions += positions
        result = evaluate.analytic_stand_in(parameters, positions, rundir, jobs, shift)
        angle = math.pi * (np.arange(positions) + shift) / positions
        scale = float(np.mean(result["torque_Nm"]))
        result["torque_Nm"] = result["torque_Nm"] + scale * (self.cosine * np.cos(6 * angle) + self.sine * np.sin(6 * angle))
        return result


def rough(cosine=0.2, sine=0.3):
    model = Rough(cosine, sine)

    def rough_analysis(parameters, positions, rundir, jobs, shift=0.0):
        return model.run(parameters, positions, rundir, jobs, shift)
    return model, rough_analysis


class StagingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_t20_1_when_staging_applies(self):
        spec = load_spec(THREE)
        self.assertEqual(evaluate.staging(spec), 6)
        for positions, phases, expected in ((12, 1, 6), (9, 3, None), (6, 3, 3), (8, 3, None), (8, 1, 4), (4, 1, None)):
            spec["fidelity"]["positions"], spec["machine"]["phases"] = positions, phases
            self.assertEqual(evaluate.staging(spec), expected, (positions, phases))
        spec["fidelity"]["positions"], spec["fidelity"]["staged"] = 12, False
        self.assertIsNone(evaluate.staging(spec))

    def test_t20_2_two_halves_are_the_full_sweep(self):
        spec = load_spec(THREE)
        parameters = design.to_parameters(spec, some_design(spec))
        full = evaluate.analytic_stand_in(parameters, 12, None, 1)
        first = evaluate.analytic_stand_in(parameters, 6, None, 1)
        second = evaluate.analytic_stand_in(parameters, 6, None, 1, shift=0.5)
        for name in ("torque_Nm", "flux_per_turn_Wb"):
            np.testing.assert_allclose(evaluate.interleave(first[name], second[name]), full[name], rtol=1e-12, atol=1e-18)

    def test_t20_3_passing_design_equals_unstaged(self):
        records, solved = {}, {}
        for staged in (True, False):
            def change(user, staged=staged):
                user["fidelity"] = {"staged": staged}
                user["limits"]["max_torque_ripple_percent"] = 500.0
            spec = spec_with(change)
            model, analysis = rough()
            records[staged] = evaluate.evaluate(spec, some_design(spec), self.path(str(staged)), analysis)
            solved[staged] = model.positions
            self.assertEqual(records[staged]["violation"], 0.0)
        self.assertEqual(solved, {True: 12, False: 12})
        self.assertEqual(records[True]["analysis"]["stage"], "full")
        self.assertFalse(records[True]["analysis"]["stopped_early"])
        np.testing.assert_allclose(records[True]["torque"]["machine_waveform_Nm"],
                                   records[False]["torque"]["machine_waveform_Nm"], rtol=1e-12)
        for key in ("torque_Nm", "loss_W", "ripple"):
            self.assertAlmostEqual(records[True]["objectives"][key], records[False]["objectives"][key], places=12)
        self.assertEqual(records[True]["winding"]["turns"], records[False]["winding"]["turns"])

    def test_t20_4_failing_design_stops_after_half(self):
        def staged(user):
            user["limits"]["max_torque_ripple_percent"] = 20.0

        def unstaged(user):
            staged(user)
            user["fidelity"] = {"staged": False}
        spec = spec_with(staged)
        model, analysis = rough()
        record = evaluate.evaluate(spec, some_design(spec), self.path("staged"), analysis)
        self.assertEqual(model.calls, [(6, 0.0)])
        self.assertEqual(record["analysis"]["positions_solved"], 6)
        self.assertTrue(record["analysis"]["stopped_early"])
        self.assertEqual(record["analysis"]["stage"], "first")
        self.assertGreater(record["violation"], spec["fidelity"]["early_stop_margin"])
        model, analysis = rough()
        full = evaluate.evaluate(spec_with(unstaged), some_design(spec), self.path("unstaged"), analysis)
        self.assertEqual(model.positions, 12)
        self.assertFalse(full["analysis"]["stopped_early"])
        # The first stage sees the cosine term only (40 % ripple); the full sweep also sees the larger sine term (60 %).
        self.assertAlmostEqual(100 * record["objectives"]["ripple"], 40.0, delta=0.5)
        self.assertLess(record["objectives"]["ripple"], full["objectives"]["ripple"])
        self.assertAlmostEqual(record["objectives"]["torque_Nm"], full["objectives"]["torque_Nm"], places=9)

    def test_just_inside_the_margin_is_refined(self):
        def change(user):
            user["limits"]["max_torque_ripple_percent"] = 38.0       # first stage shows 40 %: 5 % over, inside the margin
        spec = spec_with(change)
        model, analysis = rough()
        record = evaluate.evaluate(spec, some_design(spec), self.path("a"), analysis)
        self.assertEqual(model.positions, 12)
        self.assertFalse(record["analysis"]["stopped_early"])
        self.assertGreater(record["violation"], 0.0)

    def test_t20_5_function_without_shift(self):
        model = Rough()

        def plain(parameters, positions, rundir, jobs):
            return model.run(parameters, positions, rundir, jobs)

        def change(user):
            user["limits"]["max_torque_ripple_percent"] = 500.0
        spec = spec_with(change)
        record = evaluate.evaluate(spec, some_design(spec), self.path("plain"), plain)
        self.assertEqual(model.calls, [(6, 0.0), (12, 0.0)])
        self.assertEqual(record["analysis"]["positions"], 12)
        self.assertEqual(record["analysis"]["positions_solved"], 18)

    def test_first_stage_from_the_cache_is_refined_with_a_full_sweep(self):
        def strict(user):
            user["limits"]["max_torque_ripple_percent"] = 20.0

        def loose(user):
            user["limits"]["max_torque_ripple_percent"] = 500.0
        model, analysis = rough()
        workdir = self.path("shared")
        spec = spec_with(strict)
        evaluate.evaluate(spec, some_design(spec), workdir, analysis)
        self.assertEqual(model.positions, 6)
        record = evaluate.evaluate(spec_with(loose), some_design(spec), workdir, analysis)
        self.assertEqual(model.positions, 18)               # the raw first stage is gone, so all 12 are solved
        self.assertFalse(record["analysis"]["stopped_early"])
        again = evaluate.evaluate(spec_with(strict), some_design(spec), workdir, analysis)
        self.assertEqual(model.positions, 18)
        self.assertTrue(again["cache_hit"])


class CommandTest(unittest.TestCase):
    def test_t20_6_optimization_with_and_without_stages(self):
        with open(THREE) as f:
            user = json.load(f)
        user["limits"]["max_winding_temp_C"] = 45.0             # many designs fail, and the first stage shows it
        fronts, solved, stopped = {}, {}, {}
        with tempfile.TemporaryDirectory() as tmp:
            for staged in (True, False):
                user["fidelity"] = {"staged": staged}
                spec_file = os.path.join(tmp, f"spec_{staged}.json")
                with open(spec_file, "w") as f:
                    json.dump(user, f)
                rundir = os.path.join(tmp, f"run_{staged}")
                result = subprocess.run([sys.executable, *SCRIPT, "--spec", spec_file, "--run", rundir, "--dry-run",
                                         "--population", "12", "--generations", "4"],
                                        capture_output=True, text=True, cwd=ROOT)
                self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
                with open(os.path.join(rundir, "pareto.csv")) as f:
                    rows = list(csv.DictReader(f))
                fronts[staged] = sorted((r["torque_Nm"], r["loss_W"], r["ripple"]) for r in rows)
                self.assertTrue(all(r["stopped_early"] == "False" and r["positions"] == "12" for r in rows))
                with open(os.path.join(rundir, "all_designs.csv")) as f:
                    everything = list(csv.DictReader(f))
                stopped[staged] = [r for r in everything if r["stopped_early"] == "True"]
                self.assertTrue(all(r["feasible"] == "False" for r in stopped[staged]))
                solved[staged] = int(next(line for line in result.stdout.splitlines()
                                          if "rotor positions solved" in line).split()[0])
                with open(os.path.join(rundir, "report.md")) as f:
                    report = f.read()
                self.assertIn("in two stages" if staged else "solved in one stage", report)
        self.assertEqual(fronts[True], fronts[False])
        self.assertGreater(len(stopped[True]), 0)
        self.assertEqual(len(stopped[False]), 0)
        self.assertEqual(solved[False] - solved[True], 6 * len(stopped[True]))


@slow
class FieldStagesTest(unittest.TestCase):
    def test_t20_7_and_8_field_solver(self):
        def loose(user):
            user["limits"]["max_torque_ripple_percent"] = 500.0

        def loose_unstaged(user):
            loose(user)
            user["fidelity"] = {"staged": False}

        def strict(user):
            user["limits"]["max_torque_ripple_percent"] = 2.0
        spec = spec_with(loose)
        values = some_design(spec)
        with tempfile.TemporaryDirectory() as tmp:
            staged = evaluate.evaluate(spec, values, os.path.join(tmp, "staged"))
            direct = evaluate.evaluate(spec_with(loose_unstaged), values, os.path.join(tmp, "direct"))
            self.assertTrue(staged["analysed"] and direct["analysed"], staged.get("reason"))
            self.assertEqual(staged["analysis"]["positions_solved"], 12)
            a = np.array(staged["torque"]["phase_waveform_Nm"])
            b = np.array(direct["torque"]["phase_waveform_Nm"])
            np.testing.assert_allclose(a, b, atol=0.005 * np.abs(b).max())
            self.assertAlmostEqual(staged["objectives"]["loss_W"] / direct["objectives"]["loss_W"], 1.0, delta=0.005)

            # First-stage ripple from the same solution: a lower bound on the full ripple.
            from emachine.physics import torque
            first = torque.metrics(torque.machine_torque(b[0::2], 3))
            full = torque.metrics(torque.machine_torque(b, 3))
            self.assertLessEqual(first["peak_to_peak"], full["peak_to_peak"] + 1e-12)
            self.assertAlmostEqual(first["mean"] / full["mean"], 1.0, delta=0.03)

            stopped = evaluate.evaluate(spec_with(strict), values, os.path.join(tmp, "strict"))
            print(f"\nT20: full ripple {100 * full['ripple']:.1f} %, first-stage ripple {100 * first['ripple']:.1f} %, "
                  f"mean torque first / full = {first['mean'] / full['mean']:.4f}; "
                  f"times: full {direct['seconds']:.0f} s, stopped after first stage {stopped['seconds']:.0f} s")
            if 100 * first["ripple"] > 2.0 * 1.1:
                self.assertTrue(stopped["analysis"]["stopped_early"])
                self.assertEqual(stopped["analysis"]["positions_solved"], 6)
                self.assertGreater(stopped["violation"], 0.1)
                self.assertLess(stopped["seconds"], 0.75 * direct["seconds"])
            else:
                self.assertFalse(stopped["analysis"]["stopped_early"])


if __name__ == "__main__":
    unittest.main()
