"""
Elmer magnetostatics of "section2d" meshes (T59, T60): a radial section with any number of air gaps,
or the unrolled slices of an axial machine; every part is a 2D problem (MagnetoDynamics2D, the case
writer of section2d.py), and torque and flux linkage are the sums over the parts.

    radial gap r1..r2   torque on the inner body  T = L / (mu0 (r2 - r1)) * integral r B_r B_theta dS,
                        on the outer body the opposite (Arkkio)
    axial gap y0..y1    force on the body below   F_x = dr / (mu0 g) * integral B_x B_y dS (Maxwell
                        stress averaged over the band), on the body above the opposite; torque r F_x
    flux per turn       per phase: depth * sum over its coil sides of sign * share * (mean A over the side)

With `core_field` the flux density of the stator core and of the rotor parts (rotor frame) is saved
for the loss model (core_field.npz, the format of the other solvers), and with `keep_fields` the
element data of every part (fields.npz) for the ParaView export.
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


def gap_torques(meta, ids, body, area, centre, b):
    """Torque on the rotor from every air gap of a part (list, one per gap)."""
    regions = meta["regions"]
    depth = meta["stack_length_mm"] * 1e-3
    geo = meta["geometry"]
    out = []
    for g in geo["gaps"]:
        names = [n for n, r in regions.items() if r.get("gap") == g["index"]]
        sel = np.isin(body, [ids[n] for n in names])
        if geo["kind"] == "radial":
            r1, r2 = g["r1"] * 1e-3, g["r2"] * 1e-3
            r = np.hypot(centre[sel, 0], centre[sel, 1])
            phi = np.arctan2(centre[sel, 1], centre[sel, 0])
            b_r = b[sel, 0] * np.cos(phi) + b[sel, 1] * np.sin(phi)
            b_t = -b[sel, 0] * np.sin(phi) + b[sel, 1] * np.cos(phi)
            t = depth / (MU0 * (r2 - r1)) * float(np.sum(area[sel] * r * b_r * b_t))
            out.append(t if g["rotor"] == "inner" else -t)
        else:
            gap = (g["y1"] - g["y0"]) * 1e-3
            force = depth / (MU0 * gap) * float(np.sum(area[sel] * b[sel, 0] * b[sel, 1]))
            t = geo["radius"] * 1e-3 * force
            out.append(t if g["rotor"] == "below" else -t)
    return out


def coil_fluxes(meta, ids, body, area, a_mean, phases):
    depth = meta["stack_length_mm"] * 1e-3
    flux = [0.0] * phases
    for name, region in meta["regions"].items():
        if region["kind"] != "coil":
            continue
        sel = body == ids[name]
        mean = float(np.sum(area[sel] * a_mean[sel]) / np.sum(area[sel]))
        flux[region["phase"]] += region.get("share", 1.0) * region["sign"] * depth * mean
    return flux


def solve_part(settings, meta, folder, ampere_turns):
    if not (settings.get("reuse_mesh") and os.path.isfile(os.path.join(folder, "mesh", "mesh.header"))):
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
    ids = case["bodies"]
    torques = gap_torques(meta, ids, body, area, centre, b)
    flux = coil_fluxes(meta, ids, body, area, a_mean, len(ampere_turns))
    data = {"points": points, "tri": tri, "potential": potential, "area": area, "centre": centre, "b": b, "body": body,
            "ids": ids, "depth": meta["stack_length_mm"] * 1e-3,
            "newton": int(newton[-1][0]) if (case["nonlinear"] and newton) else 0}
    return torques, flux, data


def machine_coordinates(meta, centre, b):
    """Element centroids (m) and flux densities in machine coordinates (x, y, z)."""
    geo = meta["geometry"]
    if geo["kind"] == "radial":
        return np.column_stack([centre, np.zeros(len(centre))]), np.column_stack([b, np.zeros(len(b))])
    r = geo["radius"] * 1e-3
    theta = centre[:, 0] / r
    c, s = np.cos(theta), np.sin(theta)
    return np.column_stack([r * c, r * s, centre[:, 1]]), np.column_stack([-s * b[:, 0], c * b[:, 0], b[:, 1]])


@register("solver", "elmer_sections")
class ElmerSections(FieldSolver):
    """FieldSolver for "section2d" meshes. Excitation ampere-turns: one value per phase (all phases at once)."""

    def __init__(self, settings=None, core_field=False):
        self.settings = dict(ANALYSIS_DEFAULTS, **(settings or {}))
        self.core_field = core_field

    def solve(self, mesh, excitation, workdir):
        began = time.time()
        phases = len(excitation.ampere_turns)
        sourceless = not any(excitation.ampere_turns) and not any(
            r["kind"] == "magnet" for part in mesh.meta["parts"] for r in part["regions"].values())
        if sourceless and not self.core_field:      # no current, no magnet: no field (the nonlinear solver would stall)
            return FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=0.0, flux_linkage_Wb=(0.0,) * phases,
                               extras={"elements": mesh.meta["mesh"]["elements"], "periodicity": 1, "core_volume_mm3": 0.0,
                                       "solver_iterations": 0, "nonlinear_iterations": 0, "seconds": 0.0,
                                       "gap_torques_Nm": []})
        torque, flux, parts, per_gap = 0.0, [0.0] * phases, [], []
        for meta in mesh.meta["parts"]:
            folder = os.path.join(workdir, meta["folder"])
            torques, f, data = solve_part(self.settings, meta, folder, list(excitation.ampere_turns))
            torque += sum(torques)
            per_gap.append(torques)
            flux = [x + y for x, y in zip(flux, f)]
            parts.append((meta, data))
            if self.settings.get("keep_fields"):
                np.savez_compressed(os.path.join(folder, "fields.npz"), points=data["points"], tri=data["tri"],
                                    potential=data["potential"], body=data["body"],
                                    names=np.array(sorted(data["ids"], key=data["ids"].get)))
            for name in os.listdir(os.path.join(folder, "results")):
                if name.endswith(".vtu"):
                    os.remove(os.path.join(folder, "results", name))
            if not self.settings.get("reuse_mesh"):
                shutil.rmtree(os.path.join(folder, "mesh"), ignore_errors=True)
        core_volume = sum(float(np.sum(d["area"][d["body"] == d["ids"]["stator_core"]])) * d["depth"]
                          for _, d in parts if "stator_core" in d["ids"]) * 1e9
        field_file = self._save_fields(workdir, mesh.meta, parts, excitation.rotor_angle_deg, phases) \
            if self.core_field else None
        return FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=torque, flux_linkage_Wb=tuple(flux),
                           field_file=field_file,
                           extras={"elements": mesh.meta["mesh"]["elements"], "periodicity": 1, "gap_torques_Nm": per_gap,
                                   "core_volume_mm3": core_volume, "solver_iterations": -1,
                                   "nonlinear_iterations": max(d["newton"] for _, d in parts),
                                   "seconds": round(time.time() - began, 2)})

    @staticmethod
    def _save_fields(workdir, meta, parts, angle_deg, phases):
        stator_c, stator_v, stator_b, rotor_c, rotor_v, rotor_b, rotor_k = [], [], [], [], [], [], []
        a = -math.radians(angle_deg)
        for part, d in parts:
            xyz, b3 = machine_coordinates(part, d["centre"], d["b"])
            volume = d["area"] * d["depth"]
            if "stator_core" in d["ids"]:
                st = d["body"] == d["ids"]["stator_core"]
                stator_c.append(xyz[st]), stator_v.append(volume[st]), stator_b.append(b3[st])
            kinds = np.full(len(d["body"]), -1, dtype=np.int8)
            if "rotor_core" in d["ids"]:
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
        params = meta["parameters"]
        if not stator_c:                     # coreless stator: no core loss
            stator_c, stator_v, stator_b = [np.zeros((0, 3))], [np.zeros(0)], [np.zeros((0, 3))]
        path = os.path.join(workdir, "core_field.npz")
        np.savez_compressed(path, centroid=np.concatenate(stator_c), volume=np.concatenate(stator_v),
                            b=np.concatenate(stator_b), periodicity=1, phases=phases, angle_deg=angle_deg,
                            electrical_period_deg=360.0 / params["electrical_pole_pairs"],
                            rotor_centroid=np.concatenate(rotor_c), rotor_volume=np.concatenate(rotor_v),
                            rotor_b=np.concatenate(rotor_b), rotor_kind=np.concatenate(rotor_k),
                            rotor_eddy_width_m=np.asarray(params["rotor_eddy_width_mm"]) / 1000.0)
        return path
