"""
Elmer magnetostatics of a 2D cross-section (vector potential A_z, MagnetoDynamics2D). The geometry
is a whole-circle mesh with a region description ("rfm.section2d" builder): coil sides carry the
current density of their phase, magnets a uniform magnetisation, the outer boundary A = 0.

From the solved A (linear triangles):
    torque         Arkkio's method over the air gap: T = L / (mu0 (r_s - r_r)) * integral r B_r B_theta dS
    flux linkage   per turn of each phase: L * sum over its coil sides of sign * share * (mean A over the side)
    fields         flux density of the stator core and of the rotor parts (rotor frame) for the loss model
"""

import math
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET

import numpy as np

from emachine.core.interfaces import FieldSolver
from emachine.core.registry import register
from emachine.core.types import FieldSample
from emachine.io.process import StageError, read_text, run

from .materials import MU0, material_block, material_curve
from .results import read_names
from .sector3d import ANALYSIS_DEFAULTS, ELMER_HOME


def convert_mesh(workdir):
    shutil.rmtree(os.path.join(workdir, "mesh"), ignore_errors=True)
    run([os.path.join(ELMER_HOME, "bin", "ElmerGrid"), "14", "2", "section.msh", "-autoclean",
         "-scale", "0.001", "0.001", "0.001", "-out", "mesh"], workdir, os.path.join(workdir, "convert.log"))


def body_ids(workdir, regions):
    """Body number of every region in the case and in the result file (GeometryIds)."""
    bodies, _ = read_names(workdir)
    missing = [name for name in regions if name not in bodies]
    if missing:
        raise StageError(f"Regions missing from the converted mesh: {missing}")
    return {name: i for i, name in enumerate(sorted(regions, key=lambda name: bodies[name]), start=1)}


