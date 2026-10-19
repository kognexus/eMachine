"""
Toothed ring (review paper, Fig. 17): one continuous U-shaped ring holds the coil, and teeth stand
on both side walls, one per pole pair on each wall: aligned, or with the back wall one pole pitch
later (staggered). Straight-cut teeth or arched valleys between the teeth.
"""

import math
import sys

from ..shapes import copies_at, occ, ring
from .frame import StatorType


def valley_profile(R, gap_angle, half, depth, margin, sign=1.0):
    """
    Outline of the arched valley between two teeth of a toothed ring, in the frame of the valley
    centre: (tangential, height above the air gap) points, with arcs given by their middle point.

    The arch ends at the top corners of the two teeth, which lie on the air-gap circle so that each
    tooth keeps its top width 2 * half, and its deepest point is at `depth` on the bisector. If the
    valley is deeper than half its width, the bottom is a half circle and the sides are straight.
    The outline is closed on the rotor side of the air gap, `margin` beyond the corners. `sign` is +1
    for an outer stator (height grows with the radius) and -1 for an inner stator.
    Returns a list of ("line", end) and ("arc", middle, end) steps that starts and ends at the left
    corner; R = None gives the linear arrangement with gap_angle as the distance between teeth.
    """
    if R is None:
        xc, zc = gap_angle / 2 - half, 0.0
    else:
        phi = gap_angle / 2 - math.asin(half / R)
        xc, zc = R * math.sin(phi), sign * (R * math.cos(phi) - R)   # the corner lies on the air-gap circle
    if xc <= 0:
        sys.exit("The teeth are too wide for arched valleys.")
    start = (-xc, zc)
    steps = []
    if depth - zc <= xc:
        steps.append(("arc", (0.0, depth), (xc, zc)))
    else:
        steps += [("line", (-xc, depth - xc)), ("arc", (0.0, depth), (xc, depth - xc)), ("line", (xc, zc))]
    steps += [("line", (xc, zc - margin)), ("line", (-xc, zc - margin)), ("line", start)]
    return start, steps


def valley_cutter(outline, sign, R, z0, z1, angle):
    """Solid that removes one arched valley: the outline extruded from axial z0 to z1, turned to `angle`."""
    start, steps = outline

    def point(x, z):  # valley frame (tangential, height) -> world at angle 0, on the plane z0
        return occ.addPoint(R + sign * z, x, z0)

    def centre(a, m, b):  # centre of the circle through three points of the valley frame
        (ax, az), (mx, mz), (bx, bz) = a, m, b
        d = 2 * (ax * (mz - bz) + mx * (bz - az) + bx * (az - mz))
        ux = ((ax * ax + az * az) * (mz - bz) + (mx * mx + mz * mz) * (bz - az) + (bx * bx + bz * bz) * (az - mz)) / d
        uz = ((ax * ax + az * az) * (bx - mx) + (mx * mx + mz * mz) * (ax - bx) + (bx * bx + bz * bz) * (mx - ax)) / d
        return ux, uz

    curves, here, centres = [], start, []
    first = tag = point(*start)
    for step in steps:
        end = step[-1]
        end_tag = first if end == start else point(*end)
        if step[0] == "line":
            curves.append(occ.addLine(tag, end_tag))
        else:
            c = point(*centre(here, step[1], end))
            centres.append((0, c))
            m = point(*step[1])
            curves += [occ.addCircleArc(tag, c, m), occ.addCircleArc(m, c, end_tag)]
        here, tag = end, end_tag
    face = occ.addPlaneSurface([occ.addCurveLoop(curves)])
    solid = [dt for dt in occ.extrude([(2, face)], 0, 0, z1 - z0) if dt[0] == 3][0]
    # Arc centres are construction points only. Left in the model they would be meshed as free
    # nodes that are not written to the mesh file, and the node count of the pipeline would not match.
    occ.remove(centres)
    occ.rotate([solid], 0, 0, 0, 0, 0, 1, angle)
    return solid[1]


