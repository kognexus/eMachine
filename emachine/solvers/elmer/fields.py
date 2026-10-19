"""Fields saved from a solution: flux density of the stator core and the rotor parts (losses), coil flux."""

import math
import os

import numpy as np

from .results import flux_density_name, tet_volumes

#: Rotor parts whose losses are estimated (emachine.physics.losses), with their code in rotor_kind.
ROTOR_LOSS_KINDS = {"rotor iron": 0, "rotor housing": 1, "magnet": 2}


def save_core_field(posdir, data, coil, periodicity, angle_deg=0.0, eddy_widths_m=None):
    """
    Saves the flux density in the stator core of this position to core_field.npz:
    element centroids (m), element volumes (m3, one sector), flux density vectors (T).
    Rotor iron, rotor housing and magnets are saved as well, in the rotor frame (positions turned
    back by the rotor angle) with cylindrical components (B_r, B_theta, B_z), for the rotor losses.
    Returns the file path, or None when there is no core.
    """
    points, tets, body, fields = data
    name = flux_density_name(fields)
    if name is None or not coil["core_bodies"]:
        return None
    sel = tets[np.isin(body, coil["core_bodies"])]
    p = points[sel]
    rotor = {"rotor_centroid": np.zeros((0, 3)), "rotor_volume": np.zeros(0), "rotor_b": np.zeros((0, 3)),
             "rotor_kind": np.zeros(0, dtype=np.int8)}
    groups = coil.get("rotor_loss_bodies") or {}
    chosen = [(ROTOR_LOSS_KINDS[k], b) for k, b in groups.items() if b]
    if chosen:
        mask = np.zeros(len(tets), dtype=bool)
        kind = np.full(len(tets), -1, dtype=np.int8)
        for code, bodies in chosen:
            hit = np.isin(body, bodies)
            mask |= hit
            kind[hit] = code
        q = points[tets[mask]]
        centre = q.mean(axis=1)
        b = fields[name][tets[mask]].mean(axis=1)
        phi = np.arctan2(centre[:, 1], centre[:, 0])
        c, s = np.cos(phi), np.sin(phi)
        a = -math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        rotor = {"rotor_centroid": np.column_stack([ca * centre[:, 0] - sa * centre[:, 1],
                                                    sa * centre[:, 0] + ca * centre[:, 1], centre[:, 2]]),
                 "rotor_volume": tet_volumes(q),
                 "rotor_b": np.column_stack([c * b[:, 0] + s * b[:, 1], -s * b[:, 0] + c * b[:, 1], b[:, 2]]),
                 "rotor_kind": kind[mask]}
    path = os.path.join(posdir, "core_field.npz")
    if eddy_widths_m is not None:
        rotor["rotor_eddy_width_m"] = np.asarray(eddy_widths_m, dtype=float)
    np.savez_compressed(path, centroid=p.mean(axis=1), volume=tet_volumes(p),
                        b=fields[name][sel].mean(axis=1), periodicity=periodicity, angle_deg=angle_deg, **rotor)
    return path


def coil_flux(data, coil, periodicity, turns):
    """
    Flux linked by the whole ring coil, in Wb-turns:
    turns * (1 / conductor area) * integral of the azimuthal vector potential over the coil volume.
    """
    if data is None or not coil["coil_bodies"]:
        return None
    points, tets, body, fields = data
    name = next((n for n in fields if "vector potential" in n and fields[n].ndim == 2), None)
    if name is None:
        return None
    a = fields[name]
    r = np.hypot(points[:, 0], points[:, 1])
    a_phi = (-a[:, 0] * points[:, 1] + a[:, 1] * points[:, 0]) / np.maximum(r, 1e-30)
    sel = tets[np.isin(body, coil["coil_bodies"])]
    integral = float(np.sum(tet_volumes(points[sel]) * a_phi[sel].mean(axis=1)))
    return turns * periodicity * integral / coil["coil_area_m2"]


