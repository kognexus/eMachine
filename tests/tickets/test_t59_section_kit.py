"""T59: 2D section kit for radial machines (and T60: axial slices): geometry, regions, multi-gap torque."""

import json
import math
import os
import random
import tempfile
import unittest

from helpers import ROOT, slow

from emachine.machines.catalogue import TOPOLOGIES, GeometryError

ENV = {"outer_diameter_mm": 85.0, "bore_diameter_mm": 52.0, "stack_length_mm": 30.0, "ferrite_remanence_T": 0.42,
       "fidelity": {"gap_cell_factor": 0.8, "size_max_mm": 3.0}}


def feasible(key, seed=3, tries=3000):
    rng = random.Random(seed)
    topo = TOPOLOGIES[key]()
    for _ in range(tries):
        values = {v.name: (rng.randint(int(v.low), int(v.high)) if v.kind == "int" else rng.uniform(v.low, v.high))
                  for v in topo.variables(ENV)}
        try:
            return topo.design(ENV, values)
        except GeometryError:
            continue
    raise AssertionError(f"no drawable design of {key}")


class CatalogueTest(unittest.TestCase):
    def test_t59_every_topology_has_drawable_designs(self):
        for key in TOPOLOGIES:
            d = feasible(key)
            self.assertIn(d["principle"], ("pm", "synrm", "pmasynrm", "srm", "vernier"))
            self.assertGreater(d["side_area_mm2"], 0)
            self.assertGreater(d["coils_per_phase"], 0)

    def test_t59_air_gap_range(self):
        for key in TOPOLOGIES:
            gap = [v for v in TOPOLOGIES[key]().variables(ENV) if v.name == "air_gap_mm"][0]
            self.assertEqual((gap.low, gap.high), (0.3, 1.0))


class MeshTest(unittest.TestCase):
    def test_t59_1_surface_pm_regions(self):
        from emachine.machines.section2d.mesher import mesh_part
        d = feasible("rfm_spm_in")
        with tempfile.TemporaryDirectory() as tmp:
            meta = mesh_part(dict(d["params"], rotor_angle_deg=0.0), {"kind": "radial"}, os.path.join(tmp, "s.msh"))
        rotor = d["params"]["parts"][0]
        poles = rotor["poles"]
        r1, r0 = rotor["r_out"], rotor["r_out"] - rotor["magnet_thickness"]
        expected = math.pi * (r1 ** 2 - r0 ** 2) * rotor["magnet_arc"] / poles
        for name, region in meta["regions"].items():
            if region["kind"] == "magnet":
                self.assertAlmostEqual(region["area_mm2"], expected, delta=0.02 * expected)
        self.assertEqual(len(meta["geometry"]["gaps"]), 1)

    def test_t60_1_axial_slice_periodic(self):
        from emachine.machines.section2d.mesher import mesh_part
        d = feasible("afm_yasa")
        with tempfile.TemporaryDirectory() as tmp:
            meta = mesh_part(dict(d["params"], rotor_angle_deg=1.234), {"kind": "axial", "slice": 0}, os.path.join(tmp, "s.msh"))
        self.assertEqual(meta["boundaries"]["right"]["periodic"], "left")
        self.assertEqual(len(meta["geometry"]["gaps"]), 2)
        self.assertEqual(sorted(g["rotor"] for g in meta["geometry"]["gaps"]), ["above", "below"])

    @slow
    def test_t59_2_same_torque_as_t41(self):
        """The T41 machine (parallel slots) drawn by the kit: torque within 2 % of the T41 mesher."""
        import emachine.plugins  # noqa: F401
        from emachine.core import registry
        from emachine.core.types import Excitation, GeometryRequest
        from emachine.pipeline import design_space as ds
        from emachine.spec.loader import load_spec
        spec = load_spec(os.path.join(ROOT, "examples", "rfm_spm_12s10p.json"))
        with open(os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")) as f:
            values = json.load(f)
        values = values.get("values", values)
        P = ds.geometry(spec, values).parameters
        p = P["rfm"]
        kit = {"stack_length": p["stack_length"], "bore_radius": p["shaft_radius"], "electrical_pole_pairs": 5,
               "rotor_eddy_width_mm": [1, 1, 1], "mesh": {"gap_cell": P["mesh"]["gap_cell"], "size_max": P["mesh"]["size_max"]},
               "parts": [{"role": "rotor", "type": "surface", "r_in": p["shaft_radius"], "r_out": p["bore_radius"] - p["air_gap"],
                          "facing": "out", "poles": 10, "offset_deg": p["rotor_offset_deg"], "magnet_thickness": p["magnet_thickness"],
                          "magnet_arc": p["magnet_arc_ratio"]},
                         {"role": "stator", "type": "slotted", "r_in": p["bore_radius"], "r_out": p["outer_radius"], "facing": "in",
                          "slots": 12, "slot_depth": p["slot_depth"], "slot_width": p["slot_width"], "tip_height": 0, "opening": 0,
                          "sides": p["sides"]}]}
        an = dict(P["analysis"], keep_fields=False)
        peak = an["coil_current_A"]
        th = 0.0
        ni = tuple(-peak * math.sin(th - 2 * math.pi * j / 3) for j in range(3))
        with tempfile.TemporaryDirectory() as tmp:
            old = registry.create("solver", "elmer2d", settings=an).solve(
                registry.create("geometry", "rfm.section2d").build(GeometryRequest("rfm.section2d", P), 0.0, tmp + "/a"),
                Excitation(rotor_angle_deg=0.0, ampere_turns=ni), tmp + "/a")
            new = registry.create("solver", "elmer_sections", settings=an).solve(
                registry.create("geometry", "section2d").build(GeometryRequest("section2d", kit), 0.0, tmp + "/b"),
                Excitation(rotor_angle_deg=0.0, ampere_turns=ni), tmp + "/b")
        self.assertAlmostEqual(new.torque_Nm, old.torque_Nm, delta=0.02 * abs(old.torque_Nm))
        for a, b in zip(new.flux_linkage_Wb, old.flux_linkage_Wb):
            self.assertAlmostEqual(a, b, delta=0.02 * max(abs(x) for x in old.flux_linkage_Wb))


if __name__ == "__main__":
    unittest.main()
