"""T41-1: slot star, phase belts and winding factors of double-layer windings."""

import unittest

from emachine.machines import winding_layout as wl


class LayoutTest(unittest.TestCase):
    def test_t41_1_concentrated_12_slots_10_poles(self):
        layout = wl.double_layer(slots=12, pole_pairs=5, phases=3, kind="concentrated")
        self.assertEqual(len(layout.coils), 12)
        self.assertEqual(sorted(sum(1 for c in layout.coils if c.phase == k) for k in range(3)), [4, 4, 4])
        self.assertAlmostEqual(wl.winding_factor(layout, 1), 0.933, places=3)
        # Each tooth carries one coil: sides in the slots on both sides of the tooth, opposite signs.
        c = layout.coils[0]
        self.assertEqual((c.slot_in, c.slot_out), (0, 1))

    def test_t41_1_distributed_36_slots_4_poles(self):
        layout = wl.double_layer(slots=36, pole_pairs=2, phases=3, kind="distributed")
        self.assertEqual(len(layout.coils), 36)
        self.assertAlmostEqual(wl.winding_factor(layout, 1), 0.960, places=3)     # q = 3, full pitch
        self.assertEqual(layout.coils[0].slot_out - layout.coils[0].slot_in, 9)

    def test_balanced_phases_120_degrees_apart(self):
        layout = wl.double_layer(slots=12, pole_pairs=5, phases=3, kind="concentrated")
        angles = [wl.phase_axis_deg(layout, k) for k in range(3)]
        spread = sorted(((angles[k] - angles[0]) % 360) for k in (1, 2))
        self.assertAlmostEqual(spread[0], 120.0, places=6)
        self.assertAlmostEqual(spread[1], 240.0, places=6)

    def test_unbalanced(self):
        with self.assertRaises(ValueError):
            wl.double_layer(slots=12, pole_pairs=6, phases=3, kind="concentrated")


if __name__ == "__main__":
    unittest.main()


class SequenceTest(unittest.TestCase):
    def test_phase_b_lies_120_degrees_further_on(self):
        for slots, p, kind in ((12, 5, "concentrated"), (36, 2, "distributed"), (12, 4, "concentrated")):
            layout = wl.double_layer(slots=slots, pole_pairs=p, phases=3, kind=kind)
            a, b, c = (wl.phase_axis_deg(layout, k) for k in range(3))
            self.assertAlmostEqual((b - a) % 360, 120.0, places=6, msg=(slots, p))
            self.assertAlmostEqual((c - a) % 360, 240.0, places=6, msg=(slots, p))