def write_case(settings, meta, workdir, ampere_turns):
    """case.sif for the ampere-turns of each phase (one coil, all turns; in A)."""
    regions = meta["regions"]
    bodies, boundaries = read_names(workdir)
    ids = body_ids(workdir, regions)
    order = sorted(ids, key=ids.get)
    curves = {"stator core": material_curve(settings, "stator_core"), "rotor iron": material_curve(settings, "rotor_iron")}
    nonlinear = any(curves.values())
    out = ["! Written by emachine (solvers/elmer/section2d.py).", 'Check Keywords "Warn"\n',
           'Header\n  Mesh DB "." "mesh"\n  Results Directory "results"\nEnd\n',
           "Simulation\n  Max Output Level = 5\n  Coordinate System = Cartesian 2D\n"
           "  Simulation Type = Steady State\n  Steady State Max Iterations = 1\nEnd\n",
           "Constants\n  Permeability of Vacuum = 1.25663706212e-6\nEnd\n"]
    materials = [("air", 1.0, None), ("copper", 1.0, None), ("stator core", settings["stator_core_mu_r"], curves["stator core"]),
                 ("rotor iron", settings["rotor_iron_mu_r"], curves["rotor iron"])]
    material_ids = {name: i + 1 for i, (name, _, _) in enumerate(materials)}
    magnet_blocks, forces = [], []
    for index, name in enumerate(order, start=1):
        region = regions[name]
        lines = [f"Body {index}", f'  Name = "{name}"', f"  Target Bodies(1) = {bodies[name]}", "  Equation = 1"]
        if region["kind"] == "magnet":
            number = len(materials) + len(magnet_blocks) + 1
            mu_magnet = region.get("mu_r", settings["magnet_mu_r"])      # per magnet (ferrite in a PMaSynRM, T59)
            m_region = region.get("remanence_T", settings["magnet_remanence_T"]) / (MU0 * mu_magnet)
            if "magnetization" in region:          # direction given in the plane (axial slices, T55)
                mx, my = (m_region * c for c in region["magnetization"])
            else:                                   # radial: along the magnet's centre line
                phi = math.radians(region["centre_deg"])
                mx, my = m_region * region["direction"] * math.cos(phi), m_region * region["direction"] * math.sin(phi)
            magnet_blocks.append("\n".join([f"Material {number}", f'  Name = "{name}"',
                                            f"  Relative Permeability = {mu_magnet:g}",
                                            f"  Magnetization 1 = Real {mx:.8e}",
                                            f"  Magnetization 2 = Real {my:.8e}",
                                            "  Relative Permittivity = 1", "  Electric Conductivity = 0", "End", ""]))
            lines.append(f"  Material = {number}")
        elif region["kind"] == "coil":
            lines.append(f"  Material = {material_ids['copper']}")
            density = region.get("share", 1.0) * region["sign"] * ampere_turns[region["phase"]] / (region["area_mm2"] * 1e-6)
            forces.append([f'  Name = "{name}"', f"  Current Density = Real {density:.8e}"])
            lines.append(f"  Body Force = {len(forces)}")
        elif region["kind"] == "core":
            lines.append(f"  Material = {material_ids['stator core' if region['side'] == 'stator' else 'rotor iron']}")
        else:
            lines.append(f"  Material = {material_ids['air']}")
        out.append("\n".join(lines) + "\nEnd\n")
    for i, lines in enumerate(forces, start=1):
        out.append(f"Body Force {i}\n" + "\n".join(lines) + "\nEnd\n")
    for name, mu, curve in materials:
        out.append(material_block(material_ids[name], name, mu, curve))
    out += magnet_blocks
    out.append('Equation 1\n  Active Solvers(2) = 1 2\nEnd\n')
    out.append('Solver 1\n  Equation = "MgDyn2D"\n  Variable = "A"\n  Variable DOFs = 1\n'
               '  Procedure = "MagnetoDynamics2D" "MagnetoDynamics2D"\n'
               + (f"  Nonlinear System Max Iterations = {int(settings['nonlinear_max_iterations'])}\n"
                  f"  Nonlinear System Convergence Tolerance = {settings['nonlinear_tolerance']:g}\n"
                  "  Nonlinear System Newton After Iterations = 3\n  Nonlinear System Newton After Tolerance = 1e-3\n"
                  "  Nonlinear System Relaxation Factor = 1\n" if nonlinear else "")
               + '  Linear System Solver = "Direct"\n  Linear System Direct Method = UMFPack\nEnd\n')
    out.append('Solver 2\n  Exec Solver = After All\n  Equation = ResultOutput\n'
               '  Procedure = "ResultOutputSolve" "ResultOutputSolver"\n  Output File Name = fields\n'
               "  Vtu Format = Logical True\n  Ascii Output = Logical True\n  Save Geometry Ids = Logical True\nEnd\n")
    # boundaries of the mesh: "zero" (A = 0), "free" (natural), or periodic onto another boundary (T55)
    conditions = meta.get("boundaries") or {"outer": "zero"}
    names = list(conditions) + [c["periodic"] for c in conditions.values()
                                if isinstance(c, dict) and c["periodic"] not in conditions]
    numbers = {name: i for i, name in enumerate(names, start=1)}
    for name in names:
        lines = [f"Boundary Condition {numbers[name]}", f'  Name = "{name}"', f"  Target Boundaries(1) = {boundaries[name]}"]
        condition = conditions.get(name, "free")
        if condition == "zero":
            lines.append("  A = Real 0")
        elif isinstance(condition, dict):
            lines += [f"  Periodic BC = {numbers[condition['periodic']]}",
                      f"  Periodic BC Translate(3) = Real {condition['dx'] * 1e-3:.10g} 0 0",   # from the target onto this one
                      "  Periodic BC A = Logical True"]
        out.append("\n".join(lines) + "\nEnd\n")
    with open(os.path.join(workdir, "case.sif"), "w") as f:
        f.write("\n".join(out))
    return {"nonlinear": nonlinear, "bodies": {name: i for i, name in enumerate(order, start=1)}}


