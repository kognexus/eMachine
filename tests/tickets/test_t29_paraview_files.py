"""T29: whole motor and efficiency map as ParaView files, and the five views as tabs."""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest


import numpy as np
from helpers import ROOT, slow

from emachine.io import paraview_files as paraviewfiles
from emachine.io import vtk as vtkio
from emachine.io.pvpython import find_pvpython

USER_EXPORT = os.path.join(ROOT, "runs", "user_tr48", "paraview")


def write_ring(folder, phases=3, pitch=9.1, turn=5.0):
    """A ring of two tetrahedra: one stator core (material 4) and one magnet (material 3), no shared points."""
    points = np.array([[10, 0, 0], [11, 0, 0], [10, 1, 0], [10, 0, 1],
                       [20, 0, 0], [21, 0, 0], [20, 1, 0], [20, 0, 1]], dtype=float)
    cells = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    b = np.tile([1.0, 0.0, 0.0], (8, 1))
    vtkio.write_vtu(os.path.join(folder, "full_ring.vtu"), points, cells, vtkio.TETRA,
                    {"B": b, "B_magnitude": np.ones(8)},
                    {"region": np.array([1, 2]), "material": np.array([4, 3]), "saturation": np.zeros(2)})
    with open(os.path.join(folder, "summary.json"), "w") as f:
        json.dump({"phases": phases, "phase_pitch_mm": pitch, "phase_turn_deg": turn}, f)
    return points


