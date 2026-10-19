"""T12: multi-objective optimizer (NSGA-II)."""

import math
import os
import tempfile
import unittest

import helpers  # noqa: F401

from emachine.optimization import nsga2


def real(name, low, high):
    return {"name": name, "kind": "real", "low": low, "high": high}


def zdt1(designs):
    out = []
    for x in designs:
        g = 1 + 9 * sum(x[1:]) / (len(x) - 1)
        out.append(([x[0], g * (1 - math.sqrt(x[0] / g))], 0.0))
    return out


def constrained(designs):
    """Minimise x and 1 - x... with the constraint x0 + x1 >= 1."""
    return [([x[0], x[1]], max(0.0, 1.0 - x[0] - x[1])) for x in designs]


def mixed(designs):
    return [([abs(x[0] - 7.3) + x[1], (x[0] - 2) ** 2 + (1 - x[1])], 0.0) for x in designs]


def population_signature(state):
    return sorted((nsga2.key_of(p["x"]), tuple(p["f"]), p["violation"]) for p in state["population"])


class Nsga2Test(unittest.TestCase):
    def test_t12_1_zdt1(self):
        variables = [real(f"x{i}", 0.0, 1.0) for i in range(6)]
        state = nsga2.optimize(variables, zdt1, population=40, generations=60, seed=3)
        front = nsga2.pareto_front(state["population"])
        self.assertGreater(len(front), 15)
        error = sum(abs(p["f"][1] - (1 - math.sqrt(p["f"][0]))) for p in front) / len(front)
        self.assertLess(error, 0.05)
        spread = max(p["f"][0] for p in front) - min(p["f"][0] for p in front)
        self.assertGreater(spread, 0.6)          # the front is covered, not one point

    def test_t12_2_non_dominated_sort(self):
        points = [(1, 5), (2, 3), (4, 1), (3, 4), (5, 2), (5, 5)]
        population = [{"x": [i], "f": list(f), "violation": 0.0} for i, f in enumerate(points)]
        fronts = [sorted(front) for front in nsga2.non_dominated_sort(population)]
        self.assertEqual(fronts, [[0, 1, 2], [3, 4], [5]])
        # Infeasible designs drop behind every feasible one, ordered by violation. Point 3 was
        # dominated only by point 1, so it joins the first front once point 1 is infeasible.
        population[1]["violation"] = 0.5
        population[5]["violation"] = 0.1
        fronts = [sorted(front) for front in nsga2.non_dominated_sort(population)]
        self.assertEqual(fronts, [[0, 2, 3], [4], [5], [1]])

    def test_crowding_distance(self):
        population = [{"x": [i], "f": [f, 4 - f], "violation": 0.0} for i, f in enumerate([0.0, 1.0, 2.0, 4.0])]
        d = nsga2.crowding_distance(population, [0, 1, 2, 3])
        self.assertEqual(d[0], math.inf)
        self.assertEqual(d[3], math.inf)
        self.assertAlmostEqual(d[1], 2 * (2.0 - 0.0) / 4.0)
        self.assertAlmostEqual(d[2], 2 * (4.0 - 1.0) / 4.0)

    def test_t12_3_constraints(self):
        variables = [real("a", 0.0, 2.0), real("b", 0.0, 2.0)]
        state = nsga2.optimize(variables, constrained, population=24, generations=60, seed=1)
        self.assertTrue(all(p["violation"] == 0 for p in state["population"]))
        front = nsga2.pareto_front(state["population"])
        self.assertGreater(len(front), 5)
        sums = [p["x"][0] + p["x"][1] for p in front]
        self.assertGreaterEqual(min(sums), 1.0 - 1e-12)      # every design satisfies a + b >= 1
        self.assertLess(sum(sums) / len(sums), 1.05)         # and the front hugs that boundary

    def test_t12_4_integers(self):
        variables = [{"name": "n", "kind": "int", "low": 2, "high": 12}, real("y", 0.0, 1.0)]
        state = nsga2.optimize(variables, mixed, population=16, generations=15, seed=5)
        for individual in state["archive"].values():
            n = individual["x"][0]
            self.assertEqual(n, int(n))
            self.assertIsInstance(n, int)
            self.assertTrue(2 <= n <= 12)
            self.assertTrue(0.0 <= individual["x"][1] <= 1.0)
        self.assertGreater(len({ind["x"][0] for ind in state["archive"].values()}), 4)   # integers are explored

    def test_t12_5_reproducible(self):
        variables = [real(f"x{i}", 0.0, 1.0) for i in range(4)]
        a = nsga2.optimize(variables, zdt1, population=12, generations=8, seed=11)
        b = nsga2.optimize(variables, zdt1, population=12, generations=8, seed=11)
        c = nsga2.optimize(variables, zdt1, population=12, generations=8, seed=12)
        self.assertEqual(population_signature(a), population_signature(b))
        self.assertNotEqual(population_signature(a), population_signature(c))

    def test_t12_6_resume(self):
        variables = [real(f"x{i}", 0.0, 1.0) for i in range(4)] + [{"name": "n", "kind": "int", "low": 0, "high": 5}]

        def problem(designs):
            return [([x[0] + 0.1 * x[4], 1 - x[0] + sum(x[1:4])], 0.0) for x in designs]

        whole = nsga2.optimize(variables, problem, population=12, generations=6, seed=4)
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "state.json")
            first = nsga2.optimize(variables, problem, population=12, generations=3, seed=4, state_file=state_file)
            self.assertEqual(first["generation"], 3)
            calls = []

            def counting(designs):
                calls.append(len(designs))
                return problem(designs)

            resumed = nsga2.optimize(variables, counting, population=12, generations=6, seed=4, state_file=state_file)
        self.assertEqual(resumed["generation"], 6)
        self.assertEqual(population_signature(resumed), population_signature(whole))
        self.assertEqual(resumed["evaluations"], whole["evaluations"])
        self.assertEqual(len(calls), 3)          # only the three remaining generations were evaluated

    def test_t12_7_moves_towards_feasibility(self):
        variables = [real("a", 0.0, 1.0), real("b", 0.0, 1.0)]

        def hard(designs):
            return [([x[1], 1 - x[1]], max(0.0, 0.9 - x[0])) for x in designs]

        initial = [[0.05 + 0.02 * i, 0.1 * i % 1.0] for i in range(12)]   # every start is infeasible
        state = nsga2.optimize(variables, hard, population=12, generations=25, seed=2, initial=initial)
        best = [h["best_violation"] for h in state["history"]]
        self.assertGreater(best[0], 0.5)
        self.assertEqual(best, sorted(best, reverse=True))               # never gets worse
        self.assertEqual(best[-1], 0.0)
        self.assertGreater(state["history"][-1]["feasible"], 0)

    def test_duplicates_are_evaluated_once(self):
        variables = [{"name": "n", "kind": "int", "low": 0, "high": 3}]
        seen = []

        def problem(designs):
            seen.extend(nsga2.key_of(x) for x in designs)
            return [([x[0], 3 - x[0]], 0.0) for x in designs]

        state = nsga2.optimize(variables, problem, population=8, generations=10, seed=1)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertLessEqual(state["evaluations"], 4)                    # only four designs exist


if __name__ == "__main__":
    unittest.main()
