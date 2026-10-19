"""T15: seeded optimization."""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT

from emachine.machines.tfm import design
from emachine.optimization import nsga2
from emachine.pipeline import seeding
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec

SCRIPT = ["-m", "emachine", "optimize"]
SPEC = os.path.join(ROOT, "examples/tfm_single_phase.json")


def run(rundir, *extra, spec=SPEC):
    return subprocess.run([sys.executable, *SCRIPT, "--spec", spec, "--run", rundir, "--dry-run",
                           "--population", "12", *extra], capture_output=True, text=True, cwd=ROOT)


def table(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def front_of(rundir):
    """Objective triples of the trade-off designs of a run, with the design values."""
    with open(os.path.join(rundir, "state.json")) as f:
        state = json.load(f)
    return nsga2.pareto_front(state["population"]), state


class SeedReadingTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(SPEC)
        self.values = design.clip(self.spec, REFERENCE_DESIGN)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_t15_1_four_source_forms(self):
        names = list(self.values)
        rundir = self.path("run")
        os.makedirs(rundir)
        for target in (os.path.join(rundir, "pareto.csv"), self.path("designs.csv")):
            with open(target, "w", newline="") as f:
                out = csv.writer(f)
                out.writerow(names + ["torque_Nm"])
                out.writerow([self.values[n] for n in names] + [1.0])
        with open(self.path("pick.json"), "w") as f:
            json.dump(design.to_parameters(self.spec, self.values), f)
        with open(self.path("plain.json"), "w") as f:
            json.dump(self.values, f)
        for source in (rundir, self.path("designs.csv"), self.path("pick.json"), self.path("plain.json")):
            seeds, summary = seeding.collect(self.spec, [source])
            self.assertEqual(len(seeds), 1, source)
            for name in names:
                self.assertAlmostEqual(seeds[0]["values"][name], self.values[name], places=9, msg=source)
            self.assertEqual((summary[0]["clipped"], summary[0]["filled"], summary[0]["infeasible"]), (0, 0, 0))

    def test_t15_2_clipped(self):
        raw = dict(self.values, pole_pairs=40)
        with open(self.path("high.json"), "w") as f:
            json.dump(raw, f)
        low = dict(self.spec)
        seeds, summary = seeding.collect(low, [self.path("high.json")])
        self.assertEqual(summary[0]["clipped"], 1)
        if seeds:           # the clipped design may fail the geometry checks; if it survives it is at the limit
            self.assertEqual(seeds[0]["values"]["pole_pairs"], self.spec["limits"]["pole_pairs"][1])
        values, clipped, filled = seeding.fit(self.spec, raw)
        self.assertEqual(values["pole_pairs"], 32)
        self.assertEqual(clipped, ["pole_pairs"])

    def test_t15_3_filled(self):
        raw = {k: v for k, v in self.values.items() if k != "bridge_height_mm"}
        values, clipped, filled = seeding.fit(self.spec, raw)
        var = next(v for v in design.variables(self.spec) if v["name"] == "bridge_height_mm")
        self.assertEqual(filled, ["bridge_height_mm"])
        self.assertAlmostEqual(values["bridge_height_mm"], (var["low"] + var["high"]) / 2)
        with self.assertRaises(seeding.SeedError):
            seeding.fit(self.spec, {"something_else": 1})

    def test_missing_source(self):
        # A missing source is skipped with a note, so that an unattended run does not abort.
        seeds, summary = seeding.collect(self.spec, [self.path("nothing_here")])
        self.assertEqual(seeds, [])
        self.assertIn("no such file", summary[0]["error"])
        self.assertTrue(seeding.describe(summary)[0].startswith("skipped"))
        with self.assertRaises(seeding.SeedError):
            seeding.read_source(self.path("nothing_here"))


class OversizedStartTest(unittest.TestCase):
    def test_t15_4_more_starts_than_population(self):
        variables = [{"name": "a", "kind": "real", "low": 0.0, "high": 1.0},
                     {"name": "b", "kind": "real", "low": 0.0, "high": 1.0}]
        calls = []

        def evaluate(designs):
            calls.extend(designs)
            return [([x[0], 1 - x[0] + x[1]], 0.0) for x in designs]

        # Ten starts on the true front (b = 0) and ten far from it.
        good = [[i / 9, 0.0] for i in range(10)]
        bad = [[i / 9, 1.0] for i in range(10)]
        state = nsga2.optimize(variables, evaluate, population=10, generations=0, seed=3, initial=bad + good)
        self.assertEqual(len(calls), 20)
        self.assertEqual(len(state["population"]), 10)
        self.assertTrue(all(p["x"][1] == 0.0 for p in state["population"]))


class SeededRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a = os.path.join(cls.tmp.name, "a")
        cls.result_a = run(cls.a, "--generations", "4")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t15_5_seeds_are_kept(self):
        self.assertEqual(self.result_a.returncode, 0, self.result_a.stderr[-1500:])
        b = os.path.join(self.tmp.name, "b0")
        result = run(b, "--generations", "0", "--seed-from", self.a, "--max-seeds", "100")
        self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
        front_a, _ = front_of(self.a)
        front_b, state_b = front_of(b)
        for p in front_a:
            self.assertIn(nsga2.key_of(p["x"]), state_b["archive"])
        # The one place not taken by a seed holds a random design, which may join the trade-off set.
        self.assertLessEqual({tuple(p["f"]) for p in front_a}, {tuple(p["f"]) for p in front_b})

    def test_t15_6_seeded_run_is_not_worse(self):
        b = os.path.join(self.tmp.name, "b3")
        result = run(b, "--generations", "3", "--seed-from", self.a, "--max-seeds", "100")
        self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
        front_a, _ = front_of(self.a)
        front_b, _ = front_of(b)
        for p in front_b:
            for q in front_a:
                if tuple(q["f"]) != tuple(p["f"]):
                    self.assertFalse(nsga2.dominates(q, p), "a seed dominates a final design")
        with open(os.path.join(b, "report.md")) as f:
            report = f.read()
        self.assertIn("Started from known designs", report)
        self.assertIn(self.a, report)
        self.assertTrue(os.path.isfile(os.path.join(b, "seeds.json")))
        self.assertTrue(os.path.isfile(os.path.join(b, "spec.json")))

    def test_t15_7_cache_is_reused(self):
        b = os.path.join(self.tmp.name, "b_cache")
        result = run(b, "--generations", "0", "--seed-from", self.a, "--max-seeds", "100")
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        front_a, _ = front_of(self.a)
        self.assertIn(f"{len(front_a)} with results already in the cache", result.stdout)
        seed_lines = [line for line in result.stdout.splitlines() if line.startswith("  design:")]
        cached = [line for line in seed_lines if "(cached)" in line]
        self.assertGreaterEqual(len(cached), len(front_a))

    def test_t15_8_seed_an_existing_run(self):
        c = os.path.join(self.tmp.name, "c")
        first = run(c, "--generations", "1", "--seed", "5")
        self.assertEqual(first.returncode, 0, first.stderr[-1500:])
        second = run(c, "--generations", "2", "--seed", "5", "--seed-from", self.a, "--max-seeds", "100")
        self.assertEqual(second.returncode, 0, second.stdout[-1500:] + second.stderr[-1500:])
        front_a, _ = front_of(self.a)
        front_c, state_c = front_of(c)
        self.assertEqual(state_c["generation"], 2)
        for p in front_a:
            self.assertIn(nsga2.key_of(p["x"]), state_c["archive"])
        for p in front_c:
            for q in front_a:
                if tuple(q["f"]) != tuple(p["f"]):
                    self.assertFalse(nsga2.dominates(q, p))

    def test_max_seeds(self):
        spec = load_spec(SPEC)
        seeds, summary = seeding.collect(spec, [self.a], max_seeds=3)
        self.assertLessEqual(len(seeds), 3)
        self.assertGreaterEqual(len(seeds), 1)


if __name__ == "__main__":
    unittest.main()
