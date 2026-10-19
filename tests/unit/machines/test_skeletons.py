"""T40: the other machines are known to the system: options, variables, dimensions, checks."""

import unittest

from emachine.core import interfaces, registry
from emachine.core.types import Check, ExcitationPlan, ThermalNetwork, Winding
from emachine.machines.base import NotSolvableYet
from emachine.pipeline import design_space
from emachine.spec import SpecError, load_spec

MACHINES = {"tfm/pmsm", "tfm/srm", "rfm/pmsm", "rfm/synrm", "rfm/srm", "afm/pmsm", "afm/srm"}
#: (machine, rotor layout) of every registered combination; since T43 the former rfm/ipm and
#: rfm/pmasynrm are rotor layouts of rfm/pmsm and rfm/synrm
CASES = [(key, rotor) for key in sorted(MACHINES) for rotor in registry.get("machine", key).rotors]
SOLVABLE = {("tfm/pmsm", rotor) for rotor in ("halbach", "surface", "spoke", "axial_ring")} | {("rfm/pmsm", "surface")}


def spec_of(key, rotor):
    flux_path, principle = key.split("/")
    return load_spec({"machine": {"flux_path": flux_path, "principle": principle, "rotor": rotor,
                                  "phases": 3, "stack_length_mm": 40.0}})


def middle(spec):
    return {v["name"]: (v["low"] + v["high"]) / 2 for v in design_space.variables(spec)}


class SkeletonTest(unittest.TestCase):
    def test_t40_1_registered(self):
        self.assertEqual(set(registry.names("machine")) & MACHINES, MACHINES)
        self.assertIn(("rfm/pmsm", "interior"), CASES)
        self.assertIn(("rfm/synrm", "flux_barrier_pm"), CASES)

    def test_t40_2_each_machine_on_its_default_spec(self):
        for key, rotor in CASES:
            with self.subTest(machine=key, rotor=rotor):
                spec = spec_of(key, rotor)
                machine = registry.create("machine", key)
                self.assertIsInstance(machine, interfaces.Machine)
                values = design_space.clip(spec, middle(spec))
                d = machine.derive(spec, values)
                for name in ("pole_pairs", "electrical_frequency_Hz", "ampere_turns_peak", "ampere_turns_rms"):
                    self.assertIn(name, d)
                self.assertTrue(all(isinstance(c, Check) for c in machine.checks(spec, values)))
                self.assertIsInstance(machine.winding(spec, values), Winding)
                self.assertIsInstance(machine.thermal_network(spec, values), ThermalNetwork)
                self.assertIsInstance(machine.excitation(spec, values), ExcitationPlan)

    def test_t40_3_geometry_of_a_skeleton(self):
        for key, rotor in CASES:
            if (key, rotor) in SOLVABLE:
                continue
            with self.subTest(machine=key, rotor=rotor):
                spec = spec_of(key, rotor)
                machine = registry.create("machine", key)
                solvable, ticket = machine.rotor_status(rotor)
                self.assertFalse(solvable)
                with self.assertRaises(NotSolvableYet) as raised:
                    machine.geometry(spec, design_space.clip(spec, middle(spec)))
                self.assertIn(ticket, str(raised.exception))

    def test_options_validated(self):
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "phases": 3, "slots": 13}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rfm", "principle": "srm", "phases": 3, "winding": "distributed"}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "afm", "principle": "pmsm", "phases": 3, "arrangement": "triple"}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "rotor": "interior", "phases": 3,
                                   "stator": "u_core"}})


if __name__ == "__main__":
    unittest.main()
