"""T47: the Onshape feature "eMachine" against the Python names and dimensions."""

import json
import os
import re
import subprocess
import sys
import unittest

from emachine.cad import sheet
from emachine.core import registry
from emachine.machines import matrix
from emachine.machines.tfm import options as tfm_options
from emachine.pipeline import design_space
from emachine.spec import load_spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FS = os.path.join(ROOT, "emachine", "cad", "featurescript")
TFM_FS = os.path.join(ROOT, "emachine", "machines", "tfm", "cad", "featurescript")


def read(path):
    with open(path) as f:
        return f.read()


def enums(source):
    """{enum name: {member: annotation name}} of a Feature Studio."""
    out = {}
    for name, body in re.findall(r"export enum (\w+)\s*\{(.*?)\n\}", source, flags=re.S):
        out[name] = dict((m, n) for n, m in re.findall(r'annotation \{ "Name" : "([^"]+)" \}\s*(\w+)', body))
    return out


def field_names(source):
    """Names of the dialog fields (annotations of the precondition)."""
    pre = source[source.index("precondition"):source.index("emCheckMatrix(definition);")]
    return set(re.findall(r'annotation \{ "Name" : "([^"]+)"', pre))


def defaults_keys(source, name):
    block = re.search(r"const %s = \{(.*?)\};" % name, source, flags=re.S).group(1)
    return set(re.findall(r'"(\w+)" :', block))


def all_rotors():
    names = set()
    for key in registry.names("machine"):
        names |= set(registry.get("machine", key).rotors)
    return names


class EnumTest(unittest.TestCase):
    def setUp(self):
        self.main = read(os.path.join(FS, "emachine_main.fs"))
        self.enums = enums(self.main)

    def test_t47_1_enums_follow_the_naming_standard(self):
        self.assertEqual(list(self.enums["EmFluxPath"]), [f.upper() for f in matrix.FLUX_PATHS])
        self.assertEqual(list(self.enums["EmPrinciple"]), [p.upper() for p in matrix.PRINCIPLES])
        self.assertEqual(set(self.enums["EmStator"]), {s.upper() for s in tfm_options.STATOR_CODES})
        rotors = {r.upper() for r in sheet.ROTORS}
        self.assertEqual(set(self.enums["EmRotor"]), rotors)
        self.assertTrue({r.upper() for r in all_rotors()} <= rotors, all_rotors())
        with open(os.path.join(ROOT, "docs", "naming.md")) as f:
            naming = f.read()
        for rotor in sheet.ROTORS:
            self.assertIn(f"`{rotor}`", naming)

    def test_t47_1_sheet_texts_are_the_dialog_entries(self):
        for table, enum in ((sheet.FLUX_PATHS, "EmFluxPath"), (sheet.PRINCIPLES, "EmPrinciple"), (sheet.ROTORS, "EmRotor"),
                            (sheet.STATORS, "EmStator"), (sheet.PLACEMENTS, "EmRotorPlacement"),
                            (sheet.SPANS, "EmWindingSpan")):
            with self.subTest(enum=enum):
                self.assertEqual({k.upper(): v for k, v in table.items()}, self.enums[enum])

    def test_t47_1_sheet_fields_exist_in_the_dialog(self):
        fields = field_names(self.main)
        cases = [(os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"), os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")),
                 (os.path.join(ROOT, "examples", "user_tr48.json"), os.path.join(ROOT, "examples", "user_tr48_design.json"))]
        specs = [(load_spec(s), json.loads(read(d))) for s, d in cases]
        for key in ("rfm/pmsm", "rfm/synrm", "rfm/srm"):
            for rotor in registry.get("machine", key).rotors:
                fp, pr = key.split("/")
                spec = load_spec({"machine": {"flux_path": fp, "principle": pr, "rotor": rotor, "phases": 3,
                                              "rotor_placement": "inner"}})
                values = {v["name"]: (v["low"] + v["high"]) / 2 for v in design_space.variables(spec)}
                specs.append((spec, design_space.clip(spec, values)))
        for spec, values in specs:
            with self.subTest(machine=f"{spec['machine']['flux_path']}/{spec['machine']['principle']}/{spec['machine']['rotor']}"):
                for field, _ in sheet.emachine_rows(spec, design_space.clip(spec, values)):
                    self.assertIn(field, fields)

    def test_t47_1_tfm_fields_are_fields_of_the_tfm_features(self):
        """mergeMaps ignores nothing: a mistyped key would silently keep the default of the TFM feature."""
        body = self.main[self.main.index("function emTfm("):self.main.index("// ---------------------------------------------------------------- RFM")]
        stator_call = body[body.index("tfmStator("):body.index("});")]
        rotor_map = body[body.index("var rotor = {"):body.index("tfmInrunnerRotor(")]
        stator_keys = set(re.findall(r'"(\w+)" :', stator_call))
        rotor_keys = set(re.findall(r'"(\w+)" :', rotor_map)) | set(re.findall(r"rotor\.(\w+) =", rotor_map))
        ui32 = read(os.path.join(TFM_FS, "tfm_ui32_design.fs"))
        self.assertLessEqual(stator_keys, defaults_keys(ui32, "TFM_STATOR_DEFAULTS"))
        self.assertLessEqual(rotor_keys, defaults_keys(ui32, "TFM_ROTOR_DEFAULTS"))
        # everything the UI32 feature passes, the eMachine feature passes too
        machine = ui32[ui32.index("tfmStator(context, id + \"stator\""):ui32.index("}, { \"includeStator\"")]
        self.assertLessEqual(set(re.findall(r'"(\w+)" :', machine)), stator_keys | rotor_keys)


