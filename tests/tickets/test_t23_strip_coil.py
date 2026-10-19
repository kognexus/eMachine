"""T23: coil of stacked flat copper rings (strip winding)."""

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, coil_winding, copper_loss, phase_resistance, turns_of

from emachine.machines.tfm import design
from emachine.physics import winding as electrical
from emachine.machines.tfm.cad import sheet as onshape
from emachine.spec import SpecError, copper_fill, load_spec

THREE = os.path.join(ROOT, "examples/tfm_three_phase.json")
SCRIPT = ["-m", "emachine", "optimize"]


def three_phase(**winding):
    with open(THREE) as f:
        user = json.load(f)
    user["winding"] = dict({"conductor": "round_wire"}, **winding)     # the file itself uses a strip coil
    return load_spec(user)


def some_design(spec):
    values = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
    values.update({"tooth_span": 0.6, "pole_pairs": 25, "slot_height_mm": 9.2, "yoke_height_mm": 3.0,
                   "magnet_thickness_mm": 4.0, "rotor_iron_mm": 3.0, "bridge_height_mm": 2.0,
                   "current_density_A_mm2": 8.0})
    return design.clip(spec, values)


def coil(spec, d):
    """The Winding of a design's derived dimensions `d` (as TFMPMSM.winding), for dimensions changed by hand."""
    return coil_winding(spec, d["coil_area_mm2"], d["turn_length_mm"], coil_height_mm=d["coil_height"],
                        coil_width_mm=d["coil_width"])


def choose_turns(spec, d, flux, temp_C):
    return turns_of(spec, coil(spec, d), flux, d["electrical_frequency_Hz"], d["ampere_turns_peak"], temp_C)


def old_choose_turns(spec, d, flux, temp_C):
    """choose_turns as it was before T23, for the round-wire comparison."""
    lim = spec["limits"]
    ni_peak = d["ampere_turns_peak"]
    r1 = electrical.winding_resistance(spec["materials"]["copper"], coil(spec, d), temp_C)
    v1 = float(np.max(np.abs(electrical.volts_per_turn(r1, d["electrical_frequency_Hz"], flux, ni_peak))))
    phase_factor = 1.0 if spec["machine"]["phases"] == 1 else math.sqrt(3)
    bus_max = lim["bus_voltage_V"][1]
    turns_min = max(1, int(math.ceil(ni_peak / lim["max_current_A"] - 1e-9)))
    turns_max = int(math.floor(electrical.usable_phase_voltage(spec["machine"]["phases"], bus_max) / v1 + 1e-9))
    feasible = turns_max >= turns_min
    turns = turns_max if feasible else turns_min
    area = d["coil_area_mm2"] * spec["winding"]["fill_factor"] / turns
    return {"turns": turns, "feasible": feasible,
            "violation": max(0.0, turns_min * v1 * phase_factor / bus_max - 1.0),
            "peak_current_A": ni_peak / turns, "required_bus_voltage_V": turns * v1 * phase_factor,
            "resistance_ohm": phase_resistance(spec, coil(spec, d), turns, temp_C), "wire_area_mm2": area}


FLUX = 2e-5 * np.cos(math.pi * np.arange(12) / 12)


