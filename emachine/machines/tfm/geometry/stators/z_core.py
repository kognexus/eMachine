"""Z-core: a plate with a coil window, a tooth that faces the rotor from one side, and a leg that
passes the rotor and returns on its other side as a limb. Built for --stator-only; not analysable
yet (ticket B02)."""

import sys

from ..shapes import copies_at
from .frame import StatorType


class ZCore(StatorType):
    code = "z"
    analysable = False

    def layout(self, f, sp):
        f.window_top = f.slot_h + sp["z_tooth_height"]
        f.trimmable = False                    # the air gap is enclosed between tooth and return limb

    def r_near(self, f, sp):
        return f.radial(-sp["z_rotor_gap"] - f.yoke)      # the Z-core reaches past the air gap

    def build(self, f, sp):
        half_w, slot_w = f.half_w, f.slot_w
        h_tooth, rotor_gap = sp["z_tooth_height"], sp["z_rotor_gap"]
        y1 = slot_w / 2 - sp["z_slot_gap"]          # tooth face next to the leg
        y0 = y1 - sp["z_tooth_width"]
        if sp["z_slot_gap"] >= slot_w:
            sys.exit("The tooth to leg gap must be smaller than the slot width.")
        if y0 <= -half_w:
            sys.exit("The tooth is too wide for this core.")
        z_limb = -rotor_gap - f.yoke
        seed = f.prism_axial_height([
            (-half_w, z_limb), (half_w, z_limb), (half_w, f.height), (-half_w, f.height), (-half_w, h_tooth / 2),
            (y0, h_tooth / 2), (y0, 0.0), (y1, 0.0), (y1, h_tooth), (-slot_w / 2, h_tooth), (-slot_w / 2, f.window_top),
            (slot_w / 2, f.window_top), (slot_w / 2, -rotor_gap), (-half_w, -rotor_gap)])
        return [(3, tag) for tag in copies_at(seed, f.evens)]
