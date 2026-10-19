"""T26: arched valleys between the teeth of the toothed ring."""

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import FEATURESCRIPT, ROOT, slow

from emachine.machines.tfm.cad import sheet as onshape
from tickets.test_t24_toothed_ring import MESHER, STATOR, params, stator_only

ARCHED = dict(STATOR, ring_arched_valleys=True)


def corner(R, gap, half, sign):
    """Tooth corner in the frame of the valley centre: (tangential, height above the air gap)."""
    phi = gap / 2 - math.asin(half / R)
    return R * math.sin(phi), sign * (R * math.cos(phi) - R)


def removed_area(R, gap, half, depth, sign):
    """Iron removed by one valley, per unit of axial length, by integration across the valley."""
    xc, zc = corner(R, gap, half, sign)
    x = np.linspace(-xc, xc, 200001)
    if depth - zc <= xc:                                   # one arc through both corners and the bottom
        z0 = (xc ** 2 + zc ** 2 - depth ** 2) / (2 * (zc - depth))
        top = z0 + np.sqrt((depth - z0) ** 2 - x ** 2)
    else:                                                  # half circle with straight sides
        top = (depth - xc) + np.sqrt(np.maximum(xc ** 2 - x ** 2, 0.0))
    air_gap = sign * (np.sqrt(R ** 2 - x ** 2) - R)          # the iron starts at the air-gap circle
    return np.trapezoid(top - air_gap, x)


def expected_core(sp):
    R, p, sign = sp["air_gap_radius"], sp["pole_pairs"], -1 if sp["inner_stator"] else 1
    pitch = math.pi / p
    half = sp["tooth_span"] * R * pitch / 2
    shift = math.radians(sp["pole_shift_deg"])
    leg, slot_w, slot_h, depth = sp["leg_width"], sp["slot_width"], sp["slot_height"], sp["ring_tooth_height"]
    top = slot_h + sp["yoke_height"]

    def ring(z0, z1, width):
        return math.pi * abs((R + sign * z1) ** 2 - (R + sign * z0) ** 2) * width

    gaps = [2 * pitch + (shift if k % 2 == 0 else -shift) for k in range(p)]
    valleys = 2 * leg * sum(removed_area(R, g, half, depth, sign) for g in gaps)
    return ring(0.0, slot_h, 2 * leg) + ring(slot_h, top, slot_w + 2 * leg) - valleys


def arch_case(sp):
    R, p, sign = sp["air_gap_radius"], sp["pole_pairs"], -1 if sp["inner_stator"] else 1
    xc, zc = corner(R, 2 * math.pi / p, sp["tooth_span"] * R * math.pi / p / 2, sign)
    return "arc" if sp["ring_tooth_height"] - zc <= xc else "half circle"


class SourceTest(unittest.TestCase):
    def test_t26_4_featurescript_and_sheet(self):
        with open(os.path.join(FEATURESCRIPT, "tfm_stator.fs")) as f:
            source = f.read()
        self.assertIn('annotation { "Name" : "Arched valleys between teeth", "Default" : false }', source)
        self.assertIn('"archedValleys" : false', source)
        self.assertIn("function tfmValleyCutter(", source)
        rows = {r["field"]: r for r in onshape.stator_rows(ARCHED)}
        self.assertEqual(rows["Arched valleys between teeth"]["text"], "on")
        rows = {r["field"]: r for r in onshape.stator_rows(STATOR)}
        self.assertEqual(rows["Arched valleys between teeth"]["text"], "off")


@slow
class MesherTest(unittest.TestCase):
    def test_t26_1_volumes(self):
        cases = []
        for inner in (True, False):
            for shift in (0.0, 3.0):
                for depth in (3.0, 7.0):
                    cases.append(dict(ARCHED, inner_stator=inner, pole_shift_deg=shift, ring_tooth_height=depth))
        self.assertEqual({arch_case(sp) for sp in cases}, {"arc", "half circle"})
        for sp in cases:
            with self.subTest(inner_stator=sp["inner_stator"], shift=sp["pole_shift_deg"], case=arch_case(sp)), \
                    tempfile.TemporaryDirectory() as tmp:
                result = stator_only(tmp, sp)
                self.assertEqual(result.returncode, 0, result.stderr[-800:])
                volumes = {m.group(1): (int(m.group(2)), float(m.group(3))) for m in
                           re.finditer(r"volume\s+(\S+)\s+(\d+) solids\s+([\d.]+) mm\^3", result.stdout)}
                self.assertEqual(volumes["tfm_core"][0], 1)
                self.assertAlmostEqual(volumes["tfm_core"][1] / expected_core(sp), 1.0, delta=0.001)

    def test_t26_2_sector_mesh(self):
        for style in ("outrunner", "inrunner"):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "machine.json")
                with open(path, "w") as f:
                    json.dump(params(style, ring_arched_valleys=True), f)
                mesh = os.path.join(tmp, "sector.msh")
                result = subprocess.run([sys.executable, *MESHER, "--params", path, "--out", mesh],
                                        capture_output=True, text=True, cwd=ROOT)
                self.assertEqual(result.returncode, 0, result.stdout[-800:] + result.stderr[-800:])
                check = subprocess.run([sys.executable, "-m", "emachine", "check-mesh", mesh],
                                       capture_output=True, text=True, cwd=ROOT)
                self.assertIn("node ids shared between the two sides: 0 ", check.stdout)
                for a, b, hits in re.findall(r"A (\d+) nodes, B (\d+) nodes, matched after rotation (\d+)", check.stdout):
                    self.assertTrue(a == b == hits)
                # Every node of the mesh file is counted by the mesher (no free construction points).
                with open(os.path.splitext(mesh)[0] + ".regions.json") as f:
                    counted = json.load(f)["mesh"]["nodes"]
                with open(mesh) as f:
                    text = f.read()
                self.assertEqual(int(text.split("$Nodes\n", 1)[1].split("\n", 1)[0]), counted)


@slow
class FieldTest(unittest.TestCase):
    def test_t26_3_no_load_flux_changes_sign(self):
        from emachine.pipeline import sweep
        from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS
        analysis = dict(ANALYSIS_DEFAULTS, coil_turns=1)
        machine = params("outrunner", ring_arched_valleys=True)
        pitch = 180.0 / STATOR["pole_pairs"]
        with tempfile.TemporaryDirectory() as tmp:
            fluxes = [sweep.solve_position(machine, analysis, angle, os.path.join(tmp, f"p{k}"),
                                                  current=0.0)["flux_linkage_Wb"]
                      for k, angle in enumerate((0.0, pitch))]
        self.assertLess(fluxes[0] * fluxes[1], 0.0, fluxes)
        self.assertAlmostEqual(abs(fluxes[1] / fluxes[0]), 1.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
