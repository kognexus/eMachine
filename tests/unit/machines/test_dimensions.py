"""T49, T50: machines described by lengths and arcs (docs/parameters.md); old designs converted."""

import json
import math
import os
import tempfile
import unittest

from helpers import ROOT, slow

from emachine.pipeline import design_space
from emachine.spec import SpecError, load_spec
from emachine.spec.names import standard_values

SPEC = os.path.join(ROOT, "examples", "rfm_spm_12s10p.json")
DESIGN = os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")
#: the reference design as written before T49
OLD_REFERENCE = {"pole_pairs": 5, "bore_ratio": 0.6, "tooth_ratio": 0.55, "slot_depth_ratio": 0.6, "yoke_mm": 6.0,
                 "magnet_thickness_mm": 3.0, "magnet_arc_ratio": 0.85, "current_density_A_mm2": 4.0}


def reference():
    spec = load_spec(SPEC)
    with open(DESIGN) as f:
        return spec, json.load(f)


def failed(spec, values):
    return {c.name for c in design_space.checks(spec, values) if c.violation > 0}


def rfm(**machine):
    return load_spec({"machine": dict({"flux_path": "rfm", "principle": "pmsm", "phases": 3, "outer_diameter_mm": 100.0,
                                       "stack_length_mm": 40.0, "bore_diameter_mm": 20.0, "air_gap_mm": 0.7}, **machine)})


class SlottedStatorTest(unittest.TestCase):
    def test_t49_1_reference_dimensions(self):
        spec, values = reference()
        d = design_space.derived(spec, values)
        self.assertAlmostEqual(d["bore_radius"], 30.0)
        self.assertAlmostEqual(d["back_radius"], 50.0)            # the stator fills the outer diameter
        self.assertAlmostEqual(d["slot_depth"], 12.0)
        self.assertAlmostEqual(d["slot_width"], 7.07)
        self.assertAlmostEqual(d["tooth_width"], 2 * math.pi * 30 / 12 - 7.07)
        self.assertEqual(failed(spec, values), set())

    def test_t49_slot_area_is_the_drawn_slot(self):
        """Parallel-sided slot: width x height plus the thin circle segment at the bore (under 1 %)."""
        spec, values = reference()
        d = design_space.derived(spec, values)
        self.assertAlmostEqual(d["slot_area_mm2"] / (7.07 * 12.0), 1.0, delta=0.01)
        self.assertGreater(d["slot_area_mm2"], 7.07 * 12.0)
        self.assertAlmostEqual(d["coil_area_mm2"], d["slot_area_mm2"] / 2)       # double layer

    def test_t49_3_old_design_converts_to_the_same_stator(self):
        spec, _ = reference()
        new = standard_values(spec, OLD_REFERENCE)
        self.assertNotIn("bore_ratio", new)
        self.assertAlmostEqual(new["slot_height_mm"], 12.0)
        self.assertAlmostEqual(new["slot_width_mm"], 2 * math.pi * 30 / 12 * 0.45)
        self.assertAlmostEqual(new["yoke_height_mm"], 8.0)
        self.assertAlmostEqual(new["magnet_arc_el_deg"], 153.0)
        d = design_space.derived(spec, OLD_REFERENCE)                # read directly, too
        self.assertAlmostEqual(d["bore_radius"], 30.0)
        self.assertAlmostEqual(d["tooth_width"], 0.55 * 2 * math.pi * 30 / 12)

    def test_t49_4_old_ratio_bounds_name_the_new_variables(self):
        with self.assertRaises(SpecError) as raised:
            load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm"}, "variables": {"bore_ratio": [0.5, 0.7]}})
        self.assertIn("slot_height_mm", str(raised.exception))
        # a run's spec that fixed all three ratios still loads: the same stator in lengths
        spec = load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "outer_diameter_mm": 100.0},
                          "variables": {"bore_ratio": 0.6, "tooth_ratio": 0.55, "slot_depth_ratio": 0.6, "yoke_mm": 6.0}})
        self.assertAlmostEqual(spec["variables"]["slot_height_mm"], 12.0)
        self.assertAlmostEqual(spec["variables"]["yoke_height_mm"], 8.0)

    def test_t49_5_wide_slots_leave_no_tooth(self):
        spec, values = reference()
        self.assertIn("tooth_width", failed(spec, dict(values, slot_width_mm=14.5)))
        self.assertIn("rotor_radius", failed(spec, dict(values, slot_height_mm=28.0, yoke_height_mm=10.0)))

    def test_t49_bounds_follow_the_envelope(self):
        spec = rfm()
        var = {v["name"]: v for v in design_space.variables(spec)}
        self.assertEqual(var["slot_height_mm"]["high"], 20.0)        # half the room between shaft and outer diameter
        self.assertAlmostEqual(var["slot_width_mm"]["high"], math.pi * 100 / 24)
        self.assertEqual(var["slot_width_mm"]["low"], spec["limits"]["min_slot_width_mm"])


