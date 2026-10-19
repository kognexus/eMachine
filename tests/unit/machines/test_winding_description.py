"""T46: the winding description: span, layers, pitch, slot class; FSCW, FSDW, ISDW."""

import json
import os
import tempfile
import unittest

from helpers import ROOT, slow

from emachine.machines import winding_layout as wl
from emachine.pipeline import design_space
from emachine.spec import SpecError, load_spec

SPEC = os.path.join(ROOT, "examples", "rfm_spm_12s10p.json")
DESIGN = os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")


def reference_spec(**winding):
    with open(SPEC) as f:
        user = json.load(f)
    return load_spec(dict(user, winding=dict(user["winding"], **winding)))


def described(slots, pole_pairs, span, layers=2, pitch=None):
    layout = wl.layout(slots, pole_pairs, 3, span, layers, pitch)
    return layout, wl.describe(span, layout, slots, pole_pairs, 3, layers)


def balanced(layout):
    axes = sorted((wl.phase_axis_deg(layout, k) - wl.phase_axis_deg(layout, 0)) % 360 for k in (1, 2))
    counts = {sum(1 for c in layout.coils if c.phase == k) for k in range(3)}
    return len(counts) == 1 and abs(axes[0] - 120) < 1e-6 and abs(axes[1] - 240) < 1e-6


class FactorTest(unittest.TestCase):
    def test_t46_1_fscw_12s10p(self):
        _, d = described(12, 5, "concentrated")
        self.assertEqual((d["label"], d["q_text"], d["layers"]), ("FSCW", "2/5", 2))
        self.assertAlmostEqual(d["k_w1"], 0.933, delta=0.001)

    def test_t46_2_isdw_36s6p_full_pitch(self):
        _, d = described(36, 3, "distributed")
        self.assertEqual((d["label"], d["q"], d["pitch_slots"]), ("ISDW", 2.0, 6))
        self.assertAlmostEqual(d["k_d1"], 0.966, delta=0.001)
        self.assertAlmostEqual(d["k_p1"], 1.0, delta=0.001)
        self.assertAlmostEqual(d["k_w1"], 0.966, delta=0.001)

    def test_t46_3_short_pitch_five_sixths(self):
        layout, d = described(36, 3, "distributed", pitch=5)
        self.assertAlmostEqual(d["k_p1"], 0.966, delta=0.001)
        self.assertAlmostEqual(d["k_w1"], 0.933, delta=0.001)
        self.assertTrue(balanced(layout))

    def test_t46_4_fsdw_18s4p(self):
        _, d = described(18, 2, "distributed")
        self.assertEqual((d["label"], d["q"], d["pitch_slots"]), ("FSDW", 1.5, 4))
        self.assertAlmostEqual(d["k_d1"], 0.960, delta=0.001)
        self.assertAlmostEqual(d["k_p1"], 0.985, delta=0.001)
        self.assertAlmostEqual(d["k_w1"], 0.945, delta=0.001)

    def test_t46_5_single_layer(self):
        for slots, p, span, pitch, k_w1 in ((12, 5, "concentrated", None, 0.966), (24, 2, "distributed", None, 0.966),
                                            (36, 3, "distributed", 5, 0.966)):
            with self.subTest(slots=slots, poles=2 * p, pitch=pitch):
                layout, d = described(slots, p, span, 1, pitch)
                self.assertAlmostEqual(d["k_w1"], k_w1, delta=0.001)
                self.assertTrue(balanced(layout))
                sides = layout.sides()
                self.assertEqual(sorted({s[0] for s in sides}), list(range(slots)))
                for slot in range(slots):              # one coil side per slot, in both halves with share 0.5
                    in_slot = [s for s in sides if s[0] == slot]
                    self.assertEqual(sorted(s[1] for s in in_slot), [0, 1])
                    self.assertEqual({(s[2], s[3], s[4]) for s in in_slot}.__len__(), 1)
                    self.assertEqual(in_slot[0][4], 0.5)
        with self.assertRaises(ValueError):
            wl.layout(12, 5, 3, "concentrated", 3)


