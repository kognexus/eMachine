"""Claw-pole core: one claw per pole pitch, the claw roots alternating between the two side walls."""

import math
import sys

from ..shapes import copies_at, occ, ring
from .frame import StatorType


class ClawPole(StatorType):
    code = "cp"
    allows_pole_shift = False

    def layout(self, f, sp):
        f.window_top = f.slot_h + sp["claw_root_height"]

    def cores_per_turn(self, f):
        return 2 * f.p

    def build(self, f, sp):
        zc, zt, tip_gap = sp["claw_root_height"], sp["claw_tip_height"], sp["claw_tip_gap"]
        half_w, slot_w, zb = f.half_w, f.slot_w, f.zb
        if tip_gap >= slot_w:
            sys.exit("The claw tip gap must be smaller than the slot width.")
        if zt > zc:
            sys.exit("The claw tip must not be thicker than the claw root.")
        solids = []
        if sp["claw_full_discs"]:
            # Two discs with claws (SMC claw-pole stators): each disc is a continuous ring below the
            # claw level and carries an L-shaped claw on every second pole pitch (a rim tooth on the
            # disc plus a head across the coil window). At the claw level a disc has no iron where the
            # claws of the other disc reach across. The yoke is a continuous ring.
            for s_, angles in ((1.0, f.evens), (-1.0, f.odds)):
                seed = f.trim(f.prism_axial_height([
                    (-s_ * half_w, zb), (s_ * (slot_w / 2 - tip_gap), zb), (s_ * (slot_w / 2 - tip_gap), zt),
                    (-s_ * slot_w / 2, zc), (-s_ * half_w, zc)]))
                solids += copies_at(seed, angles)
            walls = sorted((f.radial(zc), f.radial(f.height)))
            solids += [ring(*walls, -half_w, -slot_w / 2), ring(*walls, slot_w / 2, half_w),
                       ring(*sorted((f.radial(f.window_top), f.radial(f.height))), -half_w, half_w)]
        else:
            # An O-shaped frame on every pole pitch. Each frame carries one wedge-shaped claw that spans
            # the air-gap width. Diagonal yoke links tie neighbouring frames together.
            for s_, angles in ((1.0, f.evens), (-1.0, f.odds)):
                seed = f.trim(f.prism_axial_height([
                    (-s_ * half_w, zb), (s_ * (slot_w / 2 - tip_gap), zb), (s_ * (slot_w / 2 - tip_gap), zt),
                    (-s_ * slot_w / 2, zc), (-s_ * slot_w / 2, f.window_top), (s_ * slot_w / 2, f.window_top),
                    (s_ * slot_w / 2, zb), (s_ * half_w, zb), (s_ * half_w, f.height), (-s_ * half_w, f.height)]))
                solids += copies_at(seed, angles)
            hs = f.radial((f.window_top + f.height) / 2) * math.sin(f.pitch / 2)
            seed = f.prism_tangential_axial([(-hs, half_w), (-hs, half_w - f.leg), (hs, -half_w), (hs, -half_w + f.leg)],
                                            f.window_top, f.yoke)
            solids += copies_at(seed, [(j + 0.5) * f.pitch for j in range(2 * f.p)])
        out, _ = occ.fuse([(3, solids[0])], [(3, tag) for tag in solids[1:]])
        return [dt for dt in out if dt[0] == 3]