class RotorArcTest(unittest.TestCase):
    def test_t50_1_tfm_tooth_arc_is_tooth_span_in_degrees(self):
        from emachine.machines.tfm import design
        spec = load_spec(os.path.join(ROOT, "examples", "three_phase_ui.json"))
        middle = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
        old = {k: v for k, v in middle.items() if k != "tooth_arc_el_deg"}
        old["tooth_span"] = middle["tooth_arc_el_deg"] / 180.0
        self.assertEqual(design.to_parameters(spec, old), design.to_parameters(spec, middle))
        self.assertAlmostEqual(design.to_parameters(spec, middle)["stator"]["tooth_span"], 0.725)

    def test_t50_3_claw_tip_of_older_designs(self):
        from emachine.machines.tfm import design
        spec = load_spec(os.path.join(ROOT, "examples", "three_phase_cp.json"))
        middle = {v["name"]: (v["low"] + v["high"]) / 2 for v in design.variables(spec)}
        old = {k: v for k, v in middle.items() if k != "claw_tip_height_mm"}
        for root, tip in ((6.0, 3.0), (3.0, 2.0)):            # 0.5 x root, not below the minimum iron (2 mm)
            d = design.derived(spec, dict(old, claw_root_height_mm=root))
            self.assertEqual(d["claw_tip_height"], tip)
        self.assertEqual(design.derived(spec, dict(middle, claw_tip_height_mm=4.5))["claw_tip_height"], 4.5)

    def test_t50_4_srm_pole_arcs(self):
        """8/6 SRM (4 phases): stroke 15 deg, rotor pole pitch 60 deg."""
        spec = load_spec({"machine": {"flux_path": "rfm", "principle": "srm", "phases": 4, "slots": 8, "rotor_poles": 6,
                                      "outer_diameter_mm": 120.0, "bore_diameter_mm": 20.0}})
        base = {"slot_height_mm": 15.0, "yoke_height_mm": 8.0, "current_density_A_mm2": 4.0, "rotor_pole_height_mm": 6.0}
        r_bore = 60 - 15 - 8

        def slot_for(beta_s):            # parallel-sided slot that leaves a stator pole of beta_s at the bore
            return 2 * r_bore * math.sin(math.radians((45 - beta_s) / 2))

        def arcs(beta_s, beta_r):
            return failed(spec, dict(base, slot_width_mm=slot_for(beta_s), rotor_pole_arc_deg=beta_r)) & {
                "stator_pole_arc", "rotor_pole_arc", "pole_arcs"}
        self.assertEqual(arcs(20, 22), set())
        self.assertEqual(arcs(14, 16), {"stator_pole_arc"})
        self.assertEqual(arcs(16, 14), {"rotor_pole_arc"})
        self.assertEqual(arcs(30, 32), {"pole_arcs"})

    def test_t50_5_barriers_keep_iron_between_them(self):
        spec = rfm(principle="synrm", rotor="flux_barrier", barriers=3)
        values = {"pole_pairs": 2, "slot_height_mm": 12.0, "slot_width_mm": 6.0, "yoke_height_mm": 8.0,
                  "current_density_A_mm2": 4.0, "rib_mm": 0.8}
        self.assertNotIn("barrier_iron", failed(spec, dict(values, barrier_width_mm=2.0)))
        self.assertIn("barrier_iron", failed(spec, dict(values, barrier_width_mm=6.0)))

    def test_t50_interior_v_within_the_pole(self):
        spec = rfm(rotor="interior")
        values = {"pole_pairs": 4, "slot_height_mm": 12.0, "slot_width_mm": 6.0, "yoke_height_mm": 8.0,
                  "current_density_A_mm2": 4.0, "magnet_thickness_mm": 3.0, "v_angle_deg": 140.0, "bridge_mm": 1.0}
        self.assertEqual(failed(spec, dict(values, magnet_length_mm=8.0)) & {"magnet_width", "rotor_core"}, set())
        self.assertIn("magnet_width", failed(spec, dict(values, magnet_length_mm=20.0)))

    def test_t50_dropped_ratios_name_the_new_variable(self):
        spec = rfm(rotor="interior")
        with self.assertRaises(SpecError) as raised:
            standard_values(spec, {"magnet_width_ratio": 0.6})
        self.assertIn("magnet_length_mm", str(raised.exception))


