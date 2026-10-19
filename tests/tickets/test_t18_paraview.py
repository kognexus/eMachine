"""T18: ParaView export."""

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.machines.tfm import design
from emachine.io import vtk as vtkio
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec

SPEC = os.path.join(ROOT, "examples/tfm_single_phase.json")
MU0 = 4e-7 * math.pi


def tet_volumes(points, cells):
    p = points[cells]
    return np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6


class VtkFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.points = np.array([[1.0, 0, 0], [2.0, 0, 0], [1.0, 1.0, 0], [1.0, 0, 1.0], [2.0, 1.0, 1.0]])
        self.cells = np.array([[0, 1, 2, 3], [1, 2, 3, 4]])

    def tearDown(self):
        self.tmp.cleanup()

    def test_t18_1_round_trip(self):
        path = os.path.join(self.tmp.name, "sub", "mesh.vtu")
        point_data = {"B": np.arange(15, dtype=float).reshape(5, 3) / 7, "B_magnitude": np.linspace(0, 1, 5)}
        cell_data = {"material": np.array([3, 4]), "B_cell": np.array([[0.1, 0.2, 0.3], [-1.5, 0.0, 2.0]])}
        vtkio.write_vtu(path, self.points, self.cells, vtkio.TETRA, point_data, cell_data, {"torque_Nm": 0.8765})
        back = vtkio.read_vtu(path)
        np.testing.assert_allclose(back["points"], self.points)
        np.testing.assert_array_equal(back["cells"], self.cells)
        self.assertEqual(back["cell_type"], vtkio.TETRA)
        for name, array in point_data.items():
            np.testing.assert_allclose(back["point_data"][name], array, rtol=1e-5)
        np.testing.assert_array_equal(back["cell_data"]["material"], [3, 4])
        np.testing.assert_allclose(back["cell_data"]["B_cell"], cell_data["B_cell"], rtol=1e-5)
        self.assertAlmostEqual(back["field_data"]["torque_Nm"], 0.8765)
        with self.assertRaises(ValueError):
            vtkio.write_vtu(path, self.points, self.cells, vtkio.TETRA, {"B": np.zeros((4, 3))})

    def test_reader_rejects_wrong_counts(self):
        path = os.path.join(self.tmp.name, "mesh.vtu")
        vtkio.write_vtu(path, self.points, self.cells, vtkio.TETRA, {"x": np.arange(5.0)})
        with open(path) as f:
            text = f.read().replace('NumberOfPoints="5"', 'NumberOfPoints="6"')
        with open(path, "w") as f:
            f.write(text)
        with self.assertRaises(ValueError):
            vtkio.read_vtu(path)

    def test_t18_2_repeat_sector(self):
        radial = self.points * np.array([1.0, 1.0, 0.0])                 # a radial vector at every point
        p, c, pd, cd = vtkio.repeat_sector(self.points, self.cells, {"v": radial, "s": np.arange(5.0)},
                                           {"material": np.array([3, 4])}, 4, 90.0)
        self.assertEqual((len(p), len(c)), (20, 8))
        self.assertAlmostEqual(tet_volumes(p, c).sum(), 4 * tet_volumes(self.points, self.cells).sum())
        np.testing.assert_allclose(pd["v"], p * np.array([1.0, 1.0, 0.0]), atol=1e-12)      # still radial in every copy
        np.testing.assert_allclose(p[5], [0.0, 1.0, 0.0], atol=1e-12)                       # first point turned by 90 degrees
        np.testing.assert_array_equal(pd["s"], np.tile(np.arange(5.0), 4))
        np.testing.assert_array_equal(cd["material"], [3, 4] * 4)
        same = vtkio.repeat_sector(self.points, self.cells, {}, {}, 1, 90.0)
        self.assertIs(same[0], self.points)

    def test_subset(self):
        p, c, pd, cd = vtkio.subset(self.points, self.cells, np.array([False, True]),
                                    {"s": np.arange(5.0)}, {"m": np.array([3, 4])})
        self.assertEqual(len(p), 4)
        np.testing.assert_array_equal(pd["s"], [1, 2, 3, 4])
        np.testing.assert_array_equal(cd["m"], [4])
        np.testing.assert_allclose(p[c[0]], self.points[self.cells[1]])

    def test_t18_5_pvd(self):
        folder = os.path.join(self.tmp.name, "series")
        files = []
        for k in range(3):
            files.append(os.path.join(folder, "machine", f"machine_{k:03d}.vtu"))
            vtkio.write_vtu(files[-1], self.points, self.cells)
        path = os.path.join(folder, "machine.pvd")
        vtkio.write_pvd(path, [(30.0 * k, f) for k, f in enumerate(files)])
        with open(path) as f:
            text = f.read()
        self.assertIn('file="machine/machine_001.vtu"', text)             # relative to the .pvd file
        entries = vtkio.read_pvd(path)
        self.assertEqual([t for t, _ in entries], [0.0, 30.0, 60.0])
        self.assertTrue(all(os.path.isfile(f) for _, f in entries))


