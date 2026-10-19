"""U-core and U-core with I-bridge: one U-shaped core per pole pair around the coil."""

import sys

from ..shapes import copies_at, occ
from .frame import StatorType


class UCore(StatorType):
    code = "u"

    def build(self, f, sp):
        xa, xb = sorted((f.radial(f.zb), f.radial(f.height)))
        body = occ.addBox(xa, -f.t / 2, -f.half_w, xb - xa, f.t, 2 * f.half_w)
        wa, wb = sorted((f.radial(f.zb - 1.0), f.radial(f.slot_h)))
        window = occ.addBox(wa, -f.t / 2 - 1, -f.slot_w / 2, wb - wa, f.t + 2, f.slot_w)
        out, _ = occ.cut([(3, body)], [(3, window)])
        seed = f.trim(out[0][1])
        return [(3, tag) for tag in copies_at(seed, f.evens)]


class UICore(UCore):
    """U-core plus an I-bridge: a trapezoid in the radial-axial plane, on the pole pitches between the U-cores."""
    code = "ui"

    def build(self, f, sp):
        parts = super().build(f, sp)
        hb = sp["bridge_height"]
        top = sp["bridge_top_ratio"] * f.slot_w / 2
        if top >= f.half_w or hb >= f.slot_h:
            sys.exit("The I-bridge does not fit: check bridge_top_ratio and bridge_height.")
        seed = f.trim(f.prism_axial_height([(-f.half_w, f.zb), (f.half_w, f.zb), (f.half_w, 0.0), (top, hb),
                                            (-top, hb), (-f.half_w, 0.0)]))
        return parts + [(3, tag) for tag in copies_at(seed, f.odds)]
