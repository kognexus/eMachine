"""E-core: three legs and two coils; the middle leg sits one pole pitch from the outer legs, so the
yoke is a chevron seen along the radius. Built for --stator-only; not analysable yet (ticket B02)."""

from ..shapes import copies_at
from .frame import StatorType


class ECore(StatorType):
    code = "e"
    analysable = False

    def layout(self, f, sp):
        f.half_w = sp["mid_leg_width"] / 2 + f.slot_w + f.leg
        f.coil_centres = [-(sp["mid_leg_width"] / 2 + f.slot_w / 2), sp["mid_leg_width"] / 2 + f.slot_w / 2]
        f.x_max = (f.tau + f.t) / 2

    def build(self, f, sp):
        half, half_w, slot_w, leg, zb, height = f.half, f.half_w, f.slot_w, f.leg, f.zb, f.height
        w_mid = sp["mid_leg_width"]
        xo, xm = -f.tau / 2, f.tau / 2
        yc = w_mid / 2 + slot_w / 2
        ya, yb = yc + sp["skew_fraction"] * slot_w / 2, yc - sp["skew_fraction"] * slot_w / 2
        seed = f.fused([
            f.block(xo - half, xo + half, -half_w, -half_w + leg, zb, height),
            f.block(xo - half, xo + half, half_w - leg, half_w, zb, height),
            f.block(xm - half, xm + half, -w_mid / 2, w_mid / 2, zb, height),
            f.prism_tangential_axial([(xo - half, -half_w), (xo + half, -half_w), (xo + half, -ya), (xm + half, -yb),
                                      (xm + half, yb), (xo + half, ya), (xo + half, half_w), (xo - half, half_w),
                                      (xo - half, ya), (xm - half, yb), (xm - half, -yb), (xo - half, -ya)],
                                     f.slot_h, f.yoke)])[0]
        seed = f.trim(seed)
        return [(3, tag) for tag in copies_at(seed, f.mids)]
