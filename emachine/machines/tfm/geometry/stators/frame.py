"""
The frame shared by all stator types: dimensions of one core element at angle 0 (radial = X,
tangential = Y, axial = Z), its pole angles and the shape helpers that work in that frame.
"""

import math
import sys

from ..shapes import occ


class StatorType:
    """One kind of stator core. Subclasses build their core elements in a StatorFrame."""

    code = ""
    analysable = True            # can be meshed for analysis (one coil, rotor outside the core)
    allows_pole_shift = True

    def layout(self, frame, sp):
        """Adjusts the frame before its height is known (coil window, trimming, coil centres)."""

    def build(self, frame, sp):
        """Returns the core solids as a list of (dimension, tag)."""
        raise NotImplementedError

    def r_near(self, frame, sp):
        """Radius of the part of the core nearest to the rotor (default: the air gap)."""
        return frame.R

    def cores_per_turn(self, frame):
        """Core elements around the circumference whose far ends could touch."""
        return frame.p


class StatorFrame:
    def __init__(self, sp):
        self.R = float(sp["air_gap_radius"])
        self.p = int(sp["pole_pairs"])
        self.sign = -1.0 if sp["inner_stator"] else 1.0
        self.pitch = math.pi / self.p
        self.tau = self.R * self.pitch
        self.t = sp["tooth_span"] * self.tau
        self.leg, self.slot_w, self.slot_h, self.yoke = sp["leg_width"], sp["slot_width"], sp["slot_height"], sp["yoke_height"]
        self.half_w = self.slot_w / 2 + self.leg
        self.window_top = self.slot_h          # top of the coil window, as a height above the air gap
        self.coil_centres = [0.0]              # axial positions of the coil centres
        self.x_max = self.t / 2                # largest tangential half extent of one rigid core element
        self.trimmable = True

    def finish(self, sp, kind):
        """Height, trimming and pole angles, once the stator type has adjusted the layout."""
        self.height = self.window_top + self.yoke
        self.do_trim = bool(sp["trim_pole_faces"]) and self.trimmable
        if sp["inner_stator"] and self.R <= self.height:
            sys.exit("For an inner stator the air-gap radius must exceed the stator height.")
        # Legs are built slightly long and cut back to the air-gap cylinder (same as the Onshape feature).
        margin = 0.05 * self.tau
        self.zb = 0.0
        if self.do_trim:
            self.zb = -(self.R - math.sqrt(self.R * self.R - self.x_max ** 2) + margin) if self.sign > 0 else -margin
        # Every second core element may carry an extra offset; the stator then repeats every two pole pairs.
        self.shift = math.radians(sp["pole_shift_deg"])
        if self.shift and not kind.allows_pole_shift:
            sys.exit("The pole shift is not available for the claw-pole core, whose frames are linked.")
        if self.shift and self.p % 2:
            sys.exit("A pole shift needs an even number of pole pairs.")
        p, pitch, shift = self.p, self.pitch, self.shift
        self.evens = [2 * k * pitch + (shift if k % 2 else 0.0) for k in range(p)]
        self.odds = [(2 * k + 1) * pitch + (shift if k % 2 else 0.0) for k in range(p)]
        self.mids = [(2 * k + 0.5) * pitch + (shift if k % 2 else 0.0) for k in range(p)]
        self.half = self.t / 2

    # ---- shape helpers in the frame of the core element at angle 0

    def radial(self, z):
        """Element height above the air gap -> radius."""
        return self.R + self.sign * z

    def trim(self, tag):
        if not self.do_trim:
            return tag
        cyl = occ.addCylinder(0, 0, -2 * self.half_w, 0, 0, 4 * self.half_w, self.R)
        if self.sign > 0:
            out, _ = occ.cut([(3, tag)], [(3, cyl)])
        else:
            out, _ = occ.intersect([(3, tag)], [(3, cyl)])
        return out[0][1]

    @staticmethod
    def polygon_face(points):
        clean = []
        for point in points:
            if not clean or max(abs(a - b) for a, b in zip(point, clean[-1])) > 1e-9:
                clean.append(point)
        if max(abs(a - b) for a, b in zip(clean[0], clean[-1])) <= 1e-9:
            clean.pop()
        tags = [occ.addPoint(*point) for point in clean]
        lines = [occ.addLine(tags[i], tags[(i + 1) % len(tags)]) for i in range(len(tags))]
        return occ.addPlaneSurface([occ.addCurveLoop(lines)])

    def prism_axial_height(self, outline):
        """Outline of (axial, height) points, extruded along the tangential direction over the core thickness."""
        face = self.polygon_face([(self.radial(z), -self.t / 2, axial) for axial, z in outline])
        return [dt for dt in occ.extrude([(2, face)], 0, self.t, 0) if dt[0] == 3][0][1]

    def prism_tangential_axial(self, outline, z0, thickness):
        """Outline of (tangential, axial) points at height z0, extruded away from the air gap."""
        face = self.polygon_face([(self.radial(z0), tangential, axial) for tangential, axial in outline])
        return [dt for dt in occ.extrude([(2, face)], self.sign * thickness, 0, 0) if dt[0] == 3][0][1]

    def block(self, t0, t1, a0, a1, z0, z1):
        """Box from tangential t0..t1, axial a0..a1 and heights z0..z1 above the air gap."""
        r0, r1 = sorted((self.radial(z0), self.radial(z1)))
        return occ.addBox(r0, t0, a0, r1 - r0, t1 - t0, a1 - a0)

    @staticmethod
    def fused(tags):
        out, _ = occ.fuse([(3, tags[0])], [(3, tag) for tag in tags[1:]])
        return [dt[1] for dt in out if dt[0] == 3]
