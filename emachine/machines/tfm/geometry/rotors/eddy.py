"""Widths of the eddy-current paths in the rotor parts, for the rotor loss model (T31)."""

import math

import numpy as np


def eddy_widths(rotor):
    """
    Width in m of the path of the eddy currents in each rotor part, by part code (0 rotor iron,
    1 rotor housing, 2 magnet): the radial thickness of the rotor core (iron or housing), and for a
    magnet the smaller of its width along the circumference (at the air gap) and its axial length.
    """
    poles = int(rotor["poles"])
    outrunner = rotor["configuration"].lower() == "outrunner"
    kind = rotor["type"].lower()
    hm = rotor["fc_magnet_height"] if kind == "flux_concentrating" else rotor["magnet_thickness"]
    if outrunner:
        gap = rotor["inner_diameter"] / 2
        core = rotor["outer_diameter"] / 2 - (gap + hm)
    else:
        gap = rotor["outer_diameter"] / 2
        core = gap - hm - rotor["shaft_diameter"] / 2
    pitch = 2 * math.pi * gap / poles
    if kind == "surface":
        width = rotor["magnet_arc_ratio"] * pitch
    elif kind == "halbach":
        width = pitch / int(rotor["segments_per_pole"])
    elif kind == "flux_concentrating":
        width = rotor["fc_magnet_width"]
    else:                                   # axial ring magnet: the thinner of radial and axial size
        width = min(hm, rotor["row_gap"])
    rows = int(rotor["magnet_rows"])
    row_length = (rotor["stack_length"] - (rows - 1) * (rotor["row_gap"] if rows > 1 else 0.0)) / rows
    if kind != "axial":
        width = min(width, row_length / max(1, int(rotor.get("skew_steps", 1))))
    return np.array([core, core, width]) / 1000.0
