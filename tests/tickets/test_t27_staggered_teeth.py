"""T27: staggered teeth on the toothed ring (back wall one pole pitch after the front wall)."""

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest

from helpers import FEATURESCRIPT, ROOT, slow

from emachine.machines.tfm.cad import sheet as onshape

MESHER = ["-m", "emachine", "mesh"]

#: The user's machine of 2026-10-15 (Onshape dialogs), one phase.
STATOR = {"core_type": "tr", "air_gap_radius": 35.0, "pole_pairs": 24, "inner_stator": True, "trim_pole_faces": True,
          "tooth_span": 0.8, "leg_width": 2.0, "slot_width": 5.0, "slot_height": 10.0, "yoke_height": 5.0,
          "ring_tooth_height": 8.0, "ring_arched_valleys": True, "ring_staggered_teeth": True, "include_coil": True,
          "coil_height": 8.0, "coil_clearance": 1.0, "pole_shift_deg": 0.0}
ROTOR = {"configuration": "outrunner", "type": "halbach", "inner_diameter": 70.6, "outer_diameter": 80.0,
         "stack_length": 9.0, "poles": 48, "magnet_thickness": 2.0, "segments_per_pole": 2, "magnet_rows": 1,
         "row_gap": 0.0, "alternate_rows": False}


def build(stator):
    """Core volume and a probe for iron in both walls at angle 0 and at one pole pitch."""
    import gmsh
    from emachine.machines.tfm.geometry import sector as mesher
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        parts, names, _ = mesher.build_stator(dict(mesher.DEFAULTS["stator"], **stator))
        mesher.occ.synchronize()
        core = [tag for (_, tag), name in zip(parts, names) if name == "tfm_core"]
        volume = sum(mesher.occ.getMass(3, tag) for tag in core)
        sign = -1 if stator["inner_stator"] else 1
        r = stator["air_gap_radius"] + sign * 2.0
        pitch = math.pi / stator["pole_pairs"]
        middle = stator["slot_width"] / 2 + stator["leg_width"] / 2
        probe = {}
        for wall, z in (("front", -middle), ("back", middle)):
            for k in (0, 1):
                point = [r * math.cos(k * pitch), r * math.sin(k * pitch), z]
                probe[(wall, k)] = any(gmsh.model.isInside(3, tag, point) for tag in core)
        return volume, probe
    finally:
        gmsh.finalize()


class SourceTest(unittest.TestCase):
    def test_t27_5_featurescript_and_sheet(self):
        with open(os.path.join(FEATURESCRIPT, "tfm_stator.fs")) as f:
            source = f.read()
        self.assertIn('annotation { "Name" : "Staggered teeth (back wall one pole pitch later)", "Default" : false }', source)
        self.assertIn('"staggeredTeeth" : false', source)
        self.assertIn("staggered ? odds : evens", source)
        rows = {r["field"]: r for r in onshape.stator_rows(STATOR)}
        self.assertEqual(rows["Staggered teeth (back wall one pole pitch later)"]["text"], "on")


@slow
class MesherTest(unittest.TestCase):
    def test_t27_1_2_volume_and_tooth_positions(self):
        sys.path.insert(0, ROOT)
        for inner in (True, False):
            for arched in (False, True):
                with self.subTest(inner_stator=inner, arched=arched):
                    aligned, a_probe = build(dict(STATOR, inner_stator=inner, ring_arched_valleys=arched,
                                                  ring_staggered_teeth=False))
                    staggered, s_probe = build(dict(STATOR, inner_stator=inner, ring_arched_valleys=arched))
                    self.assertAlmostEqual(staggered / aligned, 1.0, delta=1e-4)
                    self.assertEqual(a_probe, {("front", 0): True, ("front", 1): False,
                                               ("back", 0): True, ("back", 1): False})
                    self.assertEqual(s_probe, {("front", 0): True, ("front", 1): False,
                                               ("back", 0): False, ("back", 1): True})

    def test_t27_3_sector_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "machine.json")
            with open(path, "w") as f:
                json.dump({"stator": STATOR, "rotor": ROTOR}, f)
            mesh = os.path.join(tmp, "sector.msh")
            result = subprocess.run([sys.executable, *MESHER, "--params", path, "--out", mesh],
                                    capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout[-800:] + result.stderr[-800:])
            self.assertNotIn("flux through the coil cancels", result.stderr)
            check = subprocess.run([sys.executable, "-m", "emachine", "check-mesh", mesh],
                                   capture_output=True, text=True, cwd=ROOT)
            self.assertIn("node ids shared between the two sides: 0 ", check.stdout)
            for a, b, hits in re.findall(r"A (\d+) nodes, B (\d+) nodes, matched after rotation (\d+)", check.stdout):
                self.assertTrue(a == b == hits)


@slow
class FieldTest(unittest.TestCase):
    def test_t27_4_no_load_flux(self):
        sys.path.insert(0, ROOT)
        from emachine.pipeline import sweep
        from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS
        analysis = dict(ANALYSIS_DEFAULTS, coil_turns=1)
        pitch = 180.0 / STATOR["pole_pairs"]
        with tempfile.TemporaryDirectory() as tmp:
            fluxes = [sweep.solve_position({"stator": STATOR, "rotor": ROTOR}, analysis, angle,
                                                  os.path.join(tmp, f"p{k}"), current=0.0)["flux_linkage_Wb"]
                      for k, angle in enumerate((0.0, pitch))]
        self.assertLess(fluxes[0] * fluxes[1], 0.0, fluxes)
        self.assertGreater(min(abs(f) for f in fluxes), 20e-6, fluxes)


if __name__ == "__main__":
    unittest.main()
