"""T19: torque ripple limit, and the field cache that makes changing a limit cheap."""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.pipeline import evaluate
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import SpecError, load_spec

THREE = os.path.join(ROOT, "examples/tfm_three_phase.json")
ONE = os.path.join(ROOT, "examples/tfm_single_phase.json")
SCRIPT = ["-m", "emachine", "optimize"]


def spec_with(path, limit="keep", **machine):
    with open(path) as f:
        user = json.load(f)
    user["machine"].update(machine)
    if limit != "keep":
        user["limits"]["max_torque_ripple_percent"] = limit
    spec = load_spec(user)
    spec["fidelity"]["staged"] = False          # these tests count field solutions; staging is ticket T20
    return spec


def some_design(spec, tooth_span=0.5):
    values = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
    values.update({"tooth_span": tooth_span, "pole_pairs": 18, "slot_height_mm": 10.0, "yoke_height_mm": 4.0,
                   "magnet_thickness_mm": 2.0, "rotor_iron_mm": 3.0, "bridge_height_mm": 2.5,
                   "current_density_A_mm2": 3.0})
    return design.clip(spec, values)


class LimitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def evaluate(self, spec, values, analyse=evaluate.analytic_stand_in):
        record = evaluate.evaluate(spec, values, self.tmp.name, analyse)
        self.assertTrue(record["analysed"], record.get("violated_checks"))
        return record

    def test_t19_1_default(self):
        self.assertEqual(load_spec()["limits"]["max_torque_ripple_percent"], 20.0)
        self.assertEqual(load_spec(THREE)["limits"]["max_torque_ripple_percent"], 20.0)
        self.assertIsNone(load_spec(ONE)["limits"]["max_torque_ripple_percent"])

    def test_t19_2_three_phases(self):
        # The stand-in gives three phases a ripple of 0.18 * (1.2 - tooth span): 12.6 % at 0.5.
        for limit, expected in ((20.0, 0.0), (10.0, 12.6 / 10.0 - 1.0), (None, 0.0)):
            spec = spec_with(THREE, limit)
            record = self.evaluate(spec, some_design(spec))
            self.assertAlmostEqual(100 * record["objectives"]["ripple"], 12.6, places=6)
            self.assertAlmostEqual(record["constraints"]["torque_ripple"], expected, places=6)

    def test_t19_3_one_phase(self):
        spec = spec_with(ONE, 20.0)
        record = self.evaluate(spec, design.clip(spec, REFERENCE_DESIGN))
        self.assertGreater(100 * record["objectives"]["ripple"], 199.9)
        self.assertGreater(record["constraints"]["torque_ripple"], 8.9)
        self.assertLessEqual(record["constraints"]["torque_ripple"], evaluate.RIPPLE_VIOLATION_CAP)
        self.assertGreater(record["violation"], 0.0)

    def test_three_phase_example_dimensions(self):
        # The user's machine: 29 mm = 3 x (2 mm leg + 5 mm slot + 2 mm leg) + 2 x 1 mm between the phases.
        spec = load_spec(THREE)
        self.assertEqual(spec["machine"]["phase_spacing_mm"], 1.0)
        self.assertAlmostEqual(design.phase_width(spec), 9.0)
        leg = next(v for v in design.variables(spec) if v["name"] == "leg_width_mm")
        self.assertEqual((leg["low"], leg["high"]), (2.0, 2.0))
        d = design.derived(spec, some_design(spec))
        self.assertAlmostEqual(d["slot_width"], 5.0)
        self.assertAlmostEqual(d["leg_width"], 2.0)

    def test_t19_4_invalid_limit(self):
        for bad in (-5, 0, "x"):
            with self.assertRaises(SpecError) as error:
                spec_with(THREE, bad)
            self.assertIn("limits.max_torque_ripple_percent", str(error.exception))

    def test_t19_7_changing_a_limit_reuses_the_field_solution(self):
        calls = []

        def counting_stand_in(parameters, positions, rundir, jobs):
            calls.append(1)
            return evaluate.analytic_stand_in(parameters, positions, rundir, jobs)

        spec = spec_with(THREE, 20.0)
        values = some_design(spec)
        first = self.evaluate(spec, values, counting_stand_in)
        stricter = spec_with(THREE, 10.0)
        stricter["limits"]["max_current_A"] = 12.0
        stricter["operating_point"]["speed_rpm"] = 200.0
        second = self.evaluate(stricter, values, counting_stand_in)
        self.assertEqual(len(calls), 1)
        self.assertFalse(first["analysis"]["field_solution_reused"])
        self.assertTrue(second["analysis"]["field_solution_reused"])
        self.assertFalse(second["cache_hit"])
        self.assertEqual(first["objectives"]["torque_Nm"], second["objectives"]["torque_Nm"])
        self.assertEqual(first["constraints"]["torque_ripple"], 0.0)
        self.assertGreater(second["constraints"]["torque_ripple"], 0.0)
        # A change that alters the field is solved again.
        other = dict(values, magnet_thickness_mm=values["magnet_thickness_mm"] + 0.5)
        self.evaluate(spec, other, counting_stand_in)
        self.assertEqual(len(calls), 2)

    def test_t19_8_dry_run_results_stay_apart(self):
        spec = spec_with(THREE, 20.0)
        values = some_design(spec)
        self.evaluate(spec, values)
        calls = []

        def other_analysis(parameters, positions, rundir, jobs):
            calls.append(1)
            return evaluate.analytic_stand_in(parameters, positions, rundir, jobs)

        self.evaluate(spec, values, other_analysis)
        self.assertEqual(len(calls), 1)
        parameters = design.to_parameters(spec, values)
        self.assertNotEqual(evaluate.field_key(spec, parameters, None),
                            evaluate.field_key(spec, parameters, evaluate.analytic_stand_in))
        self.assertNotEqual(evaluate.record_name(spec, values, None),
                            evaluate.record_name(spec, values, evaluate.analytic_stand_in))


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def run_command(self, spec_user, name):
        spec_file = os.path.join(self.tmp.name, name + ".json")
        with open(spec_file, "w") as f:
            json.dump(spec_user, f)
        rundir = os.path.join(self.tmp.name, name)
        result = subprocess.run([sys.executable, *SCRIPT, "--spec", spec_file, "--run", rundir, "--dry-run",
                                 "--population", "12", "--generations", "4"], capture_output=True, text=True, cwd=ROOT)
        return result, rundir

    def test_t19_5_front_respects_the_limit(self):
        with open(THREE) as f:
            user = json.load(f)
        user["limits"]["max_torque_ripple_percent"] = 11.0          # the stand-in gives 4.5 to 12.6 %
        result, rundir = self.run_command(user, "three")
        self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
        with open(os.path.join(rundir, "pareto.csv")) as f:
            rows = list(csv.DictReader(f))
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertLessEqual(float(row["ripple_percent"]), 11.0 + 1e-9)
        with open(os.path.join(rundir, "all_designs.csv")) as f:
            everything = list(csv.DictReader(f))
        above = [r for r in everything if r["ripple_percent"] and float(r["ripple_percent"]) > 11.0]
        self.assertGreater(len(above), 0)                           # the limit did reject designs
        self.assertTrue(all(r["feasible"] == "False" and "torque_ripple" in r["reason"] for r in above))
        with open(os.path.join(rundir, "report.md")) as f:
            report = f.read()
        self.assertIn("| Torque ripple, (highest - lowest) / mean | 11 % |", report)
        self.assertIn("above the torque ripple limit", report)
        self.assertNotIn("One phase:", report)

    def test_t19_6_one_phase_warns(self):
        with open(ONE) as f:
            user = json.load(f)
        user["limits"]["max_torque_ripple_percent"] = 20.0
        result, rundir = self.run_command(user, "one")
        self.assertIn("WARNING: One phase", result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No design met every limit", result.stderr)
        with open(os.path.join(rundir, "report.md")) as f:
            self.assertIn("One phase:", f.read())


@slow
class FieldTest(unittest.TestCase):
    def test_t19_9_three_phase_field_evaluation(self):
        spec = spec_with(THREE, 20.0)
        spec["fidelity"]["positions"] = 6
        values = some_design(spec, tooth_span=0.6)
        with tempfile.TemporaryDirectory() as tmp:
            record = evaluate.evaluate(spec, values, tmp)
            self.assertTrue(record["analysed"], record.get("reason"))
            ripple = 100 * record["objectives"]["ripple"]
            print(f"\nT19-9: three phases in 29 mm, {values['pole_pairs']} pole pairs: torque "
                  f"{record['objectives']['torque_Nm']:.3f} Nm, ripple {ripple:.1f} %, "
                  f"ripple constraint {record['constraints']['torque_ripple']:.3f}")
            self.assertGreater(record["objectives"]["torque_Nm"], 0.0)
            self.assertEqual(record["constraints"]["torque_ripple"] > 0, ripple > 20.0)
            self.assertEqual(len(record["torque"]["machine_waveform_Nm"]), 6)
            again = evaluate.evaluate(spec_with(THREE, 5.0) | {"fidelity": spec["fidelity"]}, values, tmp)
            self.assertTrue(again["analysis"]["field_solution_reused"])


if __name__ == "__main__":
    unittest.main()