def read_solution(workdir):
    """Points (m), triangles, body numbers and nodal A of the last result file."""
    files = sorted(f for f in os.listdir(os.path.join(workdir, "results")) if f.endswith(".vtu"))
    if not files:
        raise StageError(f"No result file in {workdir}/results.")
    piece = ET.parse(os.path.join(workdir, "results", files[-1])).getroot().find(".//Piece")

    def array(node):
        return np.array(node.text.split(), dtype=float)

    points = array(piece.find("Points/DataArray")).reshape(-1, 3)[:, :2]
    cells = {a.get("Name"): array(a) for a in piece.find("Cells")}
    types, offsets, conn = cells["types"].astype(int), cells["offsets"].astype(int), cells["connectivity"].astype(int)
    tri = np.array([conn[offsets[i] - 3:offsets[i]] for i in np.where(types == 5)[0]])
    body = {a.get("Name").lower(): array(a) for a in piece.find("CellData")}["geometryids"].astype(int)[types == 5]
    fields = {a.get("Name").lower(): array(a) for a in piece.find("PointData")}
    name = next(n for n in fields if n == "a" or n.startswith("a "))
    return points, tri, body, fields[name]


def triangle_fields(points, tri, potential):
    """Areas (m2), centroids (m) and flux density (Bx, By) of each triangle from the nodal A."""
    p = points[tri]
    a = potential[tri]
    x, y = p[:, :, 0], p[:, :, 1]
    det = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    dadx = ((a[:, 1] - a[:, 0]) * (y[:, 2] - y[:, 0]) - (a[:, 2] - a[:, 0]) * (y[:, 1] - y[:, 0])) / det
    dady = ((x[:, 1] - x[:, 0]) * (a[:, 2] - a[:, 0]) - (x[:, 2] - x[:, 0]) * (a[:, 1] - a[:, 0])) / det
    return np.abs(det) / 2, p.mean(axis=1), np.column_stack([dady, -dadx]), a.mean(axis=1)


