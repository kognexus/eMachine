"""T37: optimizers behind core.interfaces.Optimizer."""

import json
import math
import os
import unittest

from emachine.core import interfaces, registry
from emachine.core.types import Objective, Problem, Variable
from emachine.spec import SpecError, load_spec

BASELINE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      "regression", "baseline")


def zdt1(designs):
    out = []
    for x in designs:
        g = 1 + 9 * sum(x[1:3]) / 2 + 0.1 * (x[3] - 3) ** 2
        out.append(([x[0], g * (1 - math.sqrt(x[0] / g))], max(0.0, 0.2 - x[0])))
    return out


PROBLEM = Problem(variables=tuple([Variable(f"x{i}", 0.0, 1.0) for i in range(3)] + [Variable("n", 1, 5, "int")]),
                  objectives=(Objective("f1"), Objective("f2")))


class OptimizerTest(unittest.TestCase):
    def test_t37_1_nsga2_through_the_interface_equals_the_recorded_run(self):
        optimizer = registry.create("optimizer", "nsga2")
        self.assertIsInstance(optimizer, interfaces.Optimizer)
        state = optimizer.run(PROBLEM, zdt1, {"population": 12, "generations": 6, "seed": 5})
        with open(os.path.join(BASELINE, "nsga2.json")) as f:
            recorded = json.load(f)["population"]
        found = sorted([p["x"], p["f"], p["violation"]] for p in state["population"])
        self.assertEqual(len(found), len(recorded))
        for a, b in zip(found, recorded):
            for u, v in zip(a[0] + a[1] + [a[2]], b[0] + b[1] + [b[2]]):
                self.assertAlmostEqual(u, v, places=12)

    def test_t37_2_random_search(self):
        def sphere(designs):
            return [([(x[0] - 0.3) ** 2 + (x[1] - 0.6) ** 2], 0.0) for x in designs]
        problem = Problem(variables=(Variable("a", 0.0, 1.0), Variable("b", 0.0, 1.0)), objectives=(Objective("d"),))
        state = registry.create("optimizer", "random").run(problem, sphere, {"population": 20, "generations": 30, "seed": 2})
        best = min(state["population"], key=lambda p: p["f"][0])
        self.assertLess(best["f"][0], 5e-3)
        self.assertEqual(state["evaluations"], 20 * 31)
        self.assertEqual(state["generation"], 30)

    def test_t37_3_algorithm_from_the_spec(self):
        self.assertEqual(load_spec({})["optimizer"]["algorithm"], "nsga2")
        self.assertEqual(load_spec({"optimizer": {"algorithm": "random"}})["optimizer"]["algorithm"], "random")
        with self.assertRaises(SpecError):
            load_spec({"optimizer": {"algorithm": "simulated_annealing"}})
        self.assertEqual(set(registry.names("optimizer")), {"nsga2", "random"})


if __name__ == "__main__":
    unittest.main()


class CommandTest(unittest.TestCase):
    def test_t37_4_optimize_command_with_random_search(self):
        import subprocess
        import sys
        import tempfile
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        with tempfile.TemporaryDirectory() as tmp:
            spec = os.path.join(tmp, "spec.json")
            with open(spec, "w") as f:
                json.dump({"optimizer": {"algorithm": "random", "population": 6, "generations": 1, "jobs": 1}}, f)
            result = subprocess.run([sys.executable, "-m", "emachine", "optimize", "--spec", spec,
                                     "--run", os.path.join(tmp, "run"), "--dry-run"],
                                    capture_output=True, text=True, cwd=root)
            # The command exits non-zero when no design meets every limit; the run itself must complete.
            self.assertIn("12 designs evaluated", result.stdout, result.stdout[-1500:] + result.stderr[-1500:])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "run", "report.md")))
