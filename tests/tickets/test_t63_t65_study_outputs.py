"""T63 to T65: picks of a run, Pareto front, report HTML, Pareto page, ParaView export helpers."""

import json
import os
import tempfile
import unittest

import numpy as np
import helpers  # noqa: F401  (puts the project on the path)

from emachine.analysis import topology_export as X
from emachine.analysis import topology_report as R
from emachine.analysis.topology_study import picks

#: The parts of a study configuration (emachine study --config) that the picks and the Pareto page read.
CFG = {"limits": {"pick_max_ripple": 0.25},
       "reference": {"rated_torque_Nm": 2.0, "peak_torque_Nm": 5.0},
       "drive": {"bus_voltage_V": 48.0, "rated_current_A": 10.5, "peak_current_A": 42.0, "speed_rpm": 1000.0}}


def design(i, torque, ripple, ok=True):
    return {"id": i, "analysed": True, "violation": 0.0 if ok else 1.0, "torque_Nm": torque, "peak_torque_Nm": 3 * torque,
            "ripple": ripple, "efficiency": 0.85, "values": {"a": i}, "losses_W": {"total": 10.0}, "kt_Nm_A": torque / 10.5,
            "winding": {}, "masses": {"active_kg": 0.7}}


class PicksTest(unittest.TestCase):
    def test_t63_picks(self):
        ds = [design(1, 3.0, 0.40), design(2, 2.8, 0.10), design(3, 3.5, 0.05, ok=False), design(4, 2.9, 0.20)]
        chosen = picks(ds, CFG)
        self.assertEqual(chosen["highest_torque"]["id"], 1)          # 3 violates a limit
        self.assertEqual(chosen["optimal"]["id"], 4)                 # most torque with ripple <= 25 %

    def test_t64_pareto_front(self):
        pts = [(1, 1, -0.1), (2, 1, -0.2), (1, 2, -0.3), (0.5, 0.5, -0.5)]
        self.assertEqual(sorted(R.pareto_front(pts)), [0, 1, 2])


class ReportTest(unittest.TestCase):
    def test_t64_markdown_subset(self):
        page = R.md_to_html("# Title\n\nText **bold** and `code`.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- one\n- two\n\n![x](f.svg)", "T")
        for part in ("<h1", "<strong>bold</strong>", "<code>code</code>", "<table>", "<li>one</li>", '<img alt="x" src="f.svg">'):
            self.assertIn(part, page)
        self.assertIn("prefers-color-scheme:dark", page)

    def test_t64_pareto_page_is_self_contained(self):
        data = {"rfm_spm_in": {"title": "t", "summary": "s", "designs": [design(1, 3.0, 0.1), design(2, 2.0, 0.3)],
                               "picks": {"optimal": design(1, 3.0, 0.1)}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.html")
            R.write_pareto(data, CFG, path)
            with open(path) as f:
                page = f.read()
        self.assertNotIn("<script src", page)
        self.assertIn('"front"', page)
        payload = json.loads(page.split("const DATA = ")[1].split(";\n")[0])
        self.assertEqual(payload["topologies"]["rfm_spm_in"]["picks"]["optimal"], 1)


class ExportTest(unittest.TestCase):
    def test_t65_material_codes(self):
        self.assertEqual(X.material_code("coil_0_1_0", {"kind": "coil", "phase": 2}), 6)
        self.assertEqual(X.material_code("stator_core", {"kind": "core", "side": "stator"}), 1)
        self.assertEqual(X.material_code("magnet_1_0", {"kind": "magnet"}), 3)

    def test_t65_merge_offsets(self):
        a = (np.zeros((3, 3)), np.array([[0, 1, 2]]), {"B_mag": np.array([1.0])}, {"A_z": np.zeros(3)})
        b = (np.ones((3, 3)), np.array([[0, 1, 2]]), {"B_mag": np.array([2.0])}, {"A_z": np.ones(3)})
        pts, tri, cell, point = X.merge([a, b])
        self.assertEqual(tri.tolist(), [[0, 1, 2], [3, 4, 5]])
        self.assertEqual(cell["B_mag"].tolist(), [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
