"""T08: mesh fidelity study. Checks the recorded study results and the chosen defaults."""

import csv
import os
import unittest

from helpers import ROOT

from emachine.spec import load_spec

RESULTS = os.path.join(ROOT, "examples", "mesh_fidelity", "fidelity_results.csv")


class FidelityTest(unittest.TestCase):
    def setUp(self):
        with open(RESULTS) as f:
            self.rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]

    def test_t08_1_table(self):
        self.assertGreaterEqual(len(self.rows), 4)             # at least three sizes besides the finest
        for row in self.rows:
            self.assertGreater(row["mean_torque_Nm"], 0)
            self.assertGreater(row["seconds"], 0)

    def test_t08_2_fast_level_is_close_to_finest(self):
        spec = load_spec({})
        fast = spec["fidelity"]["levels"]["fast"]["gap_cell_factor"]
        finest = min(self.rows, key=lambda r: r["gap_cell_factor"])
        row = next(r for r in self.rows if abs(r["gap_cell_factor"] - fast) < 1e-9)
        self.assertAlmostEqual(row["mean_torque_Nm"] / finest["mean_torque_Nm"], 1.0, delta=0.05)
        self.assertAlmostEqual(row["peak_flux_per_turn_uWb"] / finest["peak_flux_per_turn_uWb"], 1.0, delta=0.05)
        self.assertLess(row["seconds"], finest["seconds"])

    def test_t08_3_defaults(self):
        spec = load_spec({})
        self.assertEqual(spec["fidelity"]["level"], "fast")
        self.assertEqual(spec["fidelity"]["levels"]["fast"]["gap_cell_factor"], 1.5)
        self.assertEqual(spec["fidelity"]["levels"]["fine"]["gap_cell_factor"], 0.6)
        self.assertEqual(spec["fidelity"]["positions"] % 3, 0)


if __name__ == "__main__":
    unittest.main()
