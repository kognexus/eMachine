"""
Elmer magnetostatics of the quasi-3D model of the raxial machine ("rafm.quasi3d", T55): the radial
section and every axial slice are 2D problems (MagnetoDynamics2D, as solvers/elmer/section2d.py),
solved one after the other; their torques and flux linkages are summed.

    radial section   torque by Arkkio's method in the radial gap, flux per turn L_r * sum sign * mean A
    axial slice      x = r theta, y = z, depth dr: force on the disc from the Maxwell stress averaged
                     over the axial gap band, F_x = -dr / (mu0 g) * integral Bx By dS; torque r F_x.
                     Both discs (the slice is mirrored at the yoke's mid-plane): torque and flux x 2.

The radial and the axial magnetic circuits are taken as independent (the paper's finding, Zhang et
al. 2023, Section 2.2); the yoke they share is modelled in each part with its own length (B18 is the
3D check).
"""

import math
import os
import re
import shutil
import time

import numpy as np

from emachine.core.interfaces import FieldSolver
from emachine.core.registry import register
from emachine.core.types import FieldSample
from emachine.io.process import StageError, read_text, run

from .materials import MU0
from .section2d import convert_mesh, read_solution, triangle_fields, write_case
from .sector3d import ANALYSIS_DEFAULTS, ELMER_HOME


def solve_part(settings, meta, folder, ampere_turns):
    """Solves one 2D part; returns (torque, flux per turn of each phase, field data for the losses)."""
    convert_mesh(folder)
    case = write_case(settings, meta, folder, ampere_turns)
    shutil.rmtree(os.path.join(folder, "results"), ignore_errors=True)
    os.makedirs(os.path.join(folder, "results"))
    run([os.path.join(ELMER_HOME, "bin", "ElmerSolver"), "case.sif"], folder, os.path.join(folder, "solve.log"))
    log = read_text(os.path.join(folder, "solve.log"))
    newton = re.findall(r"ComputeChange: NS \(ITER=(\d+)\) \(NRM,RELC\): \(\s*\S+\s+(\S+)\s*\)", log)
    if case["nonlinear"] and (not newton or float(newton[-1][1]) > settings["nonlinear_tolerance"]):
        raise StageError(f"The nonlinear iteration did not converge, see {os.path.join(folder, 'solve.log')}")
    points, tri, body, potential = read_solution(folder)
    area, centre, b, a_mean = triangle_fields(points, tri, potential)
    regions, ids = meta["regions"], case["bodies"]
    depth = meta["stack_length_mm"] * 1e-3
    gap = np.isin(body, [ids[n] for n, r in regions.items() if r.get("gap")])
    if meta["part"] == "radial":
        r_r, r_s = meta["radii"]["r_rotor"] * 1e-3, meta["radii"]["r_stator"] * 1e-3
        r = np.hypot(centre[gap, 0], centre[gap, 1])
        phi = np.arctan2(centre[gap, 1], centre[gap, 0])
        b_r = b[gap, 0] * np.cos(phi) + b[gap, 1] * np.sin(phi)
        b_t = -b[gap, 0] * np.sin(phi) + b[gap, 1] * np.cos(phi)
        torque = depth / (MU0 * (r_s - r_r)) * float(np.sum(area[gap] * r * b_r * b_t))
        mirror = 1.0
    else:
        frame = meta["frame"]
        g = (frame["gap_y1"] - frame["gap_y0"]) * 1e-3
        force = -depth / (MU0 * g) * float(np.sum(area[gap] * b[gap, 0] * b[gap, 1]))
        torque = frame["radius"] * 1e-3 * force
        mirror = 2.0                               # the other disc, mirrored at z = 0
    phases = len(ampere_turns)
    flux = [0.0] * phases
    for name, region in regions.items():
        if region["kind"] != "coil":
            continue
        sel = body == ids[name]
        mean = float(np.sum(area[sel] * a_mean[sel]) / np.sum(area[sel]))
        flux[region["phase"]] += region.get("share", 1.0) * region["sign"] * depth * mean
    data = {"area": area, "centre": centre, "b": b, "body": body, "ids": ids, "depth": depth, "mirror": mirror,
            "newton": int(newton[-1][0]) if (case["nonlinear"] and newton) else 0}
    return mirror * torque, [mirror * f for f in flux], data


def to_3d(meta, centre, b):
    """Element centroids (m) and flux densities in machine coordinates (x, y, z)."""
    if meta["part"] == "radial":
        return (np.column_stack([centre, np.zeros(len(centre))]), np.column_stack([b, np.zeros(len(b))]))
    frame = meta["frame"]
    r = frame["radius"] * 1e-3
    theta = centre[:, 0] / r + frame["theta0_rad"]
    c, s = np.cos(theta), np.sin(theta)
    xyz = np.column_stack([r * c, r * s, centre[:, 1]])
    b3 = np.column_stack([-s * b[:, 0], c * b[:, 0], b[:, 1]])      # b_x is along theta, b_y along z
    return xyz, b3


