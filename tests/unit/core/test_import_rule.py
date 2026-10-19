"""T32-4 and later: the dependency rule of docs/architecture.md, checked on the import statements.

Each package of emachine may import only the packages listed for it (and itself)."""

import ast
import os
import unittest

PACKAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                       "emachine")

#: package -> packages of emachine it may import
ALLOWED = {
    "core": set(),
    "spec": {"core"},
    "physics": {"core"},
    "io": {"core"},
    "machines": {"core", "physics", "spec", "io"},
    "solvers": {"core", "physics", "io"},
    "optimization": {"core"},
    "pipeline": {"core", "physics", "spec", "machines", "solvers", "io"},
    "analysis": {"core", "physics", "spec", "machines", "solvers", "pipeline", "io"},
    "cad": {"core", "spec", "machines", "pipeline"},
}


def imported_packages(path, package):
    """Packages of emachine imported by one file (absolute and relative imports)."""
    with open(path) as f:
        tree = ast.parse(f.read())
    found = set()
    depth_inside = os.path.relpath(os.path.dirname(path), PACKAGE).count(os.sep)   # 0 directly in the package
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0:
                if module.startswith("emachine."):
                    found.add(module.split(".")[1])
            elif node.level - 1 > depth_inside:
                found.add(module.split(".")[0] if module else "?")
        elif isinstance(node, ast.Import):
            found |= {a.name.split(".")[1] for a in node.names if a.name.startswith("emachine.")}
    return found - {package}


class ImportRuleTest(unittest.TestCase):
    def test_layers(self):
        offenders = []
        for package, allowed in ALLOWED.items():
            root = os.path.join(PACKAGE, package)
            if not os.path.isdir(root):
                continue
            for folder, _, files in os.walk(root):
                for name in files:
                    if name.endswith(".py"):
                        path = os.path.join(folder, name)
                        bad = imported_packages(path, package) - allowed
                        offenders += [(os.path.relpath(path, PACKAGE), sorted(bad))] if bad else []
        self.assertEqual(offenders, [])

    def test_core_imports_nothing(self):
        self.assertEqual(ALLOWED["core"], set())


if __name__ == "__main__":
    unittest.main()
