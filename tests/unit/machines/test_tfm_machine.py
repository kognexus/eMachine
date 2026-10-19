"""T34-1: the TFM as a Machine plugin (tfm/pmsm)."""

import json
import os
import unittest

from emachine.core import interfaces, registry, types
from emachine.spec import load_spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TfmMachineTest(unittest.TestCase):
    def setUp(self):
        self.machine = registry.create("machine", "tfm/pmsm")
        self.spec = load_spec(os.path.join(ROOT, "examples", "user_tr48.json"))
        from emachine.machines.tfm import design
        with open(os.path.join(ROOT, "examples", "user_tr48_design.json")) as f:
            self.values = design.clip(self.spec, json.load(f))
        self.design = design

    def test_identity(self):
        self.assertIsInstance(self.machine, interfaces.Machine)
        self.assertEqual(self.machine.key(), "tfm/pmsm")
        self.assertIn("tfm/pmsm", registry.names("machine"))
        self.assertIn("stator", self.machine.options())
        self.assertEqual(self.machine.rotors, ("halbach", "surface", "spoke", "axial_ring"))

    def test_variables_and_derive(self):
        variables = self.machine.variables(self.spec)
        self.assertTrue(all(isinstance(v, types.Variable) for v in variables))
        self.assertEqual([v.as_dict() for v in variables], self.design.variables(self.spec))
        self.assertEqual(self.machine.derive(self.spec, self.values), self.design.derived(self.spec, self.values))

    def test_checks(self):
        from emachine.machines.tfm import checks
        found = self.machine.checks(self.spec, self.values)
        self.assertTrue(all(isinstance(c, types.Check) for c in found))
        self.assertEqual([c.as_dict() for c in found], [c.as_dict() for c in checks.check(self.spec, self.values)])
        self.assertTrue(all(c.ok for c in found))

    def test_geometry_winding_excitation_thermal(self):
        request = self.machine.geometry(self.spec, self.values)
        self.assertEqual(request.kind, "tfm.sector3d")
        self.assertEqual(request.parameters, self.design.to_parameters(self.spec, self.values))
        d = self.design.derived(self.spec, self.values)
        winding = self.machine.winding(self.spec, self.values)
        self.assertEqual(winding.phases, 3)
        self.assertAlmostEqual(winding.coil_area_mm2, d["coil_area_mm2"])
        self.assertAlmostEqual(winding.mean_turn_length_mm, d["turn_length_mm"])
        plan = self.machine.excitation(self.spec, self.values)
        self.assertEqual(plan.mode, "single_phase_shifted")
        self.assertAlmostEqual(plan.electrical_period_deg, 360.0 / 24)
        self.assertEqual(plan.positions, self.spec["fidelity"]["positions"])
        network = self.machine.thermal_network(self.spec, self.values)
        self.assertEqual({n for c in network.conductances for n in c[:2]}, {"winding", "core", "rotor", "ambient"})


if __name__ == "__main__":
    unittest.main()
