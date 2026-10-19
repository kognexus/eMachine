"""
Parameters of the TFM sector geometry: the defaults of every stator, rotor and mesh parameter
(mirroring the Onshape features "TFM stator" and "TFM rotor"), and their merge with a parameter file.
"""

import copy
import sys

DEFAULTS = {
    "stator": {
        "core_type": "u",            # "u", "ui" (U-core with I-bridge), "cp" (claw pole) or "tr" (toothed
                                     # ring, Fig. 17) for analysis; "c", "e" and "z" are built for --stator-only
        "air_gap_radius": 60.0,
        "pole_pairs": 16,
        "inner_stator": False,
        "trim_pole_faces": True,
        "tooth_span": 0.8,           # core thickness / pole pitch
        "leg_width": 10.0,
        "slot_width": 20.0,
        "slot_height": 25.0,
        "yoke_height": 10.0,
        "bridge_height": 6.0,
        "bridge_top_ratio": 0.8,     # I-bridge top width / slot width
        "pole_shift_deg": 0.0,       # extra offset of every second core element (review paper, Fig. 17)
        "claw_root_height": 8.0,     # claw pole: claw thickness at its root
        "claw_tip_height": 2.0,      # claw pole: claw thickness at its tip
        "claw_tip_gap": 1.0,         # claw pole: gap between the claw tip and the opposite side wall
        "claw_full_discs": False,    # claw pole: two discs with L-shaped claws (continuous discs below the claw
                                     # level, a rim tooth only under the disc's own claws, continuous yoke), as
                                     # SMC claw-pole stators; False: O-shaped frames as the Onshape feature
        "skew_fraction": 0.6,        # C- and E-core: yoke skew transition / slot width
        "mid_leg_width": 20.0,       # E-core: width of the middle leg
        "z_tooth_height": 12.0,      # Z-core: tooth height
        "z_tooth_width": 10.0,       # Z-core: tooth width
        "z_slot_gap": 2.0,           # Z-core: gap between tooth and leg
        "z_rotor_gap": 6.0,          # Z-core: height of the gap that holds the rotor
        "ring_tooth_height": 8.0,    # toothed ring: height of the teeth above the continuous side walls
        "ring_arched_valleys": False,  # toothed ring: arch from tooth to tooth instead of straight-cut teeth
        "ring_staggered_teeth": False, # toothed ring: back-wall teeth one pole pitch after the front-wall teeth
        "ring_tip_overhang": 0.0,    # toothed ring: axial reach of each tooth tip over the coil slot (0: no tips, T73)
        "ring_tip_height": 0.0,      # toothed ring: radial thickness of the tooth tips
        "include_coil": True,
        "coil_height": 12.0,
        "coil_clearance": 1.0,
    },
    "rotor": {
        "configuration": "inrunner",  # "inrunner" or "outrunner"
        "type": "surface",            # "surface", "halbach", "flux_concentrating" or "axial" (axially
                                      # magnetised ring between two toothed discs; row_gap is its axial length)
        "outer_diameter": 118.0,      # inrunner: air-gap diameter. outrunner: housing diameter
        "shaft_diameter": 30.0,       # inrunner only
        "inner_diameter": 122.0,      # outrunner only: air-gap diameter
        "stack_length": 40.0,
        "poles": 32,
        "magnet_thickness": 5.0,
        "magnet_arc_ratio": 0.85,
        "segments_per_pole": 2,
        "fc_magnet_height": 12.0,
        "fc_magnet_width": 4.0,
        "magnet_rows": 2,
        "row_gap": 20.0,
        "alternate_rows": True,
        "skew_steps": 1,              # step skew of the magnets in each row (T72): axial slices
        "skew_deg": 0.0,              # mechanical angle between the first and the last slice
    },
    "mesh": {
        "gap_cell": None,            # cell size on the sliding surfaces; default = air-gap length
        "size_max": 6.0,             # cell size far from the gap
        "axial_margin": None,        # air beyond the stack at each end
        "outer_margin": None,        # air beyond the largest radius
        "inner_radius": None,        # inner limit of the model (must be > 0)
        "sector_start_deg": None,    # default: minus half a stator pole pitch
        "rotor_angle_deg": 0.0,      # turns the rotor parts before meshing
        "sliding_theta_multiple": 1, # make the cell count around the sliding surface a multiple of this
    },
}


def merged(defaults, overrides):
    out = copy.deepcopy(defaults)
    for section, values in (overrides or {}).items():
        if section in ("analysis", "design", "machine", "summary"):
            continue  # solver settings (emachine solve) and optimizer bookkeeping (emachine/machines/tfm/design.py)
        if section not in out:
            sys.exit(f"Unknown section '{section}' in the parameter file.")
        for key, value in values.items():
            if key not in out[section]:
                sys.exit(f"Unknown parameter '{section}.{key}' in the parameter file.")
            out[section][key] = value
    return out