class DerivedQuantitiesTest(unittest.TestCase):
    def test_t18_3_permeability_and_saturation(self):
        from emachine.analysis import fieldexport
        from emachine.solvers.elmer import materials
        curve = materials.bh_table(500.0, 1.9)
        mu, saturation = fieldexport.permeability(np.array([0.0, 0.02, 1.0, 1.8, 2.5]), curve, 500.0)
        self.assertAlmostEqual(mu[0] / 500.0, 1.0, delta=0.03)      # first interval of the 0.05 T table
        self.assertAlmostEqual(mu[1] / 500.0, 1.0, delta=0.03)
        self.assertTrue(np.all(np.diff(mu) <= 1e-9))
        self.assertLess(mu[4], 20)
        self.assertTrue(np.all((saturation >= 0) & (saturation <= 1)))
        self.assertTrue(np.all(np.diff(saturation) >= 0))
        self.assertGreater(saturation[4], 0.95)
        mu, saturation = fieldexport.permeability(np.array([0.0, 1.0, 2.5]), None, 500.0)
        np.testing.assert_array_equal(mu, [500.0, 500.0, 500.0])
        np.testing.assert_array_equal(saturation, [0.0, 0.0, 0.0])

    def test_t18_4_harmonics(self):
        from emachine.analysis import fieldexport
        angle = 2 * np.pi * np.arange(24) / 24
        wave = 0.8 + 1.5 * np.cos(2 * angle + 0.4) + 0.3 * np.sin(4 * angle) + 0.05 * np.cos(6 * angle)
        rows = dict(fieldexport.harmonics(wave))
        for order, amplitude in ((0, 0.8), (2, 1.5), (4, 0.3), (6, 0.05), (1, 0.0), (3, 0.0)):
            self.assertAlmostEqual(rows[order], amplitude, places=10)
        np.testing.assert_allclose(fieldexport.slope_full_period(np.cos(angle)), -np.sin(angle), atol=1e-12)
        one = np.sin(angle) ** 2
        np.testing.assert_allclose(fieldexport.machine_torque_full(one, 3), 1.5, atol=1e-12)
        np.testing.assert_allclose(fieldexport.machine_torque_full(one, 1), one)