class StripCoilTest(unittest.TestCase):
    def test_t23_1_round_wire_unchanged(self):
        spec = three_phase()
        self.assertEqual(spec["winding"]["conductor"], "round_wire")
        d = design.derived(spec, some_design(spec))
        new = choose_turns(spec, d, FLUX, 80.0)
        old = old_choose_turns(spec, d, FLUX, 80.0)
        for key, value in old.items():
            self.assertEqual(new[key], value, key)
        self.assertNotIn("strip_thickness_mm", new)

    def test_t23_2_copper_loss_ratio(self):
        wire, strip = three_phase(), three_phase(conductor="strip")
        d = design.derived(wire, some_design(wire))
        ni = 60.0
        ratio = copper_loss(strip, coil(strip, d), ni, 80.0) / copper_loss(wire, coil(wire, d), ni, 80.0)
        self.assertAlmostEqual(ratio, 0.45 / 0.85, places=9)
        # At the same current density the strip coil carries more ampere-turns.
        values = some_design(wire)
        self.assertAlmostEqual(design.derived(strip, values)["ampere_turns_rms"]
                               / design.derived(wire, values)["ampere_turns_rms"], 0.85 / 0.45, places=9)

    def test_t23_3_layer_cap(self):
        spec = three_phase(conductor="strip")
        d = design.derived(spec, some_design(spec))
        d = dict(d, coil_height=5.64, coil_area_mm2=5.64 * d["coil_width"], ampere_turns_peak=118.0)
        w = choose_turns(spec, d, FLUX, 80.0)
        cap = math.floor(5.64 * 0.85 / 0.3)
        self.assertEqual(cap, 15)
        self.assertEqual(w["layer_cap"], 15)
        self.assertGreater(old_choose_turns(spec, d, FLUX, 80.0)["turns"], 15)   # the voltage alone allows more
        self.assertEqual(w["turns"], 15)
        self.assertGreaterEqual(w["strip_thickness_mm"], 0.3 - 1e-12)
        self.assertTrue(w["feasible"])
        self.assertEqual(w["violation"], 0.0)
        self.assertAlmostEqual(w["peak_current_A"], 118.0 / 15)
        self.assertAlmostEqual(w["wire_area_mm2"], w["strip_width_mm"] * w["strip_thickness_mm"])
        self.assertLess(w["resistance_ohm"], 0.1)

    def test_t23_4_fixed_turns(self):
        spec = three_phase(conductor="strip", turns=4)
        d = dict(design.derived(spec, some_design(spec)), coil_height=5.64, ampere_turns_peak=118.0)
        w = choose_turns(spec, d, FLUX, 80.0)
        self.assertEqual(w["turns"], 4)
        self.assertEqual(w["turns_min"], 8)                     # 118 A-turns at 15 A
        self.assertAlmostEqual(w["violation"], 8 / 4 - 1.0)
        self.assertFalse(w["feasible"])
        ok = choose_turns(three_phase(conductor="strip", turns=10), d, FLUX, 80.0)
        self.assertEqual(ok["turns"], 10)
        self.assertEqual(ok["violation"], 0.0)
        wire = choose_turns(three_phase(turns=12), d, FLUX, 80.0)
        self.assertEqual(wire["turns"], 12)
        self.assertEqual(wire["violation"], 0.0)

    def test_t23_5_sheet(self):
        parameters = {"summary": {"conductor": "strip", "turns": 15, "wire_area_mm2": 1.28, "strip_width_mm": 4.0,
                                  "strip_thickness_mm": 0.32, "peak_current_A": 7.9, "rms_current_A": 5.6,
                                  "resistance_ohm": 0.043, "required_bus_voltage_V": 3.6}}
        rows = {r["field"]: r["text"] for r in onshape.winding_rows(parameters)}
        self.assertEqual(rows["Layers (turns) per phase coil"], "15")
        self.assertEqual(rows["Strip copper, axial width x radial thickness"], "4.00 mm x 0.320 mm")
        self.assertEqual(rows["Phase resistance at operating temperature"], "43.00 milliohm")
        parameters["summary"].update(conductor="round_wire", resistance_ohm=14.2, wire_area_mm2=0.0513)
        rows = {r["field"]: r["text"] for r in onshape.winding_rows(parameters)}
        self.assertIn("Turns per phase coil", rows)
        self.assertEqual(rows["Phase resistance at operating temperature"], "14.2000 ohm")

    def test_t23_6_spec_checks(self):
        with self.assertRaises(SpecError) as e:
            load_spec({"winding": {"conductor": "litz"}})
        self.assertIn("winding.conductor", str(e.exception))
        with self.assertRaises(SpecError) as e:
            load_spec({"winding": {"strip_fill_factor": 1.2}})
        self.assertIn("winding.strip_fill_factor", str(e.exception))
        with self.assertRaises(SpecError) as e:
            load_spec({"winding": {"turns": 2.5}})
        self.assertIn("winding.turns", str(e.exception))
        self.assertEqual(copper_fill(load_spec({"winding": {"conductor": "strip"}})), 0.85)
        self.assertEqual(copper_fill(load_spec()), 0.45)

    def test_t23_7_dry_run(self):
        with open(THREE) as f:
            user = json.load(f)
        self.assertEqual(user["winding"]["conductor"], "strip")
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = os.path.join(tmp, "strip.json")
            with open(spec_file, "w") as f:
                json.dump(user, f)
            rundir = os.path.join(tmp, "run")
            result = subprocess.run([sys.executable, *SCRIPT, "--spec", spec_file, "--run", rundir, "--dry-run",
                                     "--population", "12", "--generations", "3"], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
            with open(os.path.join(rundir, "pareto.csv")) as f:
                rows = list(csv.DictReader(f))
            self.assertGreater(len(rows), 0)
            spec = load_spec(user)
            for row in rows:
                self.assertLessEqual(float(row["peak_current_A"]), spec["limits"]["max_current_A"] + 1e-9)
            with open(os.path.join(rundir, "report.md")) as f:
                report = f.read()
            self.assertIn("stacked flat copper rings (strip)", report)
            self.assertIn("milliohm", report)
            with open(os.path.join(rundir, "designs", "best_compromise.onshape.md")) as f:
                self.assertIn("Layers (turns) per phase coil", f.read())


if __name__ == "__main__":
    unittest.main()
