"""T44: one module per principle, one module per rotor layout, names as docs/naming.md."""

import importlib
import os
import unittest

from emachine.core import registry

MACHINES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                        "emachine", "machines")
PRINCIPLES = ("pmsm", "synrm", "srm", "vernier")
CLASS_PREFIX = {"tfm": "TransverseFlux", "rfm": "RadialFlux", "afm": "AxialFlux", "rafm": "RadialAxialFlux"}
CLASS_SUFFIX = {"pmsm": "PMSM", "synrm": "SynRM", "srm": "SRM", "vernier": "Vernier"}


class LayoutTest(unittest.TestCase):
    def test_t44_1_principle_modules(self):
        found = set()
        for flux_path in sorted(d for d in os.listdir(MACHINES) if os.path.isdir(os.path.join(MACHINES, d))
                                and not d.startswith("_")):
            for principle in PRINCIPLES:
                if not os.path.isfile(os.path.join(MACHINES, flux_path, principle + ".py")):
                    continue
                with self.subTest(module=f"{flux_path}/{principle}.py"):
                    module = importlib.import_module(f"emachine.machines.{flux_path}.{principle}")
                    cls = registry.get("machine", f"{flux_path}/{principle}")
                    self.assertEqual(cls.__module__, module.__name__)
                    self.assertEqual(cls.__name__, CLASS_PREFIX[flux_path] + CLASS_SUFFIX[principle])
                    self.assertEqual((cls.flux_path, cls.principle), (flux_path, principle))
                    found.add(cls.key())
        self.assertEqual(found, set(registry.names("machine")))

    def test_t44_1_rotor_layout_modules(self):
        """Slotted machines: every rotor layout is a module rotors/<layout>.py of its flux path."""
        for key in registry.names("machine"):
            cls = registry.get("machine", key)
            for layout in getattr(cls, "ROTORS", ()):
                with self.subTest(machine=key, rotor=layout.name):
                    self.assertEqual(layout.__module__, f"emachine.machines.{cls.flux_path}.rotors.{layout.name}")

    def test_t44_1_tfm_geometry_layouts(self):
        """TFM: the geometry modules of the rotor layouts carry the standard names."""
        from emachine.machines.tfm import options
        from emachine.machines.tfm.geometry import rotors
        for name in options.ROTORS:
            with self.subTest(rotor=name):
                kind = rotors.ROTORS[options.ROTOR_CODES[name]]
                self.assertEqual(type(kind).__module__.rsplit(".", 1)[1], name)

    def test_t44_2_flux_paths_do_not_import_each_other(self):
        import ast
        paths = [d for d in os.listdir(MACHINES) if d in CLASS_PREFIX]
        for flux_path in paths:
            for folder, _, files in os.walk(os.path.join(MACHINES, flux_path)):
                for name in (f for f in files if f.endswith(".py")):
                    with open(os.path.join(folder, name)) as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom):
                            module = node.module or ""
                            others = [p for p in paths if p != flux_path and (f"machines.{p}" in module
                                      or (node.level >= 2 and module.split(".")[0] == p))]
                            self.assertEqual(others, [], f"{flux_path}/{name} imports {module}")


if __name__ == "__main__":
    unittest.main()
