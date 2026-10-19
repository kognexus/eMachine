"""T17: torque, speed and efficiency map."""

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, coupled, machine_of, slow

from emachine.machines.tfm import design
from emachine.analysis import effmap
from emachine.physics import winding as electrical
from emachine.pipeline import evaluate
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec

SPEC = os.path.join(ROOT, "examples/tfm_single_phase.json")
N = 12


def spec_with(change=None):
    with open(SPEC) as f:
        user = json.load(f)
    if change:
        change(user)
    return load_spec(user)


def synthetic_levels(ampere_turns, psi=2.0e-4, k=2.0e-3, a_h=0.0, a_e=0.0):
    """Linear machine: flux = psi * cos(angle) per turn, mean phase torque = k * ampere-turns."""
    angle = electrical.electrical_angles(N)
    return [{"ampere_turns_peak": float(ni), "torque_Nm": [k * ni] * N,
             "flux_per_turn_Wb": list(psi * np.cos(angle)), "a_h": a_h, "a_e": a_e} for ni in ampere_turns]


class ClosedFormTest(unittest.TestCase):
    def setUp(self):
        def fixed_resistance(user):
            user.setdefault("materials", {})["copper"] = {"temp_coefficient_per_K": 0.0}
        self.spec = spec_with(fixed_resistance)
        self.values = design.clip(self.spec, REFERENCE_DESIGN)
        self.d = design.derived(self.spec, self.values)
        self.psi, self.k, self.turns = 2.0e-4, 2.0e-3, 100
        self.r1 = electrical.winding_resistance(self.spec["materials"]["copper"],
                                                machine_of(self.spec).winding(self.spec, self.values), 20.0)
        self.levels = synthetic_levels([0, 200, 400, 600, 800], self.psi, self.k)
        self.machine = effmap.Machine(self.spec, self.values, self.levels, self.turns)

    def test_t17_1_efficiency(self):
        speeds = np.linspace(20, 300, 5)
        loads = np.array([100.0, 250.0, 500.0, 800.0])
        g = self.machine.grid(speeds, loads)
        for i, speed in enumerate(speeds):
            for j, ni in enumerate(loads):
                torque = self.k * ni
                copper = self.r1 * ni ** 2 / 2
                power = torque * 2 * math.pi * speed / 60
                self.assertAlmostEqual(g["torque_Nm"][i, j], torque, places=9)
                self.assertAlmostEqual(g["copper_loss_W"][i, j], copper, places=9)
                self.assertAlmostEqual(g["efficiency"][i, j], power / (power + copper), places=6)
                self.assertAlmostEqual(g["peak_current_A"][i, j], ni / self.turns, places=12)

    def test_t17_2_speeds(self):
        v_max = self.spec["limits"]["bus_voltage_V"][1]
        p = self.d["pole_pairs"]
        no_load = v_max / (self.turns * self.psi) * 60 / (2 * math.pi * p)
        self.assertAlmostEqual(self.machine.no_load_speed() / no_load, 1.0, delta=0.01)
        # Voltage per turn at load: (R1 * NI + w * psi) at the peak of the sine.
        corner = (v_max / self.turns - self.r1 * 800.0) / self.psi * 60 / (2 * math.pi * p)
        speeds = np.linspace(0, 1.1 * no_load, 1101)
        env = self.machine.envelope(speeds)
        full = env["drive_torque_Nm"] >= env["drive_torque_Nm"][0] * (1 - 1e-9)
        self.assertAlmostEqual(speeds[np.nonzero(full)[0][-1]] / corner, 1.0, delta=0.01)
        self.assertAlmostEqual(env["drive_torque_Nm"][0], self.k * 800.0, places=9)
        self.assertEqual(env["drive_torque_Nm"][-1], 0.0)               # above the no-load speed
        self.assertTrue(np.all(np.diff(env["drive_torque_Nm"]) <= 1e-12))

    def test_t17_3_iron_loss(self):
        machine = effmap.Machine(self.spec, self.values, synthetic_levels([0, 400, 800], a_h=0.02, a_e=3e-5), self.turns)
        for speed in (60.0, 240.0):
            f = self.d["pole_pairs"] * speed / 60
            self.assertAlmostEqual(machine.point(speed, 300.0)["iron_loss_W"], 0.02 * f + 3e-5 * f * f, places=9)

    def test_thermal_response_equals_iteration(self):
        spec = load_spec(SPEC)                      # resistance rises with temperature here
        values = design.clip(spec, REFERENCE_DESIGN)
        d = design.derived(spec, values)
        machine = effmap.Machine(spec, values, synthetic_levels([0, d["ampere_turns_peak"], 2 * d["ampere_turns_peak"]],
                                                                a_h=0.03, a_e=2e-5), 100)
        speed = spec["operating_point"]["speed_rpm"]
        f = d["electrical_frequency_Hz"]
        heat = coupled(spec, values, 0.03 * f + 2e-5 * f * f, tolerance_K=1e-7)
        point = machine.point(speed, d["ampere_turns_peak"])
        self.assertAlmostEqual(point["winding_C"], heat["winding_C"], places=4)
        self.assertAlmostEqual(point["magnet_C"], heat["magnet_C"], places=4)
        self.assertAlmostEqual(point["copper_loss_W"], heat["copper_loss_W"], places=5)


