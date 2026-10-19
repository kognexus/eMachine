"""T43: the naming standard (docs/naming.md): standard names, old names as aliases, cache keys kept."""

import ast
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

from emachine.spec import SpecError, load_spec
from emachine.spec.names import legacy_spec, standard_machine

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BASELINE = os.path.join(ROOT, "tests", "regression", "baseline", "cache_keys.json")


def spec_files():
    files = sorted(f for f in glob.glob(os.path.join(ROOT, "examples", "*.json")) if not f.endswith("_design.json"))
    return files + sorted(glob.glob(os.path.join(ROOT, "runs", "*", "spec.json")))


class NamesTest(unittest.TestCase):
    def test_t43_1_old_and_new_names_give_the_same_spec(self):
        for path in spec_files():
            with self.subTest(spec=os.path.relpath(path, ROOT)):
                spec = load_spec(path)
                again = load_spec({"machine": legacy_spec(spec)["machine"],
                                   **{k: v for k, v in spec.items() if k != "machine"}})
                self.assertEqual(again, spec)
                self.assertIn(f"{spec['machine']['flux_path']}/{spec['machine']['principle']}", ("tfm/pmsm", "rfm/pmsm", "rafm/pmsm"))

    def test_t43_1_cache_keys_unchanged(self):
        """Keys recorded before T43: every cached result of an older TFM run is still found, with the
        design in the old names or in the names of T50 (tooth_arc_el_deg, ...). Left out:
        - tfm/srm: its old spec carried the TFM rotor_type 'halbach', which meant nothing for it, and
          it cannot be solved, so no cache of it exists;
        - radial and axial machines: since T49 their stator fills the outer diameter and the slot
          area is that of the drawn slot, so the old results belong to another machine."""
        from emachine.analysis import effmap
        from emachine.pipeline import evaluate
        from emachine.spec.names import standard_values
        with open(BASELINE) as f:
            baseline = json.load(f)
        checked = 0
        for name, recorded in sorted(baseline.items()):
            if name == "machine:tfm/srm":
                continue
            source = recorded["user"] if name.startswith("machine:") else os.path.join(ROOT, name)
            if not isinstance(source, dict) and not os.path.isfile(source):
                continue
            spec = load_spec(source)
            if spec["machine"]["flux_path"] != "tfm":
                continue
            with self.subTest(spec=name):
                for values in (recorded["values"], standard_values(spec, recorded["values"])):
                    self.assertEqual(evaluate.cache_key(spec, values), recorded["cache_key"])
                    self.assertEqual(effmap._signature(spec, values), recorded["signature"])
                checked += 1
        self.assertGreaterEqual(checked, 10)   # the specs of the repository; more with local runs/

    def test_t43_2_old_topology_is_a_rotor_layout(self):
        old = load_spec({"machine": {"family": "rfm", "topology": "ipm", "configuration": "inrunner"}})
        new = load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "rotor": "interior",
                                     "rotor_placement": "inner"}})
        self.assertEqual(old, new)
        old = load_spec({"machine": {"family": "rfm", "topology": "pmasynrm"}})
        self.assertEqual((old["machine"]["principle"], old["machine"]["rotor"]), ("synrm", "flux_barrier_pm"))
        with self.assertRaises(SpecError):
            load_spec({"machine": {"family": "rfm", "topology": "ipm", "rotor": "surface"}})

    def test_t43_3_rotor_layout_checked(self):
        with self.assertRaises(SpecError) as raised:
            load_spec({"machine": {"flux_path": "rfm", "principle": "srm", "rotor": "surface"}})
        self.assertIn("salient", str(raised.exception))
        with self.assertRaises(SpecError) as raised:
            load_spec({"machine": {"rotor": "interior"}})
        self.assertIn("halbach, surface, spoke, axial_ring", str(raised.exception))

    def test_t43_4_tfm_option_values(self):
        spec = load_spec({"machine": {"stator_type": "cp", "rotor_type": "flux_concentrating", "configuration": "outrunner"}})
        m = spec["machine"]
        self.assertEqual((m["stator"], m["rotor"], m["rotor_placement"]), ("claw_pole", "spoke", "outer"))
        self.assertNotIn("stator_type", m)
        self.assertEqual(load_spec({"machine": {"stator": "cp"}})["machine"]["stator"], "claw_pole")
        self.assertEqual(standard_machine({"sides": 1})["arrangement"], "single")
        with self.assertRaises(SpecError):
            load_spec({"machine": {"stator_type": "cp", "stator": "u_core"}})

    def test_t43_5_same_optimization_with_old_and_new_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = []
            for name, machine in (("old", {"stator_type": "u", "rotor_type": "surface", "configuration": "outrunner"}),
                                  ("new", {"stator": "u_core", "rotor": "surface", "rotor_placement": "outer"})):
                path = os.path.join(tmp, name + ".json")
                with open(path, "w") as f:
                    json.dump({"machine": machine, "optimizer": {"population": 6, "generations": 1, "seed": 3, "jobs": 1}}, f)
                result = subprocess.run([sys.executable, "-m", "emachine", "optimize", "--spec", path,
                                         "--run", os.path.join(tmp, "run_" + name), "--dry-run"],
                                        capture_output=True, text=True, cwd=ROOT)
                self.assertIn("designs evaluated", result.stdout, result.stderr[-1500:])   # exit 1: none met every limit
                with open(os.path.join(tmp, "run_" + name, "all_designs.csv")) as f:
                    tables.append(f.read())
                with open(os.path.join(tmp, "run_" + name, "spec.json")) as f:
                    saved = json.load(f)["machine"]
                self.assertEqual((saved["stator"], saved["rotor_placement"]), ("u_core", "outer"))
            self.assertEqual(tables[0], tables[1])

    def test_t43_6_old_names_only_in_the_alias_table(self):
        allowed = {os.path.join("emachine", "spec", "names.py")}
        found = []
        for path in glob.glob(os.path.join(ROOT, "emachine", "**", "*.py"), recursive=True):
            relative = os.path.relpath(path, ROOT)
            if relative in allowed:
                continue
            with open(path) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and node.value in ("family", "topology", "stator_type", "rotor_type"):
                    found.append(f"{relative}:{node.lineno} {node.value!r}")
                if isinstance(node, ast.Attribute) and node.attr in ("family", "topology"):
                    found.append(f"{relative}:{node.lineno} .{node.attr}")
        self.assertEqual(found, [])

    def test_t43_7_label(self):
        from emachine.cli import describe
        self.assertEqual(describe.label(load_spec({})), "TFM-PMSM (halbach)")
        rfm = load_spec(os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"))
        self.assertEqual(describe.label(rfm), "RFM-PMSM (surface)")
        self.assertTrue(describe.summary(rfm).startswith("RFM-PMSM (surface), inner rotor"))
        synrm = load_spec({"machine": {"flux_path": "rfm", "principle": "synrm", "rotor": "flux_barrier_pm"}})
        self.assertEqual(describe.label(synrm), "RFM-SynRM (flux_barrier_pm)")


if __name__ == "__main__":
    unittest.main()
