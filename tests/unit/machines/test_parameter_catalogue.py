"""T48: the design variables of every machine follow the catalogue of docs/parameters.md."""

import os
import re
import unittest

from helpers import ROOT

from emachine.core import registry
from emachine.machines.tfm.options import ROTORS as TFM_ROTORS, STATOR_CODES, SUPPORTED_STATORS
from emachine.pipeline import design_space
from emachine.spec import load_spec

CATALOGUE = os.path.join(ROOT, "docs", "parameters.md")
UNITS = ("_mm", "_deg", "_A_mm2")
COUNTS = ("pole_pairs",)


def catalogued():
    with open(CATALOGUE) as f:
        text = f.read()
    return set(re.findall(r"`([A-Za-z_0-9]+)`", text))


def machines():
    """(label, spec) of every machine of the matrix that has variables: all rotor layouts, the TFM
    with every stator and rotor."""
    out = []
    for key in sorted(registry.names("machine")):
        machine_class = registry.get("machine", key)
        flux_path, principle = key.split("/")
        if flux_path == "tfm":
            for stator in [name for name, code in STATOR_CODES.items() if code in SUPPORTED_STATORS]:
                for rotor in (TFM_ROTORS if principle == "pmsm" else (None,)):
                    m = {"flux_path": flux_path, "principle": principle, "stator": stator, "phases": 3,
                         "rotor_placement": "outer", "outer_diameter_mm": 80.0, "stack_length_mm": 30.0,
                         "bore_diameter_mm": 20.0}
                    if rotor:
                        m["rotor"] = rotor
                    out.append((f"{key}/{stator}/{rotor}", m))
        else:
            for rotor in machine_class.rotors:
                out.append((f"{key}/{rotor}", {"flux_path": flux_path, "principle": principle, "rotor": rotor}))
    return [(label, load_spec({"machine": m})) for label, m in out]


class CatalogueTest(unittest.TestCase):
    def test_t48_1_every_variable_is_catalogued(self):
        known = catalogued()
        for label, spec in machines():
            with self.subTest(machine=label):
                missing = [v["name"] for v in design_space.variables(spec) if v["name"] not in known]
                self.assertEqual(missing, [])

    def test_t48_2_no_ratios_and_a_unit_in_every_name(self):
        for label, spec in machines():
            for v in design_space.variables(spec):
                with self.subTest(machine=label, variable=v["name"]):
                    self.assertNotIn("ratio", v["name"])
                    self.assertNotIn("span", v["name"])
                    self.assertTrue(v["name"].endswith(UNITS) or v["name"] in COUNTS, v["name"])


if __name__ == "__main__":
    unittest.main()
