"""T42: ParaView export of a radial-flux machine (2D cross-section extruded to the stack)."""

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.analysis import section_export
from emachine.io import paraview_files, vtk

SPEC = os.path.join(ROOT, "examples", "rfm_spm_12s10p.json")
DESIGN = os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")
MAP = os.path.join(ROOT, "runs", "rfm_spm_12s10p", "map")


def annulus_mesh(r0=10.0, r1=11.0, rings=3, sectors=360):
    """Triangulated annulus: polar grid, every quadrilateral split in two."""
    radii = np.linspace(r0, r1, rings)
    angles = np.radians(np.arange(sectors) * 360.0 / sectors)
    points = np.array([[r * math.cos(a), r * math.sin(a)] for r in radii for a in angles])
    triangles = []
    for i in range(rings - 1):
        for j in range(sectors):
            a, b = i * sectors + j, i * sectors + (j + 1) % sectors
            c, d = a + sectors, b + sectors
            triangles += [[a, b, d], [a, d, c]]
    return points, np.array(triangles)


def wedge_volumes(points, wedges):
    """Signed volume of each wedge as VTK computes it (vtkCellSizeFilter): base area times height,
    positive when the base triangle's normal points towards the top triangle."""
    p = points[wedges]
    normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]) / 2
    return np.einsum("ij,ij->i", normal, p[:, 3] - p[:, 0])


class ExtrudeTest(unittest.TestCase):
    def test_t42_1_wedges_positive_volume(self):
        points = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 1.0], [2.0, 1.0]])
        triangles = np.array([[0, 1, 2], [1, 2, 3]])            # first counter-clockwise, second clockwise
        p3, wedges = section_export.extrude(points, triangles, 40.0)
        self.assertEqual(p3.shape, (8, 3))
        self.assertEqual(wedges.shape, (2, 6))
        self.assertEqual(sorted(set(p3[:, 2])), [-20.0, 20.0])
        volumes = wedge_volumes(p3, wedges)
        self.assertTrue(np.all(volumes > 0), volumes)
        self.assertAlmostEqual(float(volumes.sum()), 2.0 * 40.0, places=9)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.vtu")
            vtk.write_vtu(path, p3, wedges, vtk.WEDGE, {"A_z": np.arange(8.0)}, {"material": np.array([4, 3])})
            back = vtk.read_vtu(path)
        self.assertEqual(back["cell_type"], vtk.WEDGE)
        np.testing.assert_array_equal(back["cells"], wedges)
        np.testing.assert_allclose(back["points"], p3)


class GapSamplingTest(unittest.TestCase):
    def test_t42_2_uniform_field(self):
        points, triangles = annulus_mesh()
        b = np.tile([0.3, 0.4], (len(triangles), 1))
        theta, b_xy = section_export.sample_circle(points, triangles, b, 10.5, 720)
        self.assertEqual(len(theta), 720)
        phi = np.radians(theta)
        np.testing.assert_allclose(b_xy[:, 0] * np.cos(phi) + b_xy[:, 1] * np.sin(phi),
                                   0.3 * np.cos(phi) + 0.4 * np.sin(phi), atol=1e-9)

    def test_t42_2_containing_triangle(self):
        """A field that points along the centroid of each triangle: only the triangle that holds the
        sample gives a radial component of almost 1."""
        points, triangles = annulus_mesh()
        centre = points[triangles].mean(axis=1)
        b = centre / np.linalg.norm(centre, axis=1)[:, None]
        theta, b_xy = section_export.sample_circle(points, triangles, b, 10.37, 720)
        phi = np.radians(theta)
        b_r = b_xy[:, 0] * np.cos(phi) + b_xy[:, 1] * np.sin(phi)
        self.assertGreater(float(b_r.min()), math.cos(math.radians(1.0)))


class FullMotorTest(unittest.TestCase):
    def test_t42_3_ring_with_all_phases_is_written_once(self):
        points = np.array([[10, 0, 0], [11, 0, 0], [10, 1, 0], [10, 0, 1]], dtype=float)
        with tempfile.TemporaryDirectory() as tmp:
            vtk.write_vtu(os.path.join(tmp, "full_ring.vtu"), points, [[0, 1, 2, 3]], vtk.TETRA,
                          {"B": np.zeros((4, 3))}, {"material": np.array([2]), "phase": np.array([3])})
            with open(os.path.join(tmp, "summary.json"), "w") as f:
                json.dump({"phases": 3, "phase_pitch_mm": 0.0, "phase_turn_deg": 0.0, "ring_has_all_phases": True}, f)
            motor = vtk.read_vtu(paraview_files.full_motor(tmp))
        self.assertEqual(len(motor["cells"]), 1)
        self.assertEqual(motor["cell_data"]["phase"].tolist(), [3])
        self.assertEqual(motor["cell_type"], vtk.TETRA)


