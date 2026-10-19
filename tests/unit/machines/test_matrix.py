"""T45: the machine matrix (flux path x principle) in `list` and in docs/machines.md."""

import os
import subprocess
import sys
import unittest

from emachine.core import registry
from emachine.machines import matrix

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MatrixTest(unittest.TestCase):
    def test_t45_1_every_cell_has_a_status(self):
        cells = {cell.key: cell for cell in matrix.cells()}
        self.assertEqual(len(cells), 16)
        for cell in cells.values():
            with self.subTest(cell=cell.key):
                self.assertIn(cell.status, ("solvable", "specified", "planned", "not meaningful"))
                if cell.status in ("specified", "planned"):
                    self.assertTrue(cell.tickets and all(t.startswith(("B", "T")) for t in cell.tickets), cell.tickets)
                    for ticket in cell.tickets:          # the ID of a GitHub issue title, e.g. "B07: ..."
                        self.assertRegex(ticket, r"^[TB]\d{2}$")
                if cell.status == "not meaningful":
                    self.assertTrue(cell.reason)
        self.assertEqual(cells["tfm/pmsm"].status, "solvable")
        self.assertEqual(cells["rfm/pmsm"].status, "solvable")
        self.assertEqual(cells["rfm/synrm"].tickets, ("B07", "B08"))
        # every registered machine is a cell of the matrix
        self.assertTrue(set(registry.names("machine")) <= set(cells))

    def test_t45_2_registering_a_machine_fills_its_cell(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import FakeMachine
        saved = registry.snapshot()
        try:
            @registry.register("machine", "afm/vernier")
            class Fake(FakeMachine):
                flux_path, principle, rotors, solvable, ticket = "afm", "vernier", ("surface",), False, "B15"

            cell = {c.key: c for c in matrix.cells()}["afm/vernier"]
            self.assertEqual((cell.status, cell.tickets), ("specified", ("B15",)))
        finally:
            registry.restore(saved)

    def test_t45_3_documentation_agrees(self):
        with open(os.path.join(ROOT, "docs", "machines.md")) as f:
            self.assertEqual(f.read(), matrix.markdown(),
                             "docs/machines.md is out of date: emachine list --markdown > docs/machines.md")

    def test_t45_4_list_output(self):
        out = subprocess.run([sys.executable, "-m", "emachine", "list"], capture_output=True, text=True, cwd=ROOT).stdout
        self.assertIn("Machine matrix", out)
        self.assertTrue(all(len(line) <= 100 for line in out.splitlines()), max(map(len, out.splitlines())))
        self.assertRegex(out, r"RFM\s+solvable\s+specified \(B07, B08\)")
        flat = subprocess.run([sys.executable, "-m", "emachine", "list", "--flat"], capture_output=True, text=True,
                              cwd=ROOT).stdout
        self.assertNotIn("Machine matrix", flat)
        self.assertIn("rfm/pmsm   solvable   surface, interior (B06)", flat)


if __name__ == "__main__":
    unittest.main()
