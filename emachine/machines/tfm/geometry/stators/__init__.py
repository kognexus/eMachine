"""
Stator types of the TFM, one module each. To add a type: write a StatorType subclass in its own
module and list it in STATORS.
"""

import math
import sys

from ..shapes import ring
from .c_core import CCore
from .claw_pole import ClawPole
from .e_core import ECore
from .frame import StatorFrame, StatorType  # noqa: F401
from .toothed_ring import ToothedRing, valley_cutter, valley_profile  # noqa: F401
from .u_core import UCore, UICore
from .z_core import ZCore

STATORS = {cls.code: cls() for cls in (UCore, UICore, ClawPole, ToothedRing, CCore, ECore, ZCore)}


def build_stator(sp):
    """
    Stator ring as built by the Onshape feature "TFM stator". Returns (parts, names, info): the
    solids, their region names ("tfm_core", "tfm_coil") and a description of the ring.
    """
    core_type = sp["core_type"].lower()
    if core_type not in STATORS:
        sys.exit("stator.core_type must be one of 'u', 'ui', 'cp', 'tr', 'c', 'e', 'z'.")
    kind = STATORS[core_type]
    f = StatorFrame(sp)
    kind.layout(f, sp)
    f.finish(sp, kind)

    core = kind.build(f, sp)
    parts, names = list(core), ["tfm_core"] * len(core)
    coil = None
    # Ring coil in the top of each coil window
    if sp["include_coil"]:
        hc, cl = sp["coil_height"], sp["coil_clearance"]
        if hc + 2 * cl > f.slot_h or 2 * cl >= f.slot_w:
            sys.exit("The coil does not fit in the slot.")
        r0, r1 = sorted((f.radial(f.window_top - cl - hc), f.radial(f.window_top - cl)))
        for centre in f.coil_centres:
            parts.append((3, ring(r0, r1, centre - f.slot_w / 2 + cl, centre + f.slot_w / 2 - cl)))
            names.append("tfm_coil")
        if len(f.coil_centres) == 1:
            coil = {"r0_mm": r0, "r1_mm": r1, "half_height_mm": f.slot_w / 2 - cl,
                    "shell": "inward" if f.sign < 0 else "outward",
                    "area_mm2": sp["coil_height"] * (f.slot_w - 2 * cl)}

    r_far = f.radial(f.height)
    r_near = kind.r_near(f, sp)
    info = {
        "core_type": core_type,
        "gap_radius": f.R,
        "pole_pairs": f.p,
        "repeats": f.p // 2 if f.shift else f.p,
        "pitch": f.pitch,
        "half_width": f.half_w,
        "r_min": min(r_near, r_far),
        "r_max": max(r_near, math.hypot(r_far, f.x_max)) if f.sign > 0 else r_near,
        "analysable": kind.analysable,
        "core_thickness": f.t,
        "core_inner_arc": 2 * math.pi * r_far / kind.cores_per_turn(f) if f.sign < 0 else None,
        "coil": coil,
    }
    return parts, names, info