class ToothedRing(StatorType):
    code = "tr"

    def layout(self, f, sp):
        if sp["ring_arched_valleys"]:
            f.trimmable = False                # the walls start at the air-gap cylinder

    def build(self, f, sp):
        # Each tooth reaches up to the slot height, so its flat end lies inside the wall and tooth and
        # ring fuse into one solid.
        h_t = sp["ring_tooth_height"]
        half_w, slot_w, slot_h, half = f.half_w, f.slot_w, f.slot_h, f.half
        if not 0 < h_t < slot_h:
            sys.exit("The ring tooth height must lie between 0 and the slot height.")
        if f.sign > 0 and math.hypot(f.radial(slot_h), half) > f.radial(f.height):
            sys.exit("The yoke is too thin to cover the tooth ends.")
        arched = bool(sp["ring_arched_valleys"])
        walls = sorted((f.radial(0.0 if arched else h_t), f.radial(slot_h)))
        solids = [ring(*walls, -half_w, -slot_w / 2), ring(*walls, slot_w / 2, half_w),
                  ring(*sorted((f.radial(slot_h), f.radial(f.height))), -half_w, half_w)]
        # (axial range of the wall, tooth angles): front wall at -axial, back wall at +axial
        wall_teeth = (((-half_w, -slot_w / 2), f.evens),
                      ((slot_w / 2, half_w), f.odds if sp["ring_staggered_teeth"] else f.evens))
        if not arched:
            for (a0, a1), angles in wall_teeth:
                solids += copies_at(f.trim(f.block(-half, half, a0, a1, f.zb, slot_h)), angles)
        core = f.fused(solids)
        if arched:
            # The walls start at the air gap; the space between two neighbouring teeth of a wall is cut
            # away under an arch drawn in the frame of the valley centre (see valley_profile). Each
            # cutter stops at the coil mid-plane, so it touches its own wall only.
            cutters = []
            for (a0, a1), angles in wall_teeth:
                z0, z1 = (-half_w - 1.0, 0.0) if a0 < 0 else (0.0, half_w + 1.0)
                for i, a in enumerate(angles):
                    b = angles[i + 1] if i + 1 < f.p else angles[0] + 2 * math.pi
                    outline = valley_profile(f.R, b - a, half, h_t, 0.5 * f.tau, f.sign)
                    cutters.append(valley_cutter(outline, f.sign, f.R, z0, z1, (a + b) / 2))
            out, _ = occ.cut([(3, tag) for tag in core], [(3, tag) for tag in cutters])
            core = [dt[1] for dt in out if dt[0] == 3]
        core = self.add_tips(f, sp, core, wall_teeth)
        return [(3, tag) for tag in core]

    @staticmethod
    def add_tips(f, sp, core, wall_teeth):
        """
        Tooth tips (T73): each tooth reaches `ring_tip_overhang` over the coil slot, from the air gap
        down to `ring_tip_height`, as wide as the tooth top. Added after the valleys are cut, so the
        cutters of one wall do not touch the tips of the other wall; the top lies on the air-gap
        cylinder. Off unless both values are given.
        """
        over, tip_h = float(sp.get("ring_tip_overhang", 0.0)), float(sp.get("ring_tip_height", 0.0))
        if over <= 0 or tip_h <= 0:
            return core
        slot_w, half = f.slot_w, f.half
        staggered = bool(sp["ring_staggered_teeth"])
        if over >= slot_w or (not staggered and 2 * over >= slot_w):
            sys.exit("The tooth tips reach the opposite wall (or the opposite tips): reduce the overhang.")
        if tip_h >= sp["ring_tooth_height"]:
            sys.exit("The tooth tips must be thinner than the ring tooth height.")
        margin = 0.05 * f.tau
        cylinder = occ.addCylinder(0, 0, -2 * f.half_w, 0, 0, 4 * f.half_w, f.R)
        tips = []
        for (a0, a1), angles in wall_teeth:
            # The block starts at the face of its own wall and fuses with the tooth there. (Reaching into
            # the wall would fill the slivers that arched valleys cut from the tooth sides below its top.)
            t0, t1 = (a1, a1 + over) if a0 < 0 else (a0 - over, a0)
            block = f.block(-half, half, t0, t1, -(f.R - math.sqrt(f.R * f.R - half * half) + margin)
                            if f.sign > 0 else -margin, tip_h)
            tool = occ.copy([(3, cylinder)])
            if f.sign > 0:
                out, _ = occ.cut([(3, block)], tool)
            else:
                out, _ = occ.intersect([(3, block)], tool)
            tips += copies_at(out[0][1], angles)
        occ.remove([(3, cylinder)], recursive=True)
        return f.fused(core + tips)
