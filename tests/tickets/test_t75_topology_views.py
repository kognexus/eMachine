"""T75, T76: standard ParaView views of a topology export (machine_3d.vtu, torque.csv, back_emf.csv,
open_in_paraview.py) and their tabs, colours and chart axes in the GUI."""

import csv
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from helpers import ROOT, slow

from emachine.analysis import topology_export as X
from emachine.io.vtk import TRIANGLE, WEDGE, read_vtu, write_pvd, write_vtu

PE = 14                      # electrical per mechanical angle of the synthetic machine
STACK = 30.0


def disc_section(n=12, radius=40.0):
    """A small triangulated disc: centre point and a ring, materials 1 to 7 round the ring."""
    angles = np.linspace(0, 2 * math.pi, n, endpoint=False)
    pts = np.vstack([[0.0, 0.0, 0.0], np.column_stack([radius * np.cos(angles), radius * np.sin(angles), np.zeros(n)])])
    tri = np.array([[0, 1 + k, 1 + (k + 1) % n] for k in range(n)])
    cell = {"B": np.tile([0.1, 0.2, 0.0], (n, 1)), "B_mag": np.full(n, 0.5), "material": np.arange(n) % 8 * 1.0,
            "region": np.arange(n) * 1.0}
    return pts, tri, cell, {"A_z": np.linspace(-1e-3, 1e-3, n + 1)}


def record(positions=6):
    torque = [3.0 + 0.2 * math.cos(2 * math.pi * 6 * k / positions) for k in range(positions)]
    angle = np.radians(np.arange(2 * positions) * 360.0 / (2 * positions))
    emf = np.column_stack([20 * np.sin(angle - k * 2 * math.pi / 3) for k in range(3)])
    return {"machine": "rfm_halbach_in", "principle": "pm", "pick": "optimal", "torque_Nm": float(np.mean(torque)),
            "ripple": (max(torque) - min(torque)) / float(np.mean(torque)), "torque_waveform_Nm": torque,
            "no_load": {"emf_V": emf.tolist(), "emf_phase_peak_V": 20.0}, "design": {"pe": PE}}


def synthetic_export(out, positions=6):
    """An export as topology_export writes it (rated series, summary.json), without the T75 files."""
    pts, tri, cell, point = disc_section()
    files = []
    for k in range(positions):
        path = os.path.join(out, f"rated_rated_{k:02d}.vtu")
        write_vtu(path, pts, tri, TRIANGLE, point_data=point, cell_data=cell)
        files.append((k * 180.0 / positions, path))
    write_pvd(os.path.join(out, "rated.pvd"), files)
    rec = record(positions)
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump({"machine": rec["machine"], "pick": "optimal", "kind": "radial", "torque_Nm": rec["torque_Nm"],
                   "ripple": rec["ripple"], "files": {"rated": [os.path.basename(p) for _, p in files]},
                   "torque_waveform_Nm": rec["torque_waveform_Nm"]}, f)
    return rec


def rows(path):
    with open(path) as f:
        return list(csv.DictReader(f))


class ViewFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t75_")
        self.rec = synthetic_export(self.tmp)
        X.write_view_files(self.tmp, self.rec, STACK)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_t75_1_extruded_geometry(self):
        section = read_vtu(os.path.join(self.tmp, "rated_rated_00.vtu"))
        solid = read_vtu(os.path.join(self.tmp, "machine_3d.vtu"))
        self.assertEqual(solid["cell_type"], WEDGE)
        self.assertEqual(len(solid["points"]), 2 * len(section["points"]))
        self.assertEqual(len(solid["cells"]), len(section["cells"]))
        z = solid["points"][:, 2]
        self.assertAlmostEqual(z.min(), -STACK / 2)
        self.assertAlmostEqual(z.max(), STACK / 2)
        np.testing.assert_array_equal(solid["cell_data"]["material"], section["cell_data"]["material"])
        for name in ("region", "B_mag"):
            self.assertIn(name, solid["cell_data"])

    def test_t75_2_torque_table(self):
        table = rows(os.path.join(self.tmp, "torque.csv"))
        torque = [float(r["torque_Nm"]) for r in table]
        np.testing.assert_allclose(torque, self.rec["torque_waveform_Nm"])
        np.testing.assert_allclose([float(r["angle_el_deg"]) for r in table], np.arange(6) * 30.0)
        mean = float(table[0]["mean_Nm"])
        self.assertAlmostEqual(mean, self.rec["torque_Nm"])
        self.assertAlmostEqual((max(torque) - min(torque)) / mean, self.rec["ripple"])
        with open(os.path.join(self.tmp, "summary.json")) as f:
            summary = json.load(f)
        self.assertAlmostEqual(summary["ripple_percent"], 100 * self.rec["ripple"])
        self.assertEqual(summary["stack_length_mm"], STACK)

    def test_t75_3_back_emf_table(self):
        table = rows(os.path.join(self.tmp, "back_emf.csv"))
        emf = np.array([[float(r[k]) for k in ("emf_a_V", "emf_b_V", "emf_c_V")] for r in table])
        np.testing.assert_allclose(emf, self.rec["no_load"]["emf_V"])
        angle = [float(r["angle_el_deg"]) for r in table]
        self.assertEqual(angle[0], 0.0)
        self.assertAlmostEqual(angle[1] - angle[0], 360.0 / len(table))

    def test_t75_4_open_script(self):
        with open(os.path.join(self.tmp, "open_in_paraview.py")) as f:
            script = f.read()
        self.assertIn("section_views", script)
        self.assertIn("--interactive", script)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "section_views.py")))
        with open(os.path.join(ROOT, "emachine", "io", "section_views.py")) as f:
            source = f.read()
        self.assertNotIn("import emachine", source)          # runs in ParaView's own Python
        self.assertNotIn("from emachine", source)

    def test_t75_5_check_without_paraview(self):
        result = subprocess.run([sys.executable, os.path.join(self.tmp, "section_views.py"), "--export", self.tmp,
                                 "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        os.remove(os.path.join(self.tmp, "back_emf.csv"))         # optional (T78): view 5 is left out
        result = subprocess.run([sys.executable, os.path.join(self.tmp, "section_views.py"), "--export", self.tmp,
                                 "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("view 5", result.stdout)
        os.remove(os.path.join(self.tmp, "torque.csv"))           # required
        result = subprocess.run([sys.executable, os.path.join(self.tmp, "section_views.py"), "--export", self.tmp,
                                 "--check"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("torque.csv", result.stdout + result.stderr)

    def test_without_stack_length_the_3d_file_is_left_out(self):
        tmp = tempfile.mkdtemp(prefix="t75_")
        try:
            rec = synthetic_export(tmp)
            X.write_view_files(tmp, rec, None)
            self.assertFalse(os.path.exists(os.path.join(tmp, "machine_3d.vtu")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "torque.csv")))
        finally:
            shutil.rmtree(tmp)


class RefreshTest(unittest.TestCase):
    def test_t75_7_refresh_leaves_the_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, run = os.path.join(tmp, "export"), os.path.join(tmp, "run")
            os.makedirs(out)
            os.makedirs(os.path.join(run, "verify"))
            rec = synthetic_export(out)
            with open(os.path.join(run, "verify", "optimal.json"), "w") as f:
                json.dump(rec, f)
            before = {n: os.path.getmtime(os.path.join(out, n)) for n in os.listdir(out) if n.startswith("rated_")}
            X.main(["--refresh", "--run", run, "--pick", "optimal", "--out", out, "--stack-length", str(STACK)])
            after = {n: os.path.getmtime(os.path.join(out, n)) for n in before}
            self.assertEqual(before, after)
            for name in ("machine_3d.vtu", "torque.csv", "back_emf.csv", "open_in_paraview.py", "section_views.py"):
                self.assertTrue(os.path.isfile(os.path.join(out, name)), name)


@slow
class PictureTest(unittest.TestCase):
    def test_t75_6_pictures_with_pvpython(self):
        pvpython = pvpython_or_skip(self)
        with tempfile.TemporaryDirectory() as tmp:
            rec = synthetic_export(tmp)
            X.write_view_files(tmp, rec, STACK)
            pictures = os.path.join(tmp, "views")
            result = subprocess.run([pvpython, "--force-offscreen-rendering", os.path.join(tmp, "section_views.py"),
                                     "--export", tmp, "--out", pictures], capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
            for name in ("1_geometry_3d.png", "2_section_mesh.png", "3_em_field.png", "4_torque.png", "5_back_emf.png"):
                path = os.path.join(pictures, name)
                self.assertTrue(os.path.isfile(path) and os.path.getsize(path) > 10000, name)


GUI_PROBE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import section_views as views
views.main(["--export", sys.argv[1], "--interactive"])
from paraview.simple import GetLayouts, GetViewsInLayout, GetColorTransferFunction
tabs = {}
for (name, _), layout in GetLayouts().items():
    tabs[name] = [v.GetXMLName() for v in GetViewsInLayout(layout)]
charts = []
for (name, _), layout in GetLayouts().items():
    for v in GetViewsInLayout(layout):
        if v.GetXMLName() == "XYChartView":
            for d in v.Representations:          # the displays the views made (asking for others would create them)
                if d.Visibility and d.GetXMLName() == "XYChartRepresentation":
                    charts.append([name, int(d.UseIndexForXAxis), [str(x) for x in d.XArrayName]])
lut = GetColorTransferFunction("material")
print("PROBE" + json.dumps({"tabs": tabs, "charts": charts, "categorical": lut.InterpretValuesAsCategories,
                            "annotations": list(lut.Annotations)}))
"""


def pvpython_or_skip(test):
    from emachine.io.pvpython import find_pvpython
    pvpython = find_pvpython()
    if pvpython is None:
        test.skipTest("pvpython not found (pixi install -e paraview)")
    return pvpython


@slow
class GuiLayoutTest(unittest.TestCase):
    def test_t76_tabs_colours_and_chart_axes(self):
        pvpython = pvpython_or_skip(self)
        with tempfile.TemporaryDirectory() as tmp:
            rec = synthetic_export(tmp)
            X.write_view_files(tmp, rec, STACK)
            probe = os.path.join(tmp, "probe.py")
            with open(probe, "w") as f:
                f.write(GUI_PROBE)
            result = subprocess.run([pvpython, "--force-offscreen-rendering", probe, tmp], capture_output=True,
                                    text=True, timeout=600)
            line = [l for l in result.stdout.splitlines() if l.startswith("PROBE")]
            self.assertTrue(line, result.stdout[-2000:] + result.stderr[-2000:])
            found = json.loads(line[0][len("PROBE"):])
        expected = {"1 Geometry 3D": ["RenderView"], "2 Section mesh": ["RenderView"], "3 EM field": ["RenderView"],
                    "4 Torque and ripple": ["XYChartView"], "5 Back-EMF": ["XYChartView"]}
        for name, views in expected.items():
            self.assertEqual(found["tabs"].get(name), views, found["tabs"])
        self.assertEqual(sorted(c[0] for c in found["charts"]), ["4 Torque and ripple", "5 Back-EMF"])
        for _, use_index, x in found["charts"]:
            self.assertEqual((use_index, x), (0, ["angle_el_deg"]))
        self.assertEqual(found["categorical"], 1)
        self.assertIn("Stator core", found["annotations"])


if __name__ == "__main__":
    unittest.main()
