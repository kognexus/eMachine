"""T16: parameter sheet for the Onshape model."""

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

from helpers import FEATURESCRIPT, ROOT, slow

from emachine.machines.tfm import design
from emachine.machines.tfm.cad import sheet as onshape
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec

SPEC = os.path.join(ROOT, "examples/tfm_single_phase.json")


def annotations(name):
    with open(os.path.join(FEATURESCRIPT, name)) as f:
        return set(re.findall(r'annotation\s*\{\s*"Name"\s*:\s*"([^"]+)"', f.read()))


def spec_with(**machine):
    with open(SPEC) as f:
        user = json.load(f)
    from emachine.spec.names import standard_machine
    user["machine"].update(standard_machine(machine))       # old names in the tests, new names in the file (T43)
    return load_spec(user)


def first_feasible(spec):
    """Mid-range design of a specification."""
    return design.clip(spec, {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)})


def rows_of(sections, word):
    return {r["field"]: r for s in sections if word in s["title"] for r in s["rows"]}


class SheetTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(SPEC)
        self.parameters = design.to_parameters(self.spec, REFERENCE_DESIGN)
        self.sections = onshape.sheet(self.parameters)

    def test_t16_1_labels_exist_in_the_features(self):
        stator, rotor = annotations("tfm_stator.fs"), annotations("tfm_rotor.fs")
        for field in rows_of(self.sections, "stator"):
            self.assertIn(field, stator)
        for field, row in rows_of(self.sections, "rotor").items():
            self.assertIn(field, rotor)
        # Choices are spelled as in the dialogs.
        self.assertIn(rows_of(self.sections, "stator")["Core structure"]["text"], stator)
        self.assertIn(rows_of(self.sections, "stator")["Arrangement"]["text"], stator)
        self.assertIn(rows_of(self.sections, "rotor")["Configuration"]["text"], rotor)
        self.assertIn(rows_of(self.sections, "rotor")["Rotor type"]["text"], rotor)

    def test_t16_2_values_equal_the_mesher_parameters(self):
        s, r = self.parameters["stator"], self.parameters["rotor"]
        expected = {
            "stator": {"Air-gap radius": s["air_gap_radius"], "Leg width": s["leg_width"], "Slot width": s["slot_width"],
                       "Slot height": s["slot_height"], "Yoke height": s["yoke_height"],
                       "I-bridge height": s["bridge_height"], "Coil height": s["coil_height"],
                       "Coil clearance": s["coil_clearance"], "Pole pairs": s["pole_pairs"],
                       "Tooth span / pole pitch": s["tooth_span"]},
            "rotor": {"Inner diameter (air gap)": r["inner_diameter"], "Outer diameter": r["outer_diameter"],
                      "Stack length": r["stack_length"], "Number of poles": r["poles"],
                      "Magnet thickness": r["magnet_thickness"], "Gap between rows": r["row_gap"],
                      "Axial magnet rows": r["magnet_rows"], "Segments per pole": r["segments_per_pole"]},
        }
        for word, fields in expected.items():
            rows = rows_of(self.sections, word)
            for field, value in fields.items():
                printed = float(rows[field]["text"].split()[0])
                self.assertAlmostEqual(printed, value, delta=0.00051, msg=field)
        checks = rows_of(self.sections, "Checks")
        self.assertAlmostEqual(checks["Air gap"]["value"], self.spec["machine"]["air_gap_mm"], places=9)
        self.assertAlmostEqual(checks["Total axial length"]["value"], self.spec["machine"]["stack_length_mm"], places=9)
        self.assertAlmostEqual(checks["Overall outer diameter (rotor)"]["value"],
                               self.spec["machine"]["outer_diameter_mm"], places=9)
        self.assertEqual(onshape.flagged(self.sections), [])

    def test_t16_3_inrunner_u_surface(self):
        spec = spec_with(configuration="inrunner", stator_type="u", rotor_type="surface", bore_diameter_mm=12.0)
        sections = onshape.sheet(design.to_parameters(spec, first_feasible(spec)))
        rotor, stator = rows_of(sections, "rotor"), rows_of(sections, "stator")
        for field in ("Outer diameter (air gap)", "Shaft diameter", "Magnet arc / pole pitch"):
            self.assertIn(field, rotor)
        for field in ("Segments per pole", "Inner diameter (air gap)", "Magnet radial height"):
            self.assertNotIn(field, rotor)
        self.assertNotIn("I-bridge height", stator)
        self.assertEqual(stator["Inner stator (outer rotor)"]["text"], "off")
        self.assertEqual(rotor["Shaft diameter"]["value"], 12.0)
        self.assertAlmostEqual(rows_of(sections, "Checks")["Overall outer diameter (stator)"]["value"],
                               spec["machine"]["outer_diameter_mm"], places=9)

    def test_t16_4_flux_concentrating(self):
        spec = spec_with(rotor_type="flux_concentrating")
        rotor = rows_of(onshape.sheet(design.to_parameters(spec, first_feasible(spec))), "rotor")
        self.assertIn("Magnet radial height", rotor)
        self.assertIn("Magnet width", rotor)
        self.assertNotIn("Magnet thickness", rotor)

    def test_t16_5_three_phases(self):
        spec = spec_with(phases=3, stack_length_mm=60.0)
        values = first_feasible(spec)
        parameters = design.to_parameters(spec, values)
        parameters["machine"] = dict(spec["machine"])
        checks = rows_of(onshape.sheet(parameters), "Checks")
        width = design.phase_width(spec)
        self.assertAlmostEqual(checks["Axial distance between neighbouring phases, centre to centre"]["value"],
                               width + spec["machine"]["phase_spacing_mm"], places=9)
        self.assertAlmostEqual(checks["Total axial length"]["value"], 60.0, places=9)
        angle = next(r for f, r in checks.items() if f.startswith("Angle between neighbouring phases"))
        self.assertAlmostEqual(angle["value"], 120.0 / values["pole_pairs"], places=9)

    def test_t16_6_out_of_range_is_flagged(self):
        parameters = copy.deepcopy(self.parameters)
        parameters["stator"]["tooth_span"] = 1.2
        flags = onshape.flagged(onshape.sheet(parameters))
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0][1], "Tooth span / pole pitch")


class CommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rundir = os.path.join(cls.tmp.name, "run")
        cls.result = subprocess.run([sys.executable, "-m", "emachine", "optimize", "--spec", SPEC, "--run",
                                     cls.rundir, "--dry-run", "--population", "12", "--generations", "2"],
                                    capture_output=True, text=True, cwd=ROOT)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t16_7_optimizer_writes_and_prints_the_sheet(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-1500:])
        for pick in ("best_compromise", "highest_torque", "lowest_loss"):
            self.assertTrue(os.path.isfile(os.path.join(self.rundir, "designs", pick + ".onshape.md")), pick)
        with open(os.path.join(self.rundir, "report.md")) as f:
            report = f.read()
        self.assertIn("## Onshape parameters", report)
        self.assertIn("| Air-gap radius |", report)
        self.assertIn("Feature \"TFM stator v2\"", self.result.stdout)
        self.assertIn("Turns per phase coil", self.result.stdout)

    def test_t16_8_command(self):
        pick = os.path.join(self.rundir, "designs", "best_compromise.json")
        result = subprocess.run([sys.executable, "-m", "emachine", "onshape", "--params", pick],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(pick) as f:
            parameters = json.load(f)
        self.assertIn(f"{parameters['stator']['air_gap_radius']:.3f} mm", result.stdout)
        self.assertIn(f"{parameters['rotor']['poles']}", result.stdout)

    @slow
    def test_t16_9_pick_file_still_drives_the_mesher(self):
        pick = os.path.join(self.rundir, "designs", "best_compromise.json")
        check = subprocess.run([sys.executable, "-m", "emachine", "mesh", "--params", pick,
                                "--no-mesh", "--out", os.path.join(self.tmp.name, "sector.msh")],
                               capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(check.returncode, 0, check.stdout[-800:] + check.stderr[-800:])


if __name__ == "__main__":
    unittest.main()