class AxialFluxTest(unittest.TestCase):
    DESIGN = {"pole_pairs": 10, "inner_diameter_mm": 120.0, "slot_height_mm": 15.0, "slot_width_mm": 8.0,
              "yoke_height_mm": 6.0, "magnet_thickness_mm": 4.0, "magnet_arc_el_deg": 150.0, "current_density_A_mm2": 4.0}

    @staticmethod
    def spec(arrangement, length, principle="pmsm"):
        return load_spec({"machine": {"flux_path": "afm", "principle": principle, "arrangement": arrangement,
                                      "outer_diameter_mm": 200.0, "stack_length_mm": length, "air_gap_mm": 1.0,
                                      "slots": 24, "phases": 3}})

    def test_t51_1_double_rotor(self):
        d = design_space.derived(self.spec("double_rotor", 40.0), self.DESIGN)
        self.assertEqual(d["stator_length"], 36.0)                    # two slotted faces and one yoke
        self.assertEqual(d["rotor_back_iron"], -3.0)                  # (40 - 36 - 2 x (1 + 4)) / 2
        self.assertIn("rotor_back_iron", failed(self.spec("double_rotor", 40.0), self.DESIGN))
        self.assertEqual(design_space.derived(self.spec("double_rotor", 50.0), self.DESIGN)["rotor_back_iron"], 2.0)
        self.assertEqual(failed(self.spec("double_rotor", 50.0), self.DESIGN), set())

    def test_t51_2_single_and_double_stator(self):
        d = design_space.derived(self.spec("single", 50.0), self.DESIGN)
        self.assertEqual((d["stator_length"], d["rotor_back_iron"]), (21.0, 24.0))
        d = design_space.derived(self.spec("double_stator", 50.0), self.DESIGN)
        self.assertEqual(d["rotor_back_iron"], 50.0 - 2 * 21.0 - 2 * 5.0)       # -2: infeasible
        self.assertIn("rotor_back_iron", failed(self.spec("double_stator", 50.0), self.DESIGN))
        self.assertNotIn("rotor_back_iron", failed(self.spec("double_stator", 52.0), self.DESIGN))  # coreless rotor allowed

    def test_t51_3_tooth_slot_and_winding(self):
        spec = self.spec("double_rotor", 50.0)
        d = design_space.derived(spec, self.DESIGN)
        self.assertAlmostEqual(d["tooth_width"], 2 * math.pi * 60 / 24 - 8.0)
        self.assertEqual(d["slot_area_mm2"], 120.0)
        self.assertEqual(d["stack_length"], 40.0)                      # radial active length
        self.assertEqual(d["coils_per_phase"], 2 * 8)                   # two slotted faces
        self.assertIn("tooth_width", failed(spec, dict(self.DESIGN, inner_diameter_mm=70.0, slot_width_mm=8.0)))
        self.assertIn("inner_diameter", failed(spec, dict(self.DESIGN, inner_diameter_mm=10.0)))

    def test_t51_srm_pole_arcs_at_the_mean_radius(self):
        spec = self.spec("double_rotor", 50.0, "srm")
        values = {k: v for k, v in self.DESIGN.items() if not k.startswith("magnet") and k != "pole_pairs"}
        values.update(rotor_pole_height_mm=4.0, rotor_pole_arc_deg=20.0)
        checks = {c.name: c for c in design_space.checks(spec, values)}
        self.assertIn("pole_arcs", checks)
        self.assertEqual(design_space.derived(spec, values)["rotor_back_iron"], 2.0)   # poles take the magnets' room


@slow
class DrawnSlotTest(unittest.TestCase):
    def test_t49_2_slot_area_against_the_mesh(self):
        from emachine.core import registry
        spec, values = reference()
        cases = [(spec, values), (rfm(slots=24, rotor="surface"),
                                  {"pole_pairs": 2, "slot_height_mm": 14.0, "slot_width_mm": 4.5, "yoke_height_mm": 9.0,
                                   "current_density_A_mm2": 4.0, "magnet_thickness_mm": 3.0, "magnet_arc_el_deg": 150.0})]
        for spec, values in cases:
            with self.subTest(slots=spec["machine"]["slots"]):
                d = design_space.derived(spec, values)
                request = design_space.geometry(spec, values)
                with tempfile.TemporaryDirectory() as tmp:
                    regions = registry.create("geometry", "rfm.section2d").build(request, 7.0, tmp).regions
                meshed = sum(r["area_mm2"] for n, r in regions.items() if n.startswith("coil_"))
                self.assertAlmostEqual(meshed / (d["slots"] * d["slot_area_mm2"]), 1.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
