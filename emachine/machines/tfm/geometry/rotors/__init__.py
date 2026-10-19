"""
Rotor layouts of the TFM, one module each, named as in docs/naming.md (halbach, surface, spoke,
axial_ring). `code` is the short name in the geometry parameter files (rotor.type; spoke is
"flux_concentrating", axial_ring is "axial"). To add a layout: write a RotorType subclass in its
own module, list it in ROTORS, and give its name and code in machines/tfm/options.py.
"""

import math
import sys

from ..shapes import copies_at, occ, ring, slug
from .axial_ring import AxialRing
from .eddy import eddy_widths  # noqa: F401
from .spoke import Spoke
from .frame import RotorFrame, RotorType  # noqa: F401
from .halbach import Halbach
from .magnets import magnet_angle, magnet_name
from .surface import Surface

ROTORS = {cls.code: cls() for cls in (Surface, Halbach, Spoke, AxialRing)}


def build_rotor(rp, turn):
    """Rotor ring as built by the Onshape feature "TFM rotor" (without shaft and end cap)."""
    code = rp["type"].lower()
    if code not in ROTORS:
        sys.exit("rotor.type must be 'surface', 'halbach', 'flux_concentrating' or 'axial'.")
    kind = ROTORS[code]
    f = RotorFrame(rp, kind)
    if kind.custom_build:
        return kind.build_ring(f, rp, turn)

    electrical, span, width = kind.magnets(f, rp)
    parts, names, magnets = [], [], {}
    row_meta = []
    # Step skew (T72): every row is cut into `steps` axial slices, turned from -skew/2 to +skew/2.
    steps = max(1, int(rp.get("skew_steps", 1)))
    skew = math.radians(float(rp.get("skew_deg", 0.0))) if steps > 1 else 0.0
    for r in range(f.rows):
        z_row = f.z_bottom + r * (f.row_w + f.row_gap)
        for k in range(steps):
            z0 = z_row + k * f.row_w / steps
            z1 = z0 + f.row_w / steps
            shift = f.pitch if (f.alternate and r % 2 == 1) else 0.0
            if steps > 1:
                shift += skew * (k / (steps - 1) - 0.5)
            label = f"{r}" if steps == 1 else f"{r}s{k}"
            row_meta.append({"z0": z0, "z1": z1, "shift_deg": math.degrees(shift)})
            seed = kind.seed(f, rp, z0, z1, span, width)
            staged = []
            for e in electrical:
                beta = magnet_angle(e, f.outrunner)
                kind_name = slug(magnet_name(beta, f.outrunner))
                offset = e / 180.0 * f.pitch
                for j in range(f.poles // 2):
                    centre = offset + 2 * j * f.pitch + shift
                    name = f"{kind_name}_row{label}_{j}"
                    magnets[name] = {"kind": "magnet", "magnet_type": kind_name, "electrical_deg": e,
                                     "beta_deg": beta, "centre_deg": math.degrees(centre + turn), "row": r}
                    staged.append((name, centre))
            for (name, _), tag in zip(staged, copies_at(seed, [a for _, a in staged])):
                parts.append((3, tag))
                names.append(name)
            for dt, name in kind.row_extras(f, rp, z0, z1, width, shift):
                parts.append(dt)
                names.append(name)

    parts.append((3, ring(f.core_in, f.core_out, f.z_bottom, f.z_bottom + f.stack)))
    core_name = kind.core_name(f.outrunner)
    names.append(core_name)
    if abs(turn) > 0:
        occ.rotate(parts, 0, 0, 0, 0, 0, 1, turn)
    info = {
        "gap_radius": f.gap_radius,
        "outrunner": f.outrunner,
        "pole_pairs": f.poles // 2,
        "half_stack": f.stack / 2,
        "r_min": min(f.ra, f.core_in),
        "r_max": max(f.rb, f.core_out),
        "rows": row_meta,
        "magnets": magnets,
        "core_name": core_name,
    }
    return parts, names, info