class SpecTest(unittest.TestCase):
    def test_t46_6_slot_class(self):
        def violated(slot_class, pole_pairs):
            spec = load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "phases": 3, "slots": 12,
                                          "rotor_placement": "inner"},
                              "winding": {"slot_class": slot_class}, "limits": {"pole_pairs": [1, 8]}})
            values = design_space.clip(spec, {v["name"]: (v["low"] + v["high"]) / 2 for v in design_space.variables(spec)})
            values["pole_pairs"] = pole_pairs
            machine = design_space.machine_of(spec)
            return {c.name for c in machine.checks(spec, values) if c.violation > 0} & {"slot_class", "balanced_winding"}

        integral = [p for p in range(2, 8) if not violated("integral", p)]
        fractional = [p for p in range(2, 8) if not violated("fractional", p)]
        self.assertEqual(integral, [2])                         # q = 1
        self.assertEqual(fractional, [4, 5, 7])                 # q = 1/2, 2/5, 2/7; 3 and 6 are not balanced
        self.assertEqual(violated("fractional", 2), {"slot_class"})

    def test_t46_7_old_key(self):
        old = load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "winding": "distributed"}})
        new = load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm"}, "winding": {"span": "distributed"}})
        self.assertEqual(old, new)
        self.assertNotIn("winding", old["machine"])
        self.assertEqual(load_spec({})["winding"]["span"], "ring")
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "winding": "distributed"},
                       "winding": {"span": "concentrated"}})
        with self.assertRaises(SpecError):
            load_spec({"winding": {"span": "concentrated"}})            # a TFM has a ring winding
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rfm", "principle": "srm"}, "winding": {"span": "distributed"}})
        with self.assertRaises(SpecError):
            load_spec({"machine": {"flux_path": "rfm", "principle": "pmsm", "slots": 15}, "winding": {"layers": 1}})

    def test_t46_8_describe(self):
        from emachine.cli import describe
        spec = load_spec(SPEC)
        with open(DESIGN) as f:
            values = json.load(f)
        self.assertEqual(describe.winding_text(spec, values), "FSCW, q = 0.4, 2 layers, pitch 1 slot, k_w1 = 0.933")
        self.assertEqual(describe.winding_text(load_spec({}), {}), "ring winding (one coil around the axis per phase)")

    def test_t46_8_single_layer_dimensions(self):
        """Same slot, same current density: half the coils, each with twice the area and ampere-turns."""
        spec2 = load_spec(SPEC)
        spec1 = reference_spec(layers=1)
        with open(DESIGN) as f:
            values = json.load(f)
        d2, d1 = design_space.derived(spec2, values), design_space.derived(spec1, values)
        self.assertEqual(d1["coils_per_phase"] * 2, d2["coils_per_phase"])
        self.assertAlmostEqual(d1["coil_area_mm2"], 2 * d2["coil_area_mm2"])
        self.assertAlmostEqual(d1["ampere_turns_peak"], 2 * d2["ampere_turns_peak"])


@slow
class SingleLayerFieldTest(unittest.TestCase):
    def test_t46_9_torque_follows_the_winding_factor(self):
        """Same machine, same slot current: the single-layer FSCW (k_w1 0.966) gives 0.966 / 0.933 of
        the torque of the double layer (within 2 %)."""
        from emachine.pipeline.sweep import sweep
        torques = {}
        with open(DESIGN) as f:
            values = json.load(f)
        for layers in (2, 1):
            spec = reference_spec(layers=layers)
            request = design_space.geometry(spec, values)
            d = design_space.derived(spec, values)
            with tempfile.TemporaryDirectory() as tmp:
                result = sweep(request.parameters, 6, tmp, ampere_turns_peak=d["ampere_turns_peak"], core_field=False,
                               geometry=request.kind)
            # torque per ampere-turn of the phase (coils in series): same copper, same current density
            torques[layers] = float(result["torque_Nm"].mean()) / (d["ampere_turns_peak"] * d["coils_per_phase"])
        self.assertAlmostEqual(torques[1] / torques[2], 0.966 / 0.933, delta=0.02)


if __name__ == "__main__":
    unittest.main()