@register("solver", "elmer_quasi3d")
class ElmerQuasi3D(FieldSolver):
    """FieldSolver for a "rafm.quasi3d" mesh. Excitation ampere-turns: one value per phase."""

    def __init__(self, settings=None, core_field=False):
        self.settings = dict(ANALYSIS_DEFAULTS, **(settings or {}))
        self.core_field = core_field

    def solve(self, mesh, excitation, workdir):
        began = time.time()
        torque, flux, parts = 0.0, None, []
        shares = {}
        for meta in mesh.meta["parts"]:
            folder = os.path.join(workdir, meta["folder"])
            t, f, data = solve_part(self.settings, meta, folder, list(excitation.ampere_turns))
            torque += t
            flux = f if flux is None else [x + y for x, y in zip(flux, f)]
            shares[meta["folder"]] = {"torque_Nm": t, "flux_Wb": f}
            parts.append((meta, data))
            if not self.settings["keep_fields"]:
                for name in os.listdir(os.path.join(folder, "results")):
                    if name.endswith(".vtu"):
                        os.remove(os.path.join(folder, "results", name))
                shutil.rmtree(os.path.join(folder, "mesh"), ignore_errors=True)
        core_volume = sum(float(np.sum(d["area"][d["body"] == d["ids"]["stator_core"]])) * d["depth"] * d["mirror"]
                          for _, d in parts) * 1e9
        field_file = self._save_fields(workdir, mesh.meta, parts, excitation.rotor_angle_deg) if self.core_field else None
        return FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=torque, flux_linkage_Wb=tuple(flux),
                           field_file=field_file,
                           extras={"elements": mesh.meta["mesh"]["elements"], "periodicity": 1,
                                   "core_volume_mm3": core_volume, "solver_iterations": -1,
                                   "nonlinear_iterations": max(d["newton"] for _, d in parts),
                                   "parts": shares, "seconds": round(time.time() - began, 1)})

    @staticmethod
    def _save_fields(workdir, meta, parts, angle_deg):
        """core_field.npz as the 3D solver writes it: the stator core of all parts, and the rotor parts in
        the rotor frame; volumes include the depth of each part (and the mirrored disc)."""
        stator_c, stator_v, stator_b, rotor_c, rotor_v, rotor_b, rotor_k = [], [], [], [], [], [], []
        a = -math.radians(angle_deg)
        for part, d in parts:
            xyz, b3 = to_3d(part, d["centre"], d["b"])
            volume = d["area"] * d["depth"] * d["mirror"]
            st = d["body"] == d["ids"]["stator_core"]
            stator_c.append(xyz[st]), stator_v.append(volume[st]), stator_b.append(b3[st])
            kinds = np.full(len(d["body"]), -1, dtype=np.int8)
            kinds[d["body"] == d["ids"]["rotor_core"]] = 0
            for name, region in part["regions"].items():
                if region["kind"] == "magnet":
                    kinds[d["body"] == d["ids"][name]] = 2
            rot = kinds >= 0
            phi = np.arctan2(xyz[rot, 1], xyz[rot, 0])
            c, s = np.cos(phi), np.sin(phi)
            rotor_c.append(np.column_stack([math.cos(a) * xyz[rot, 0] - math.sin(a) * xyz[rot, 1],
                                            math.sin(a) * xyz[rot, 0] + math.cos(a) * xyz[rot, 1], xyz[rot, 2]]))
            rotor_v.append(volume[rot])
            rotor_b.append(np.column_stack([c * b3[rot, 0] + s * b3[rot, 1], -s * b3[rot, 0] + c * b3[rot, 1], b3[rot, 2]]))
            rotor_k.append(kinds[rot])
        p = meta["parameters"]["rafm"]
        path = os.path.join(workdir, "core_field.npz")
        np.savez_compressed(path, centroid=np.concatenate(stator_c), volume=np.concatenate(stator_v),
                            b=np.concatenate(stator_b), periodicity=1, phases=1 + max(c["phase"] for c in p["coils"]),
                            angle_deg=angle_deg, electrical_period_deg=360.0 / p["pole_pairs"],
                            rotor_centroid=np.concatenate(rotor_c), rotor_volume=np.concatenate(rotor_v),
                            rotor_b=np.concatenate(rotor_b), rotor_kind=np.concatenate(rotor_k),
                            rotor_eddy_width_m=np.array([p["rotor_iron"], p["rotor_iron"],
                                                         p["magnet_thickness"]]) / 1000.0)
        return path
