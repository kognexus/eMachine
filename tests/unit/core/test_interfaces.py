"""T32-1: abstract interfaces of emachine.core."""

import unittest

from emachine.core import interfaces


class InterfacesTest(unittest.TestCase):
    def test_cannot_instantiate_without_methods(self):
        for name in ("Machine", "GeometryBuilder", "FieldSolver", "LossModel", "ThermalModel", "Optimizer"):
            cls = getattr(interfaces, name)
            with self.subTest(interface=name):
                with self.assertRaises(TypeError):
                    cls()

    def test_complete_subclass_works(self):
        class Solver(interfaces.FieldSolver):
            name = "fake"

            def solve(self, mesh, excitation, workdir):
                return "solved"

        self.assertEqual(Solver().solve(None, None, None), "solved")

    def test_machine_declares_identity(self):
        methods = {m for m in dir(interfaces.Machine) if not m.startswith("_")}
        for required in ("flux_path", "principle", "rotors", "rotor_status", "options", "variables", "derive", "checks", "geometry",
                         "winding", "thermal_network", "excitation", "key"):
            self.assertIn(required, methods)


if __name__ == "__main__":
    unittest.main()