@register("solver", "elmer2d")
class ElmerSection2D(FieldSolver):
    """FieldSolver for an "rfm.section2d" mesh. Excitation ampere-turns: one value per phase."""

    def __init__(self, settings=None, core_field=False):
        self.settings = dict(ANALYSIS_DEFAULTS, **(settings or {}))
        self.core_field = core_field

    def solve(self, mesh, excitation, workdir):
        began = time.time()
        meta = mesh.meta
        convert_mesh(workdir)
        case = write_case(self.settings, meta, workdir, list(excitation.ampere_turns))
        shutil.rmtree(os.path.join(workdir, "results"), ignore_errors=True)
        os.makedirs(os.path.join(workdir, "results"))
        run([os.path.join(ELMER_HOME, "bin", "ElmerSolver"), "case.sif"], workdir, os.path.join(workdir, "solve.log"))
        log = read_text(os.path.join(workdir, "solve.log"))
        newton = re.findall(r"ComputeChange: NS \(ITER=(\d+)\) \(NRM,RELC\): \(\s*\S+\s+(\S+)\s*\)", log)
        if case["nonlinear"] and (not newton or float(newton[-1][1]) > self.settings["nonlinear_tolerance"]):
            raise StageError(f"The nonlinear iteration did not converge, see {os.path.join(workdir, 'solve.log')}")

        points, tri, body, potential = read_solution(workdir)
        area, centre, b, a_mean = triangle_fields(points, tri, potential)
        regions, ids = meta["regions"], case["bodies"]
        length = meta["stack_length_mm"] * 1e-3
        radii = meta["radii"]
        r_r, r_s = radii["r_rotor"] * 1e-3, radii["r_stator"] * 1e-3

        gap = np.isin(body, [ids[n] for n, r in regions.items() if r.get("gap")])
        r = np.hypot(centre[gap, 0], centre[gap, 1])
        phi = np.arctan2(centre[gap, 1], centre[gap, 0])
        b_r = b[gap, 0] * np.cos(phi) + b[gap, 1] * np.sin(phi)
        b_t = -b[gap, 0] * np.sin(phi) + b[gap, 1] * np.cos(phi)
        torque = length / (MU0 * (r_s - r_r)) * float(np.sum(area[gap] * r * b_r * b_t))

        phases = len(excitation.ampere_turns)
        flux = [0.0] * phases
        for name, region in regions.items():
            if region["kind"] != "coil":
                continue
            sel = body == ids[name]
            mean = float(np.sum(area[sel] * a_mean[sel]) / np.sum(area[sel]))
            flux[region["phase"]] += region.get("share", 1.0) * region["sign"] * length * mean

        field_file = None
        if self.core_field:
            field_file = self._save_fields(workdir, meta, ids, body, area, centre, b, length, excitation.rotor_angle_deg)
        sample = FieldSample(rotor_angle_deg=excitation.rotor_angle_deg, torque_Nm=torque, flux_linkage_Wb=tuple(flux),
                             field_file=field_file,
                             extras={"elements": meta["mesh"]["elements"], "periodicity": 1,
                                     "core_volume_mm3": regions["stator_core"]["area_mm2"] * meta["stack_length_mm"],
                                     "solver_iterations": -1,
                                     "nonlinear_iterations": int(newton[-1][0]) if (case["nonlinear"] and newton) else 0,
                                     "seconds": round(time.time() - began, 1)})
        if not self.settings["keep_fields"]:
            for f in os.listdir(os.path.join(workdir, "results")):
                if f.endswith(".vtu"):
                    os.remove(os.path.join(workdir, "results", f))
            shutil.rmtree(os.path.join(workdir, "mesh"), ignore_errors=True)
        return sample

    @staticmethod
    def _save_fields(workdir, meta, ids, body, area, centre, b, length, angle_deg):
        """core_field.npz in the format of the 3D solver: stator core, and rotor parts in the rotor frame."""
        regions = meta["regions"]
        stator = body == ids["stator_core"]
        b3 = np.column_stack([b, np.zeros(len(b))])
        c3 = np.column_stack([centre, np.zeros(len(centre))])
        kinds = np.full(len(body), -1, dtype=np.int8)
        kinds[body == ids["rotor_core"]] = 0
        for name, region in regions.items():
            if region["kind"] == "magnet":
                kinds[body == ids[name]] = 2
        rot = kinds >= 0
        phi = np.arctan2(c3[rot, 1], c3[rot, 0])
        c, s = np.cos(phi), np.sin(phi)
        a = -math.radians(angle_deg)
        rotated = np.column_stack([math.cos(a) * c3[rot, 0] - math.sin(a) * c3[rot, 1],
                                   math.sin(a) * c3[rot, 0] + math.cos(a) * c3[rot, 1], np.zeros(int(rot.sum()))])
        pole_pairs = meta["parameters"]["rfm"]["pole_pairs"]
        path = os.path.join(workdir, "core_field.npz")
        np.savez_compressed(path, centroid=c3[stator], volume=area[stator] * length, b=b3[stator], periodicity=1,
                            phases=len({r["phase"] for r in regions.values() if r["kind"] == "coil"}), angle_deg=angle_deg, electrical_period_deg=360.0 / pole_pairs,
                            rotor_centroid=rotated, rotor_volume=area[rot] * length,
                            rotor_b=np.column_stack([c * b3[rot, 0] + s * b3[rot, 1], -s * b3[rot, 0] + c * b3[rot, 1],
                                                     np.zeros(int(rot.sum()))]),
                            rotor_kind=kinds[rot], rotor_eddy_width_m=np.asarray(meta["rotor_eddy_width_mm"]) / 1000.0)
        return path
