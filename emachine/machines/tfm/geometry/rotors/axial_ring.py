"""
Axially magnetised ring magnet between two toothed soft-iron discs (review paper, Fig. 3c), as built
by the Onshape feature. The disc at the -Z end has a tooth at angle 0 and is the north pole; the
teeth of the other disc sit one pole pitch further. Discs and magnet fill the core region, the
teeth the magnet region.
"""

import math
import sys

from ..shapes import copies_at, occ, ring, ring_sector
from .frame import RotorType


class AxialRing(RotorType):
    code = "axial"
    custom_build = True

    def build_ring(self, f, rp, turn):
        stack, z_bottom, pitch, poles = f.stack, f.z_bottom, f.pitch, f.poles
        ra, rb, core_in, core_out = f.ra, f.rb, f.core_in, f.core_out
        magnet_length = rp["row_gap"]
        disc = (stack - magnet_length) / 2
        if magnet_length <= 1e-6 or disc <= 1e-6:
            sys.exit("Axial rotor: row_gap is the axial length of the ring magnet and must leave room for two discs.")
        span = rp["magnet_arc_ratio"] * pitch
        parts, names = [], []
        for d, label in ((0, "n"), (1, "s")):
            zd = z_bottom + d * (stack - disc)
            seed = ring_sector(ra, rb, zd, zd + disc, -span / 2, span)
            teeth = copies_at(seed, [(2 * j + d) * pitch for j in range(poles // 2)])
            out, _ = occ.fuse([(3, ring(core_in, core_out, zd, zd + disc))], [(3, tag) for tag in teeth])
            for dt in out:
                if dt[0] == 3:
                    parts.append(dt)
                    names.append(f"rotor_pole_piece_disc_{label}")
        parts.append((3, ring(core_in, core_out, z_bottom + disc, z_bottom + stack - disc)))
        names.append("magnet_axial")
        magnets = {"magnet_axial": {"kind": "magnet", "magnet_type": "magnet_axial", "axis": "axial", "direction": -1.0,
                                    "electrical_deg": 0.0, "beta_deg": 0.0, "centre_deg": 0.0, "row": 0}}
        if abs(turn) > 0:
            occ.rotate(parts, 0, 0, 0, 0, 0, 1, turn)
        return parts, names, {
            "gap_radius": f.gap_radius, "outrunner": f.outrunner, "pole_pairs": poles // 2, "half_stack": stack / 2,
            "r_min": min(ra, core_in), "r_max": max(rb, core_out),
            "rows": [{"z0": z_bottom, "z1": z_bottom + disc, "shift_deg": 0.0},
                     {"z0": z_bottom + stack - disc, "z1": z_bottom + stack, "shift_deg": math.degrees(pitch)}],
            "magnets": magnets, "core_name": None}