def write_map(folder, speeds=(0.0, 1000.0, 2000.0), torques=(0.0, 0.5, 1.0)):
    with open(os.path.join(folder, "efficiency_map.csv"), "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["speed_rpm", "torque_Nm", "efficiency", "within_drive_limits", "continuous"])
        for s in speeds:
            for t in torques:
                out.writerow([s, t, 0.5 + s / 10000 + t / 10, int(not (s == 2000.0 and t == 1.0)), int(t < 1.0)])
    with open(os.path.join(folder, "envelope.csv"), "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["speed_rpm", "drive_torque_Nm", "continuous_torque_Nm"])
        for s in speeds:
            out.writerow([s, 1.0, 0.5])


class FullMotorTest(unittest.TestCase):
    def test_t29_1_phases_placed_as_in_the_machine(self):
        with tempfile.TemporaryDirectory() as tmp:
            points = write_ring(tmp)
            data = vtkio.read_vtu(paraviewfiles.full_motor(tmp))
            p, cd, pd = data["points"], data["cell_data"], data["point_data"]
            self.assertEqual(len(p), 3 * len(points))
            self.assertEqual(list(cd["phase"]), [1, 1, 2, 2, 3, 3])
            self.assertEqual(list(cd["material"]), [4, 3] * 3)
            for k in range(3):
                block = p[8 * k: 8 * (k + 1)]
                np.testing.assert_allclose(block[:, 2] - points[:, 2], 9.1 * k, atol=1e-6)
                # Stator turned by 5 degrees per phase, rotor not.
                self.assertAlmostEqual(np.degrees(np.arctan2(block[0, 1], block[0, 0])), 5.0 * k, places=4)
                self.assertAlmostEqual(np.degrees(np.arctan2(block[4, 1], block[4, 0])), 0.0, places=6)
                self.assertAlmostEqual(np.degrees(np.arctan2(pd["B"][8 * k, 1], pd["B"][8 * k, 0])), 5.0 * k, places=4)
                np.testing.assert_allclose(pd["B"][8 * k + 4], [1.0, 0.0, 0.0])


class EfficiencyMapTest(unittest.TestCase):
    def test_t29_2_surface_and_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_map(tmp)
            map_path, limits_path = paraviewfiles.efficiency_map(tmp)
            grid = vtkio.read_vtu(map_path)
            self.assertEqual(grid["cell_type"], vtkio.QUAD)
            self.assertEqual(len(grid["points"]), 9)
            self.assertEqual(len(grid["cells"]), 4)
            np.testing.assert_allclose(grid["points"][:, 0].max(), 2.0)        # 1000 rpm
            np.testing.assert_allclose(grid["points"][:, 1].max(), 1.0)
            # The corner at 2000 rpm and 1 N m is outside: only that cell is outside.
            self.assertEqual(list(grid["cell_data"]["within_drive_limits"]), [1, 1, 1, 0])
            self.assertAlmostEqual(grid["field_data"]["best_efficiency"], 0.5 + 0.2 + 0.05)
            np.testing.assert_allclose(grid["point_data"]["efficiency_percent"], 100 * grid["point_data"]["efficiency"])
            # Quads are counter-clockwise in the speed-torque plane (positive area).
            for quad in grid["cells"]:
                x, y = grid["points"][quad, 0], grid["points"][quad, 1]
                self.assertGreater(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y), 0.0)
            limits = vtkio.read_vtu(limits_path)
            self.assertEqual(limits["cell_type"], vtkio.LINE)
            self.assertEqual(list(np.bincount(limits["cell_data"]["curve"])), [2, 2])


class ExportFolderTest(unittest.TestCase):
    def test_t29_3_refresh_writes_what_the_views_read(self):
        sys.path.insert(0, ROOT)
        from emachine.io import paraview_views as views
        with tempfile.TemporaryDirectory() as tmp:
            export, mapdir = os.path.join(tmp, "export"), os.path.join(tmp, "map")
            os.makedirs(export)
            os.makedirs(mapdir)
            write_ring(export)
            write_map(mapdir)
            with open(os.path.join(export, "machine.pvd"), "w") as f:
                f.write('<VTKFile><Collection><DataSet timestep="0" file="full_ring.vtu"/></Collection></VTKFile>')
            with open(os.path.join(export, "waveforms.csv"), "w") as f:
                f.write("electrical_angle_deg,machine_torque_Nm,phase_torque_Nm,cogging_torque_Nm\n0,1,0.3,0\n")
            with open(os.path.join(export, "summary.json")) as f:
                summary = json.load(f)
            summary.update({"pole_pairs": 24, "machine_torque_Nm": [1.0]})
            with open(os.path.join(export, "summary.json"), "w") as f:
                json.dump(summary, f)
            result = subprocess.run([sys.executable, "-m", "emachine", "export", "--refresh", "--out", export,
                                     "--map", mapdir], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(views.check_inputs(export, export), [])
            for name in ("open_in_paraview.py", "paraview_views.py", "efficiency_map.csv", "envelope.csv"):
                self.assertTrue(os.path.isfile(os.path.join(export, name)), name)
            with open(os.path.join(export, "open_in_paraview.py")) as f:
                script = f.read()
            compile(script, "open_in_paraview.py", "exec")
            self.assertIn('"--interactive"', script)
            self.assertIn('sys.modules.pop("paraview_views", None)', script)
            self.assertIn(os.path.abspath(export), script)

    def test_t29_4_view_script_has_five_tabs(self):
        with open(os.path.join(ROOT, "emachine", "io", "paraview_views.py")) as f:
            source = f.read()
        for title in ("1 Full motor", "2 Field per material", "3 Mesh", "4 Torque vs angle", "5 Efficiency map"):
            self.assertIn(f'"{title}"', source)
        self.assertIn("full_motor.vtu", source)
        self.assertIn("efficiency_map.vtu", source)

    def test_t29_5_user_export(self):
        if not os.path.isfile(os.path.join(USER_EXPORT, "full_motor.vtu")):
            self.skipTest("runs/user_tr48/paraview has not been refreshed")
        sys.path.insert(0, ROOT)
        from emachine.io import paraview_views as views
        self.assertEqual(views.check_inputs(USER_EXPORT, USER_EXPORT), [])
        self.assertIn("phase", views.vtu_arrays(os.path.join(USER_EXPORT, "full_motor.vtu")))


@slow
class RenderTest(unittest.TestCase):
    def test_t29_6_render_and_tabs_with_paraview(self):
        pvpython = find_pvpython()
        if not pvpython or not os.path.isfile(os.path.join(USER_EXPORT, "efficiency_map.vtu")):
            self.skipTest("no ParaView or no refreshed export of runs/user_tr48")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([pvpython, "--force-offscreen-rendering", os.path.join(ROOT, "emachine", "io", "paraview_views.py"),
                                     "--export", USER_EXPORT, "--map", USER_EXPORT, "--out", tmp],
                                    capture_output=True, text=True, cwd=ROOT)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output[-3000:])
            self.assertNotIn("failed", output)
            self.assertNotIn("WARN", output)
            pictures = sorted(os.listdir(tmp))
            self.assertEqual(pictures, ["1_full_motor.png", "2_segment_field.png", "3_mesh.png",
                                        "4_torque_vs_angle.png", "5_efficiency_map.png"])
        script = os.path.join(USER_EXPORT, "open_in_paraview.py")
        check = ("exec(open(%r).read(), {'__name__': '__main__'})\n"
                 "from paraview.simple import GetLayouts\nprint('LAYOUTS', len(GetLayouts()))" % script)
        result = subprocess.run([pvpython, "--force-offscreen-rendering", "-c", check],
                                capture_output=True, text=True, cwd=ROOT)
        output = result.stdout + result.stderr
        self.assertNotIn("failed", output, output[-3000:])
        self.assertIn("LAYOUTS 5", output)


if __name__ == "__main__":
    unittest.main()