class TablesTest(unittest.TestCase):
    def test_t42_4_no_phase_torque_column(self):
        from emachine.cli import export
        from emachine.io import paraview_views as views
        r = {"steps": 2, "rotor_angle_deg": [0, 1], "electrical_angle_deg": [0, 5], "phase_current_A": [0, 1],
             "phase_torque_Nm": None, "machine_torque_Nm": [1.0, 1.1], "cogging_torque_Nm": [0.0, 0.01],
             "flux_linkage_Wb": [1e-3, 0.9e-3], "no_load_flux_linkage_Wb": [1e-3, 0.9e-3],
             "induced_voltage_V": [0.0, 1.0], "terminal_voltage_V": [0.1, 1.1], "airgap_b_radial_under_leg_T": None}
        columns, rows = export.waveform_table(r)
        self.assertNotIn("phase_torque_Nm", columns)
        self.assertNotIn("airgap_b_radial_under_leg_T", columns)
        self.assertIn("machine_torque_Nm", columns)
        self.assertEqual(len(rows[0]), len(columns))
        with tempfile.TemporaryDirectory() as tmp:
            export.write_csv(os.path.join(tmp, "waveforms.csv"), columns, rows)
            missing = views.check_inputs(tmp, tmp)
        self.assertFalse([m for m in missing if "waveforms.csv" in m], missing)


