"""C-core: the rotor runs between the two legs, one pole pitch apart, joined by a skewed yoke.
Built for --stator-only; not analysable yet (ticket B02)."""

from ..shapes import copies_at
from .frame import StatorType


class CCore(StatorType):
    code = "c"
    analysable = False

    def layout(self, f, sp):
        f.x_max = (f.tau + f.t) / 2
        f.trimmable = False                    # the air gaps are the inner leg faces

    def build(self, f, sp):
        half, half_w, slot_w = f.half, f.half_w, f.slot_w
        xa, xb = -f.tau / 2, f.tau / 2
        yk = sp["skew_fraction"] * slot_w / 2
        seed = f.fused([
            f.block(xa - half, xa + half, -half_w, -slot_w / 2, 0.0, f.height),
            f.block(xb - half, xb + half, slot_w / 2, half_w, 0.0, f.height),
            f.prism_tangential_axial([(xa - half, -half_w), (xa + half, -half_w), (xa + half, -yk), (xb + half, yk),
                                      (xb + half, half_w), (xb - half, half_w), (xb - half, yk), (xa - half, -yk)],
                                     f.slot_h, f.yoke)])[0]
        return [(3, tag) for tag in copies_at(seed, f.mids)]