class BuildTest(unittest.TestCase):
    def test_t47_2_studio_up_to_date(self):
        result = subprocess.run([sys.executable, "-m", "emachine", "featurescript", "--check"], capture_output=True,
                                text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        studio = read(os.path.join(FS, "emachine_design.fs"))
        self.assertEqual(studio.count("defineFeature("), 1)
        self.assertIn("export const eMachine = defineFeature", studio)
        for function in ("function tfmStator(", "function tfmInrunnerRotor(", "function emRfm(", "function emWinding("):
            self.assertIn(function, studio)
        self.assertTrue(studio.startswith("FeatureScript 3095;"))
        # precondition: only == and != comparisons (Onshape cannot build a dialog with < or >)
        pre = studio[studio.index("precondition"):studio.index("emCheckMatrix(definition);")]
        self.assertNotRegex(pre, r"if \([^)]*[<>]")


class SheetTest(unittest.TestCase):
    def test_t47_3_rfm_reference(self):
        """The dialog takes the inputs and the design variables; the feature's defaults are this design."""
        spec = load_spec(os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"))
        with open(os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")) as f:
            values = json.load(f)
        rows = dict(sheet.emachine_rows(spec, values))
        self.assertEqual(rows["Slots"], "12")
        self.assertEqual(rows["Pole pairs"], "5")
        self.assertEqual(rows["Rotor layout"], "Surface magnets (SPM)")
        self.assertEqual(rows["Outer diameter"], "100.0000 mm")
        self.assertEqual(rows["Slot height"], "12.0000 mm")
        self.assertEqual(rows["Slot width (parallel-sided slot)"], "7.0700 mm")
        self.assertEqual(rows["Yoke height"], "8.0000 mm")
        self.assertEqual(rows["Magnet arc (electrical, 180: whole pole)"], "153.0000 deg")
        self.assertEqual(rows["Magnet thickness (spoke: magnet width)"], "3.0000 mm")
        self.assertEqual(dict(sheet.checks(spec, values))["Bore diameter (stator)"], "60.0000 mm")
        main = read(os.path.join(FS, "emachine_main.fs"))
        defaults = main[main.index("const EM_DEFAULTS"):main.index("annotation { \"Feature Type Name\"")]
        m = spec["machine"]
        for key, value in (("outerDiameter", m["outer_diameter_mm"]), ("stackLength", m["stack_length_mm"]),
                           ("airGap", m["air_gap_mm"]), ("boreDiameter", m["bore_diameter_mm"]),
                           ("yokeHeight", values["yoke_height_mm"]), ("slotHeight", values["slot_height_mm"]),
                           ("slotWidth", values["slot_width_mm"]), ("magnetThickness", values["magnet_thickness_mm"])):
            self.assertIn('"%s" : %g * millimeter' % (key, value), defaults)
        self.assertIn('"magnetArc" : %g * degree' % values["magnet_arc_el_deg"], defaults)
        for key, value in (("polePairs", values["pole_pairs"]), ("slots", m["slots"])):
            self.assertIn('"%s" : %g' % (key, value), defaults)

    def test_t52_no_ratio_fields(self):
        """T52: the dialog takes lengths and arcs (docs/parameters.md), no ratios."""
        main = read(os.path.join(FS, "emachine_main.fs"))
        pre = main[main.index("precondition"):main.index("emCheckMatrix(definition);")]
        self.assertNotIn("isReal(", pre)
        self.assertNotRegex(pre, r"(?i)\bratio\b|/ pole pitch")

    def test_t47_3_derivation_follows_the_python_model(self):
        """The formulas of emRfmDimensions and emTfmDimensions are those of SlottedMachine.derive and
        design.derived (checked by number in Onshape, T47 Result); here: the same terms in the source."""
        main = read(os.path.join(FS, "emachine_main.fs"))
        rfm = main[main.index("function emRfmDimensions"):main.index("function emRfm(")]
        for term in ("rOut - d.yokeHeight - d.slotHeight", "2 * PI * rBore / d.slots - d.slotWidth", "rBore - d.airGap"):
            self.assertIn(term, rfm)
        tfm = main[main.index("function emTfmDimensions"):main.index("function emTfm(")]
        for term in ("(d.stackLength - (d.phases - 1) * d.phaseSpacing) / d.phases", "width - 2 * d.legWidth",
                     "rOut - d.rotorIron - magnet", "rotorGapRadius - d.airGap", "statorRadius - d.airGap",
                     "d.slotHeight - d.coilClearance - d.coilMargin - bridge"):
            self.assertIn(term, tfm)

    def test_t47_3_command(self):
        result = subprocess.run([sys.executable, "-m", "emachine", "onshape", "--spec",
                                 os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"), "--design",
                                 os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json"), "--markdown"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("| Flux path | RFM: radial flux |", result.stdout)
        self.assertIn("| Winding span | Concentrated (tooth coils) |", result.stdout)


if __name__ == "__main__":
    unittest.main()


class HybridTest(unittest.TestCase):
    """T54: the "Raxial machine" feature of the hybrid studio."""

    def test_t54_studio_up_to_date(self):
        from emachine.cad import build
        self.assertEqual(read(build.HYBRID_TARGET), build.build_hybrid())
        studio = read(build.HYBRID_TARGET)
        self.assertEqual(studio.count("defineFeature("), 1)
        self.assertIn("function emAnnulus(", studio)           # the shape helpers are copied in
        pre = studio[studio.index("precondition"):studio.index("const g = rxDimensions(definition);")]
        self.assertNotIn("isReal(", pre)

    def test_t54_sheet_fields_and_defaults(self):
        from emachine.cad import build
        spec = load_spec(os.path.join(ROOT, "examples", "rafm_zhang2023.json"))
        with open(os.path.join(ROOT, "examples", "rafm_zhang2023_design.json")) as f:
            values = json.load(f)
        studio = read(build.HYBRID_TARGET)
        dialog = set(re.findall(r'annotation \{ "Name" : "([^"]+)"', studio))
        rows = sheet.raxial_rows(spec, values)
        for field, _ in rows:
            self.assertIn(field, dialog)
        defaults = studio[studio.index("const RX_DEFAULTS"):studio.index("annotation { \"Feature Type Name\"")]
        keys = {"rotor_iron_mm": "rotorIron", "magnet_thickness_mm": "magnetThickness", "magnet_arc_el_deg": "magnetArc",
                "radial_tooth_height_mm": "radialToothHeight", "radial_tooth_length_mm": "radialToothLength",
                "yoke_width_mm": "yokeWidth", "axial_tooth_height_mm": "axialToothHeight", "disc_iron_mm": "discIron",
                "axial_magnet_thickness_mm": "axialMagnetThickness", "axial_magnet_arc_el_deg": "axialMagnetArc",
                "slot_width_mm": "slotWidth", "slot_opening_mm": "slotOpening", "tooth_tip_height_mm": "toothTipHeight",
                "coil_thickness_mm": "coilThickness"}
        for name, key in keys.items():
            unit = "degree" if name.endswith("_deg") else "millimeter"
            self.assertIn('"%s" : %g * %s' % (key, values[name], unit), defaults)
        m = spec["machine"]
        for key, value in (("outerDiameter", m["outer_diameter_mm"]), ("axialLength", m["stack_length_mm"]),
                           ("boreDiameter", m["bore_diameter_mm"]), ("airGap", m["air_gap_mm"])):
            self.assertIn('"%s" : %g * millimeter' % (key, value), defaults)