class InterpolationTest(unittest.TestCase):
    def test_t17_4_inversion(self):
        ni = np.array([0.0, 100.0, 200.0, 300.0, 400.0])
        torque = 1.2 * ni / (ni + 300.0)                    # saturating
        spec = load_spec(SPEC)
        values = design.clip(spec, REFERENCE_DESIGN)
        angle = electrical.electrical_angles(N)
        levels = [{"ampere_turns_peak": float(a), "torque_Nm": [float(t)] * N,
                   "flux_per_turn_Wb": list(1e-4 * np.cos(angle)), "a_h": 0.0, "a_e": 0.0} for a, t in zip(ni, torque)]
        machine = effmap.Machine(spec, values, levels, 100)
        np.testing.assert_allclose(machine.torque(ni), torque, atol=1e-12)
        np.testing.assert_allclose(machine.ampere_turns_for(torque), ni, atol=0.3)
        dense = machine.torque(np.linspace(0, 400, 2001))
        self.assertTrue(np.all(np.diff(dense) >= -1e-12))
        # Between the levels the curve stays close to the function it samples.
        self.assertLess(abs(machine.torque([150.0])[0] - 1.2 * 150 / 450), 0.004)

    def test_pchip_keeps_trailing_axes(self):
        x = np.array([0.0, 1.0, 2.0])
        y = np.stack([np.arange(4) * v for v in (0.0, 1.0, 2.0)])
        out = effmap.pchip(x, y, [0.5, 1.5, 5.0])
        self.assertEqual(out.shape, (3, 4))
        np.testing.assert_allclose(out[0], np.arange(4) * 0.5)
        np.testing.assert_allclose(out[2], y[2])           # clamped to the last level

    def test_choose_levels(self):
        levels = effmap.choose_levels(260.0, 1000.0, 6)
        self.assertIn(260.0, levels)
        self.assertEqual((levels[0], levels[-1]), (0.0, 1000.0))
        self.assertEqual(levels, sorted(levels))


class DryRunMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.spec = load_spec(SPEC)
        cls.values = design.clip(cls.spec, REFERENCE_DESIGN)
        cls.record = evaluate.evaluate(cls.spec, cls.values, os.path.join(cls.tmp.name, "eval"),
                                       evaluate.analytic_stand_in, use_cache=False)
        cls.design_file = os.path.join(cls.tmp.name, "design.json")
        parameters = design.to_parameters(cls.spec, cls.values)
        parameters["summary"] = {"turns": cls.record["winding"]["turns"]}
        with open(cls.design_file, "w") as f:
            json.dump(parameters, f)
        cls.out = os.path.join(cls.tmp.name, "map")
        cls.result = cls.run_map()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def run_map(cls, *extra):
        return subprocess.run([sys.executable, "-m", "emachine", "map", "--spec", SPEC, "--design",
                               cls.design_file, "--out", cls.out, "--dry-run", *extra],
                              capture_output=True, text=True, cwd=ROOT)

    def rows(self, name):
        with open(os.path.join(self.out, name)) as f:
            return list(csv.DictReader(f))

    def test_t17_5_outputs_and_shape(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout[-1500:] + self.result.stderr[-1500:])
        for name in ("efficiency_map.csv", "envelope.csv", "load_levels.csv", "efficiency_map.svg", "map.md",
                     "load_levels.json", "summary.json", "efficiency_map.vtu", "efficiency_limits.vtu"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, name)), name)
        lim = self.spec["limits"]
        for row in self.rows("efficiency_map.csv"):
            eff = float(row["efficiency"])
            self.assertTrue(0.0 <= eff < 1.0)
            if float(row["speed_rpm"]) == 0 or float(row["torque_Nm"]) == 0:
                self.assertEqual(eff, 0.0)
            if row["within_drive_limits"] == "1":
                self.assertLessEqual(float(row["bus_voltage_needed_V"]), lim["bus_voltage_V"][1] * (1 + 1e-6))
                self.assertLessEqual(float(row["peak_current_A"]), lim["max_current_A"] * (1 + 1e-6))
            if row["continuous"] == "1":
                self.assertEqual(row["within_drive_limits"], "1")
                self.assertLessEqual(float(row["winding_C"]), lim["max_winding_temp_C"] + 1e-6)
                self.assertLessEqual(float(row["current_density_A_mm2"]), lim["max_current_density_A_mm2"] * (1 + 1e-6))
        envelope = self.rows("envelope.csv")
        drive = [float(r["drive_torque_Nm"]) for r in envelope]
        continuous = [float(r["continuous_torque_Nm"]) for r in envelope]
        self.assertTrue(all(b <= a + 1e-9 for a, b in zip(drive, drive[1:])))
        self.assertTrue(all(c <= d + 1e-9 for c, d in zip(continuous, drive)))
        self.assertGreater(drive[0], continuous[0])
        self.assertGreater(continuous[0], 0.0)

    def test_t17_6_rated_point_equals_the_optimizer(self):
        with open(os.path.join(self.out, "summary.json")) as f:
            rated = json.load(f)["rated"]
        record = self.record
        self.assertAlmostEqual(rated["torque_Nm"] / record["objectives"]["torque_Nm"], 1.0, delta=0.01)
        self.assertAlmostEqual(rated["loss_W"] / record["objectives"]["loss_W"], 1.0, delta=0.01)
        self.assertAlmostEqual(rated["efficiency"] / record["efficiency"], 1.0, delta=0.01)
        self.assertAlmostEqual(rated["bus_voltage_needed_V"] / record["winding"]["required_bus_voltage_V"], 1.0, delta=0.01)
        self.assertAlmostEqual(rated["peak_current_A"] / record["winding"]["peak_current_A"], 1.0, delta=1e-6)

    def test_t17_8_field_results_are_reused(self):
        again = self.run_map("--speeds", "21", "--torques", "15")
        self.assertEqual(again.returncode, 0, again.stderr[-1500:])
        self.assertIn("0 load levels solved", again.stdout)
        self.assertEqual(len(self.rows("efficiency_map.csv")), 21 * 15)
        self.__class__.result = self.run_map()          # restore the default grid for the other tests

    def test_turns_option_changes_the_speed_range(self):
        out = os.path.join(self.tmp.name, "map_fewer_turns")
        half = max(2, self.record["winding"]["turns"] // 2)
        result = subprocess.run([sys.executable, "-m", "emachine", "map", "--spec", SPEC, "--design",
                                 self.design_file, "--out", out, "--dry-run", "--turns", str(half)],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        with open(os.path.join(out, "summary.json")) as f:
            fewer = json.load(f)
        with open(os.path.join(self.out, "summary.json")) as f:
            base = json.load(f)
        self.assertGreater(fewer["no_load_speed_rpm"], 1.8 * base["no_load_speed_rpm"])


@slow
class FieldMapTest(unittest.TestCase):
    def test_t17_7_field_solver_map(self):
        def coarse(user):
            user["fidelity"] = {"positions": 6}
        spec = spec_with(coarse)
        values = design.clip(spec, REFERENCE_DESIGN)
        d = design.derived(spec, values)
        with tempfile.TemporaryDirectory() as tmp:
            record = evaluate.evaluate(spec, values, os.path.join(tmp, "eval"), use_cache=False)
            self.assertTrue(record["analysed"], record.get("reason"))
            turns = record["winding"]["turns"]
            rated = d["ampere_turns_peak"]
            levels, solved = effmap.solve_levels(spec, values, [0.0, rated, 2.5 * rated], os.path.join(tmp, "map"), log=None)
            self.assertEqual(solved, 3)
            machine = effmap.Machine(spec, values, levels, turns)
            point = machine.point(spec["operating_point"]["speed_rpm"], rated)
            self.assertAlmostEqual(point["torque_Nm"] / record["objectives"]["torque_Nm"], 1.0, delta=0.02)
            self.assertAlmostEqual(point["loss_W"] / record["objectives"]["loss_W"], 1.0, delta=0.02)
            self.assertAlmostEqual(point["efficiency"] / record["efficiency"], 1.0, delta=0.02)
            per_turn = machine.level_torque[1:] / machine.ni[1:]
            self.assertLess(per_turn[1], per_turn[0])           # saturation: less torque per ampere-turn at high load
            self.assertLess(abs(machine.level_torque[0]), 0.05 * machine.level_torque[1])
            again, solved = effmap.solve_levels(spec, values, [0.0, rated, 2.5 * rated], os.path.join(tmp, "map"), log=None)
            self.assertEqual(solved, 0)


if __name__ == "__main__":
    unittest.main()
