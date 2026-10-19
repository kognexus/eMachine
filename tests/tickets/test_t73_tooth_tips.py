"""T73: tooth tips on the toothed ring that reach axially over the coil slot."""

import math
import unittest

from helpers import slow

from emachine.machines.tfm import checks, design
from emachine.spec import SpecError

from tickets.test_t71_rotor_magnet_slots import USER_DESIGN, spec_with

TIPS = dict(USER_DESIGN, ring_tip_overhang_mm=3.5, ring_tip_height_mm=1.5)


def tip_area(radius, half, height):
    """Cross-section of one tip: inside the air-gap circle, above radius - height, |y| <= half (inner stator)."""
    def primitive(y):
        return 0.5 * y * math.sqrt(radius * radius - y * y) + 0.5 * radius * radius * math.asin(y / radius)
    return primitive(half) - primitive(-half) - 2 * half * (radius - height)


def stator_volume(stator):
    import gmsh
    from emachine.machines.tfm.geometry.parameters import DEFAULTS
    from emachine.machines.tfm.geometry.shapes import occ
    from emachine.machines.tfm.geometry.stators import build_stator
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        parts, names, _ = build_stator(dict(DEFAULTS["stator"], **stator))
        occ.synchronize()
        core = [tag for (_, tag), name in zip(parts, names) if name == "tfm_core"]
        r = stator["air_gap_radius"] - 0.5 * stator["ring_tip_height"] if stator.get("ring_tip_height") else 0.0
        probe = None
        if r:
            # middle of the front tip over the slot, at angle 0; and just off the back wall there, beyond the
            # end of the front tip, where a back tip would be (none: the back wall has its valley at angle 0)
            front = [r, 0.0, -stator["slot_width"] / 2 + 0.5 * stator["ring_tip_overhang"]]
            back = [r, 0.0, stator["slot_width"] / 2 - 0.25]
            probe = (any(gmsh.model.isInside(3, t, front) for t in core),
                     any(gmsh.model.isInside(3, t, back) for t in core))
        return sum(occ.getMass(3, t) for t in core), len(core), probe
    finally:
        gmsh.finalize()


class DesignTest(unittest.TestCase):
    def test_t73_1_variables_and_coil(self):
        plain = spec_with()
        tips = spec_with(ring_tooth_tips=True)
        names = [v["name"] for v in design.variables(tips)]
        self.assertIn("ring_tip_overhang_mm", names)
        self.assertIn("ring_tip_height_mm", names)
        d0, d1 = design.derived(plain, USER_DESIGN), design.derived(tips, TIPS)
        self.assertAlmostEqual(d0["coil_height"] - d1["coil_height"], 1.5)
        self.assertAlmostEqual(d1["pole_face_area_mm2"] / d0["pole_face_area_mm2"], (2.0 + 3.5) / 2.0)
        params = design.to_parameters(tips, TIPS)
        self.assertEqual((params["stator"]["ring_tip_overhang"], params["stator"]["ring_tip_height"]), (3.5, 1.5))
        back = design.from_parameters(tips, params)
        self.assertEqual((back["ring_tip_overhang_mm"], back["ring_tip_height_mm"]), (3.5, 1.5))

    def test_t73_2_checks(self):
        tips = spec_with(ring_tooth_tips=True)
        ok = {c.name: c for c in checks.check(tips, TIPS)}
        self.assertEqual(ok["tip_overhang"].violation, 0.0)
        self.assertEqual(ok["tip_height"].violation, 0.0)
        # A tip reaching the opposite wall, and a tip as thick as the tooth is high.
        bad = {c.name: c for c in checks.check(tips, dict(TIPS, ring_tip_overhang_mm=4.9, ring_tip_height_mm=8.0))}
        self.assertGreater(bad["tip_overhang"].violation, 0.0)
        self.assertGreater(bad["tip_height"].violation, 0.0)
        # Tips of the two walls interleave one pole pitch apart: very wide teeth collide.
        wide = {c.name: c for c in checks.check(tips, dict(TIPS, tooth_arc_el_deg=171.0))}
        self.assertGreater(wide["tip_gap"].violation, 0.0)

    def test_t73_3_option_only_for_the_toothed_ring(self):
        with self.assertRaises(SpecError):
            spec_with(ring_tooth_tips=True, stator="ui_core", ring_staggered_teeth=False, ring_arched_valleys=False)


@slow
class GeometryTest(unittest.TestCase):
    def test_t73_4_tip_volume_and_position(self):
        spec = spec_with(ring_tooth_tips=True)
        with_tips = design.to_parameters(spec, TIPS)["stator"]
        without = dict(with_tips, ring_tip_overhang=0.0, ring_tip_height=0.0)
        v1, n1, probe = stator_volume(with_tips)
        v0, n0, _ = stator_volume(without)
        self.assertEqual((n0, n1), (1, 1))
        p = with_tips["pole_pairs"]
        half = 0.5 * with_tips["tooth_span"] * math.pi * with_tips["air_gap_radius"] / p
        expected = 2 * p * with_tips["ring_tip_overhang"] * tip_area(with_tips["air_gap_radius"], half,
                                                                     with_tips["ring_tip_height"])
        self.assertAlmostEqual((v1 - v0) / expected, 1.0, delta=1e-3)
        self.assertEqual(probe, (True, False))     # front tip at angle 0; the back wall has its valley there


if __name__ == "__main__":
    unittest.main()