@slow
class ReferenceExportTest(unittest.TestCase):
    """T42-5: export of the 12-slot 10-pole reference machine, 6 positions per half period."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = os.path.join(cls.tmp.name, "paraview")
        result = subprocess.run([sys.executable, "-m", "emachine", "export", "--spec", SPEC, "--design", DESIGN,
                                 "--out", cls.out, "--positions", "6", "--turns", "20"]
                                + (["--map", MAP] if os.path.isfile(os.path.join(MAP, "efficiency_map.csv")) else []),
                                capture_output=True, text=True, cwd=ROOT)
        cls.output = result.stdout + result.stderr
        cls.returncode = result.returncode
        if result.returncode == 0:
            with open(os.path.join(cls.out, "summary.json")) as f:
                cls.summary = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.returncode, 0, self.output[-3000:])

    def test_t42_5_files_and_counts(self):
        from emachine.io import paraview_views as views
        self.assertEqual(self.summary["steps"], 12)
        for name in ("machine", "air", "airgap"):
            entries = vtk.read_pvd(os.path.join(self.out, name + ".pvd"))
            self.assertEqual(len(entries), 12, name)
            times = [t for t, _ in entries]
            self.assertEqual(times, sorted(times))
        machine = vtk.read_vtu(vtk.read_pvd(os.path.join(self.out, "machine.pvd"))[0][1])
        air = vtk.read_vtu(vtk.read_pvd(os.path.join(self.out, "air.pvd"))[0][1])
        self.assertEqual(machine["cell_type"], vtk.WEDGE)
        self.assertNotIn(1, set(machine["cell_data"]["material"].tolist()))
        self.assertEqual(set(air["cell_data"]["material"].tolist()), {1})
        self.assertEqual(set(machine["cell_data"]["material"].tolist()), {2, 3, 4, 5})
        self.assertEqual(set(machine["cell_data"]["phase"].tolist()), {0, 1, 2, 3})
        self.assertTrue(np.all(wedge_volumes(machine["points"], machine["cells"]) > 0))
        # the whole machine at the step of highest torque (the mesh is made again at every step)
        best = int(np.argmax(self.summary["machine_torque_Nm"]))
        at_best = vtk.read_vtu(vtk.read_pvd(os.path.join(self.out, "machine.pvd"))[best][1])
        motor = vtk.read_vtu(os.path.join(self.out, "full_motor.vtu"))
        self.assertEqual(len(motor["cells"]), len(at_best["cells"]))
        self.assertEqual(set(motor["cell_data"]["phase"].tolist()), {0, 1, 2, 3})
        missing = views.check_inputs(self.out, self.out if os.path.isfile(os.path.join(self.out, "efficiency_map.vtu"))
                                     else MAP)
        self.assertEqual([m for m in missing if "efficiency" not in m], [])

    def test_t42_5_torque_equals_the_evaluation_sweep(self):
        from emachine.pipeline import design_space
        from emachine.pipeline.sweep import sweep
        from emachine.spec import load_spec
        spec = load_spec(SPEC)
        with open(DESIGN) as f:
            values = json.load(f)
        request = design_space.geometry(spec, values)
        d = design_space.derived(spec, values)
        with tempfile.TemporaryDirectory() as tmp:
            reference = sweep(request.parameters, 6, tmp, ampere_turns_peak=d["ampere_turns_peak"], core_field=False,
                              geometry=request.kind)
        exported = np.array(self.summary["machine_torque_Nm"])[:6]
        np.testing.assert_allclose(exported, reference["torque_Nm"], rtol=5e-3, atol=5e-3 * abs(reference["torque_Nm"]).max())

    def test_t42_5_magnets(self):
        from emachine.spec import load_spec
        spec = load_spec(SPEC)
        machine = vtk.read_vtu(vtk.read_pvd(os.path.join(self.out, "machine.pvd"))[0][1])
        magnet = machine["cell_data"]["material"] == 3
        m = machine["cell_data"]["magnetization"][magnet]
        remanence = spec["materials"]["magnet"]["remanence_T"]
        mu_r = spec["materials"]["magnet"]["mu_r"]
        np.testing.assert_allclose(np.linalg.norm(m, axis=1), remanence / (4e-7 * math.pi * mu_r), rtol=1e-3)
        centre = machine["points"][machine["cells"][magnet]].mean(axis=1)
        radial = np.einsum("ij,ij->i", m[:, :2], centre[:, :2]) / np.linalg.norm(centre[:, :2], axis=1)
        self.assertEqual(set(np.sign(np.round(radial / np.linalg.norm(m, axis=1), 3)).tolist()), {-1.0, 1.0})
        self.assertLess(self.summary["magnet_share_below_0T"], 0.01)

    def test_t42_5_gap_field_and_core_loss(self):
        gap = vtk.read_vtu(vtk.read_pvd(os.path.join(self.out, "airgap.pvd"))[0][1])
        b_r = gap["point_data"]["B_radial"]
        self.assertLess(abs(float(b_r.mean())), 0.02 * float(np.abs(b_r).max()))
        self.assertGreater(float(np.abs(b_r).max()), 0.4)
        core = vtk.read_vtu(os.path.join(self.out, "core_loss.vtu"))
        volume_m3 = wedge_volumes(core["points"], core["cells"]) * 1e-9
        total = float(np.sum(core["cell_data"]["loss_density_W_per_m3"] * volume_m3))
        expected = self.summary["iron"]["iron_loss_W"] * self.summary["phases"]
        self.assertAlmostEqual(total / expected, 1.0, delta=0.01)


@slow
class RenderTest(unittest.TestCase):
    def test_t42_6_views_with_paraview(self):
        from emachine.io.pvpython import find_pvpython
        pvpython = find_pvpython()
        export = os.path.join(ROOT, "runs", "rfm_spm_12s10p", "paraview")
        if not pvpython or not os.path.isfile(os.path.join(export, "efficiency_map.vtu")):
            self.skipTest("no ParaView or no export in runs/rfm_spm_12s10p/paraview")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([pvpython, "--force-offscreen-rendering", os.path.join(ROOT, "emachine", "io", "paraview_views.py"),
                                     "--export", export, "--map", export, "--out", tmp],
                                    capture_output=True, text=True, cwd=ROOT)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output[-3000:])
            self.assertNotIn("failed", output)
            self.assertNotIn("WARN", output)
            self.assertEqual(sorted(os.listdir(tmp)), ["1_full_motor.png", "2_segment_field.png", "3_mesh.png",
                                                      "4_torque_vs_angle.png", "5_efficiency_map.png"])
        check = ("exec(open(%r).read(), {'__name__': '__main__'})\n"
                 "from paraview.simple import GetLayouts\nprint('LAYOUTS', len(GetLayouts()))"
                 % os.path.join(export, "open_in_paraview.py"))
        result = subprocess.run([pvpython, "--force-offscreen-rendering", "-c", check],
                                capture_output=True, text=True, cwd=ROOT)
        output = result.stdout + result.stderr
        self.assertNotIn("failed", output, output[-3000:])
        self.assertIn("LAYOUTS 5", output)
        # the wedges as ParaView sees them: every volume positive, the sum = section area x stack length
        sizes = ("import vtk\nr = vtk.vtkXMLUnstructuredGridReader()\nr.SetFileName(%r)\n"
                 "f = vtk.vtkCellSizeFilter()\nf.SetInputConnection(r.GetOutputPort())\nf.Update()\n"
                 "v = f.GetOutput().GetCellData().GetArray('Volume')\n"
                 "values = [v.GetValue(i) for i in range(v.GetNumberOfTuples())]\n"
                 "print('VOLUMES', min(values), sum(values))" % os.path.join(export, "full_motor.vtu"))
        result = subprocess.run([pvpython, "-c", sizes], capture_output=True, text=True, cwd=ROOT)
        smallest, total = map(float, result.stdout.split("VOLUMES")[1].split())
        self.assertGreater(smallest, 0.0)
        motor = vtk.read_vtu(os.path.join(export, "full_motor.vtu"))
        self.assertAlmostEqual(total / float(wedge_volumes(motor["points"], motor["cells"]).sum()), 1.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
