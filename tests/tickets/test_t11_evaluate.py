"""T11: design evaluation."""

import math
import tempfile
import time
import unittest

import numpy as np

from helpers import coupled, machine_of, slow, turns_of

from emachine.machines.tfm import design
from emachine.pipeline import evaluate
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec


def stand_in(calls):
    def analyse(parameters, positions, rundir, jobs):
        calls.append(parameters)
        angle = math.pi * np.arange(positions) / positions
        return {"torque_Nm": 2.0 * np.sin(angle) ** 2, "flux_per_turn_Wb": 1e-4 * np.cos(angle), "core_field_files": []}
    return analyse


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        # One phase: the ripple limit of T19 cannot be met and is switched off for these tests.
        # Staging (T20) is off too, because some of these tests count field solutions.
        self.spec = load_spec({"limits": {"max_torque_ripple_percent": None}, "fidelity": {"staged": False}})
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_t11_1_infeasible_geometry_is_fast(self):
        calls = []
        bad = dict(REFERENCE_DESIGN, tooth_span=0.8, slot_height_mm=17.0, rotor_iron_mm=2.5, bridge_height_mm=5.0)
        began = time.time()
        record = evaluate.evaluate(self.spec, bad, self.tmp.name, stand_in(calls))
        self.assertLess(time.time() - began, 0.01)
        self.assertFalse(record["analysed"])
        self.assertGreater(record["violation"], 0)
        self.assertEqual(calls, [])
        self.assertIn("core_overlap", [c["name"] for c in record["violated_checks"]])
        self.assertTrue(all(v == math.inf for v in record["f"]))

    def test_t11_2_objectives_from_stand_in(self):
        record = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name, stand_in([]))
        values = design.clip(self.spec, REFERENCE_DESIGN)
        d = design.derived(self.spec, values)
        heat = coupled(self.spec, values, 0.0)
        self.assertTrue(record["analysed"])
        self.assertAlmostEqual(record["objectives"]["torque_Nm"], 1.0, places=12)      # mean of 2 sin^2
        self.assertAlmostEqual(record["objectives"]["ripple"], 2.0, places=12)
        self.assertAlmostEqual(record["objectives"]["loss_W"], heat["copper_loss_W"], places=9)
        self.assertEqual(record["f"], [-record["objectives"]["torque_Nm"], record["objectives"]["loss_W"], 2.0])
        winding = turns_of(self.spec, machine_of(self.spec).winding(self.spec, values),
                           1e-4 * np.cos(math.pi * np.arange(12) / 12), d["electrical_frequency_Hz"],
                           d["ampere_turns_peak"], heat["winding_C"])
        self.assertEqual(record["winding"]["turns"], winding["turns"])
        self.assertLessEqual(record["winding"]["peak_current_A"], 15.0 + 1e-9)
        self.assertLessEqual(record["winding"]["required_bus_voltage_V"], 48.0 + 1e-9)
        omega = 2 * math.pi * 300 / 60
        self.assertAlmostEqual(record["output_power_W"], omega * 1.0, places=9)
        for key in ("torque", "winding", "losses", "thermal", "geometry", "constraints", "analysis", "seconds"):
            self.assertIn(key, record)

    def test_three_phase_objectives(self):
        spec = load_spec({"machine": {"phases": 3, "stack_length_mm": 73.0}})
        record = evaluate.evaluate(spec, REFERENCE_DESIGN, self.tmp.name, stand_in([]))
        self.assertAlmostEqual(record["objectives"]["torque_Nm"], 3.0, places=12)      # three phases of mean 1
        self.assertLess(record["objectives"]["ripple"], 1e-9)                         # sin^2 phases add up to a constant
        self.assertAlmostEqual(record["losses"]["total_W"], 3 * record["losses"]["copper_W_per_phase"], places=9)

    def test_t11_3_cache(self):
        calls = []
        first = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name, stand_in(calls))
        second = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name, stand_in(calls))
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(second["f"], first["f"])
        other = evaluate.evaluate(self.spec, dict(REFERENCE_DESIGN, magnet_thickness_mm=2.5), self.tmp.name, stand_in(calls))
        self.assertFalse(other["cache_hit"])
        self.assertEqual(len(calls), 2)
        changed = load_spec({"operating_point": {"speed_rpm": 600.0}, "limits": {"max_torque_ripple_percent": None},
                              "fidelity": {"staged": False}})      # another specification, another cache entry
        self.assertFalse(evaluate.evaluate(changed, REFERENCE_DESIGN, self.tmp.name, stand_in(calls))["cache_hit"])

    def test_t11_4_failure_is_contained(self):
        def broken(parameters, positions, rundir, jobs):
            raise RuntimeError("mesher exploded\nwith details")
        record = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name, broken)
        self.assertTrue(record["failed"])
        self.assertFalse(record["analysed"])
        self.assertGreater(record["violation"], 0)
        self.assertIn("mesher exploded", record["reason"])
        again = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name, stand_in([]))
        self.assertTrue(again["analysed"])                                   # a failure is not cached

    def test_constraints_flag_electrical_infeasibility(self):
        def high_voltage(parameters, positions, rundir, jobs):
            angle = math.pi * np.arange(positions) / positions
            return {"torque_Nm": np.sin(angle) ** 2, "flux_per_turn_Wb": 0.05 * np.cos(angle), "core_field_files": []}
        record = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name, high_voltage)
        self.assertGreater(record["constraints"]["turns"], 0)
        self.assertGreater(record["violation"], 0)

    def test_batch_evaluator_and_analytic_stand_in(self):
        batch = evaluate.BatchEvaluator(self.spec, self.tmp.name, evaluate.analytic_stand_in)
        x = design.to_vector(self.spec, design.clip(self.spec, REFERENCE_DESIGN))
        out = batch([x, x])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], out[1])
        self.assertEqual(len(batch.records), 1)
        record = next(iter(batch.records.values()))
        self.assertGreater(record["objectives"]["torque_Nm"], 0)

    @slow
    def test_t11_5_reference_design_with_field_analysis(self):
        record = evaluate.evaluate(self.spec, REFERENCE_DESIGN, self.tmp.name)
        self.assertTrue(record["analysed"], record.get("reason"))
        self.assertGreater(record["objectives"]["torque_Nm"], 0.5)
        self.assertGreater(record["losses"]["iron_W_per_phase"], 0)
        self.assertLess(record["losses"]["iron_W_per_phase"], 100)            # T09-6
        self.assertGreater(record["losses"]["copper_W_per_phase"], 0)
        self.assertGreater(record["thermal"]["winding_C"], 25.0)
        self.assertGreater(record["thermal"]["winding_C"], record["thermal"]["core_C"])
        self.assertLess(record["losses"]["core_b_p95_T"], 1.8)                # within the linear-model guard
        self.assertLess(record["losses"]["core_b_max_T"], 3.5)                # local peaks exceed real saturation
        self.assertEqual(record["violation"], 0.0)
        self.assertLessEqual(record["winding"]["peak_current_A"], 15.0)
        self.assertLessEqual(record["winding"]["required_bus_voltage_V"], 48.0)
        self.assertEqual(record["analysis"]["positions"], 12)
        print("\nreference design:", {k: round(v, 4) for k, v in record["objectives"].items()},
              "turns", record["winding"]["turns"], "I_pk", round(record["winding"]["peak_current_A"], 2),
              "V_bus", round(record["winding"]["required_bus_voltage_V"], 1),
              "Pcu", round(record["losses"]["copper_W_per_phase"], 2), "Pfe", round(record["losses"]["iron_W_per_phase"], 2),
              "Bmax", round(record["losses"]["core_b_max_T"], 2), "Tw", round(record["thermal"]["winding_C"], 1),
              "Tmag", round(record["thermal"]["magnet_C"], 1), "eff", round(record["efficiency"], 3),
              "violation", record["violation"], "seconds", round(record["seconds"], 1))


if __name__ == "__main__":
    unittest.main()