@slow
class ExportTest(unittest.TestCase):
    POSITIONS = 6

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.spec = load_spec(SPEC)
        cls.values = design.clip(cls.spec, REFERENCE_DESIGN)
        cls.design_file = os.path.join(cls.tmp.name, "design.json")
        with open(cls.design_file, "w") as f:
            json.dump(design.to_parameters(cls.spec, cls.values), f)
        cls.out = os.path.join(cls.tmp.name, "view")
        cls.result = subprocess.run([sys.executable, "-m", "emachine", "export", "--spec", SPEC,
                                     "--design", cls.design_file, "--out", cls.out, "--positions", str(cls.POSITIONS),
                                     "--sectors", "2"], capture_output=True, text=True, cwd=ROOT)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def waveforms(self):
        with open(os.path.join(self.out, "waveforms.csv")) as f:
            return list(csv.DictReader(f))

    def test_t18_6_files(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout[-1500:] + self.result.stderr[-1500:])
        for name in ("machine.pvd", "air.pvd", "airgap.pvd", "core_loss.vtu", "full_ring.vtu", "waveforms.csv",
                     "harmonics.csv", "airgap_profile.csv", "regions.csv", "waveforms.svg", "summary.md",
                     "open_in_paraview.py", "paraview_views.py", "full_motor.vtu"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, name)), name)
        self.assertFalse(os.path.isdir(os.path.join(self.out, "raw")))
        steps = 2 * self.POSITIONS
        sizes = {}
        for name in ("machine", "air", "airgap"):
            entries = vtkio.read_pvd(os.path.join(self.out, name + ".pvd"))
            self.assertEqual(len(entries), steps)
            times = [t for t, _ in entries]
            self.assertEqual(times, sorted(times))
            self.assertAlmostEqual(times[1] - times[0], 360.0 / steps)
            for _, path in entries[::5]:
                data = vtkio.read_vtu(path)                       # raises if counts disagree
                self.assertIn("B", data["point_data"])
                self.assertIn("torque_Nm", data["field_data"])
                sizes[name] = len(data["cells"])
                if name == "machine":
                    self.assertNotIn(1, set(np.unique(data["cell_data"]["material"])))
                    self.assertTrue({2, 3, 4} <= set(np.unique(data["cell_data"]["material"])))
                if name == "air":
                    self.assertEqual(set(np.unique(data["cell_data"]["material"])), {1})
        ring = vtkio.read_vtu(os.path.join(self.out, "full_ring.vtu"))
        machine = vtkio.read_vtu(vtkio.read_pvd(os.path.join(self.out, "machine.pvd"))[0][1])
        # Two sectors in the series, all 18 in the full ring: the volumes scale accordingly.
        ratio = tet_volumes(ring["points"], ring["cells"]).sum() / tet_volumes(machine["points"], machine["cells"]).sum()
        self.assertAlmostEqual(ratio, 18 / 2, delta=0.05)

    def test_t18_7_torque_equals_the_analysis(self):
        from emachine.pipeline import sweep
        spec = load_spec(SPEC)
        with tempfile.TemporaryDirectory() as tmp:
            reference = sweep.field_analysis("tfm.sector3d", "elmer3d")(design.to_parameters(spec, self.values), self.POSITIONS, os.path.join(tmp, "em"),
                                   int(spec["optimizer"]["jobs"]), core_field=False)
        rows = self.waveforms()
        torque = np.array([float(r["phase_torque_Nm"]) for r in rows[:self.POSITIONS]])
        scale = np.max(np.abs(reference["torque_Nm"]))
        np.testing.assert_allclose(torque, reference["torque_Nm"], atol=0.005 * scale)
        # The second half period repeats the first.
        second = np.array([float(r["phase_torque_Nm"]) for r in rows[self.POSITIONS:]])
        np.testing.assert_allclose(second, torque, atol=0.03 * scale)

    def test_t18_8_magnetisation(self):
        data = vtkio.read_vtu(vtkio.read_pvd(os.path.join(self.out, "machine.pvd"))[3][1])
        cd = data["cell_data"]
        magnets = cd["material"] == 3
        m = cd["magnetization"][magnets]
        magnet = self.spec["materials"]["magnet"]
        np.testing.assert_allclose(np.linalg.norm(m, axis=1), magnet["remanence_T"] / (MU0 * magnet["mu_r"]), rtol=1e-3)
        self.assertTrue(np.all(cd["magnetization"][~magnets] == 0))
        # Halbach: in the frame of each magnet the magnetisation is radial or tangential, and all four
        # directions occur. A segment spans 5 degrees, so an element lies within 2.5 degrees of its centre.
        centroid = data["points"][data["cells"][magnets]].mean(axis=1)
        local = np.degrees(np.arctan2(m[:, 1], m[:, 0]) - np.arctan2(centroid[:, 1], centroid[:, 0])) % 360.0
        nearest = np.round(local / 90.0) * 90.0
        self.assertLess(np.max(np.abs(local - nearest)), 2.6)
        self.assertEqual(set((nearest % 360).astype(int)), {0, 90, 180, 270})
        # The coil carries an azimuthal current density equal to ampere-turns / coil area.
        coil = cd["material"] == 2
        step = self.waveforms()[3]
        d = design.derived(self.spec, self.values)
        with open(os.path.join(self.out, "summary.json")) as f:
            turns = json.load(f)["turns"]
        expected = abs(float(step["phase_current_A"])) * turns / d["coil_area_mm2"]
        np.testing.assert_allclose(np.linalg.norm(cd["current_density"][coil], axis=1), expected, rtol=1e-3)
        self.assertLess(np.max(np.abs(cd["current_density"][coil][:, 2])), 1e-9)

    def test_t18_9_airgap_and_core_loss(self):
        gap = vtkio.read_vtu(vtkio.read_pvd(os.path.join(self.out, "airgap.pvd"))[0][1])
        self.assertEqual(gap["cell_type"], vtkio.QUAD)
        radial = gap["point_data"]["B_radial"]
        self.assertLess(abs(radial.mean()), 0.02 * np.abs(radial).max())
        self.assertGreater(np.abs(radial).max(), 0.5)
        np.testing.assert_allclose(np.hypot(gap["points"][:, 0], gap["points"][:, 1]),
                                   design.derived(self.spec, self.values)["stator_radius"] + 0.25, atol=1e-3)
        core = vtkio.read_vtu(os.path.join(self.out, "core_loss.vtu"))
        volume = tet_volumes(core["points"], core["cells"]) * 1e-9
        total = 18 * np.sum(volume * core["cell_data"]["loss_density_W_per_m3"])
        self.assertAlmostEqual(total / core["field_data"]["iron_loss_W_per_phase"], 1.0, delta=0.01)
        self.assertLess(core["cell_data"]["B_peak"].max(), 2.6)
        # Saturating core: the permeability varies and stays at or below the initial value.
        machine = vtkio.read_vtu(vtkio.read_pvd(os.path.join(self.out, "machine.pvd"))[0][1])
        mu = machine["cell_data"]["mu_r"][machine["cell_data"]["material"] == 4]
        self.assertLessEqual(mu.max(), 500.0 * 1.02)
        self.assertLess(mu.min(), 250.0)

    def test_t18_10_linear_material(self):
        with open(SPEC) as f:
            user = json.load(f)
        user["materials"] = {"stator_core": {"saturation_T": None}, "rotor_iron": {"saturation_T": None}}
        spec_file = os.path.join(self.tmp.name, "linear.json")
        with open(spec_file, "w") as f:
            json.dump(user, f)
        out = os.path.join(self.tmp.name, "linear_view")
        result = subprocess.run([sys.executable, "-m", "emachine", "export", "--spec", spec_file,
                                 "--design", self.design_file, "--out", out, "--positions", "3", "--skip-no-load",
                                 "--skip-air"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-1500:])
        self.assertFalse(os.path.isfile(os.path.join(out, "air.pvd")))
        machine = vtkio.read_vtu(vtkio.read_pvd(os.path.join(out, "machine.pvd"))[1][1])
        cd = machine["cell_data"]
        np.testing.assert_array_equal(cd["mu_r"][cd["material"] == 4], 500.0)
        np.testing.assert_array_equal(cd["saturation"], 0.0)
        with open(os.path.join(out, "waveforms.csv")) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["cogging_torque_Nm"], "")


if __name__ == "__main__":
    unittest.main()
