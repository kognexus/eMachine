"""
Field export for ParaView of a machine solved on its 2D cross-section (geometry "rfm.section2d").

One full electrical period is solved with the fields kept, loaded (all phases) and at no load. The
triangles of every rotor position are extruded to wedges over the stack length (z from -L/2 to
L/2), so the files are those of the TFM export (fieldexport.py) and the same views open them:

    machine.pvd, air.pvd, airgap.pvd   time series, one step per rotor position
    core_loss.vtu                      stator core: peak flux density and loss density
    full_ring.vtu                      the whole section at the step of highest torque

The section holds every phase, so full_ring.vtu already is the whole machine (summary key
`ring_has_all_phases`). Besides the arrays of the TFM export the files carry `phase` (1..m on the
coil sides, 0 elsewhere) and `A_z`, the vector potential, whose contour lines are the flux lines.

Lengths in the written files are millimetres; fields are in SI units unless the name says otherwise.
"""

import json
import math
import os
import shutil

import numpy as np

from emachine.core import registry
from emachine.core.types import Excitation, GeometryRequest
from emachine.io import vtk as vtkio
from emachine.physics import losses, torque
from emachine.physics import winding as winding_model
from emachine.pipeline import design_space as design
from emachine.pipeline.evaluate import temperatures
from emachine.pipeline.sweep import run_positions
from emachine.solvers.elmer import materials
from emachine.solvers.elmer.section2d import body_ids, read_solution, triangle_fields
from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS

from .fieldexport import MATERIAL_IDS, MU0, ExportError, permeability, slope_full_period

#: samples around the circle in the middle of the air gap
GAP_SAMPLES = 720


# ----------------------------------------------------------------------------- geometry helpers

def extrude(points, triangles, length_mm):
    """
    Triangles in the plane extruded to wedges from z = -L/2 to L/2. Returns (points (2n, 3),
    wedges (m, 6)): the points of the bottom layer, then those of the top layer. The base triangle
    of every wedge runs counter-clockwise seen from +z, its normal pointing towards the top
    triangle: that is what VTK computes a positive volume for (checked with vtkCellSizeFilter and
    vtkMeshQuality in ParaView 6.2; the class documentation of vtkWedge says the opposite).
    """
    points = np.asarray(points, dtype=float)[:, :2]
    tri = np.array(triangles, dtype=np.int64)
    p = points[tri]
    ccw = ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
           - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1])) > 0
    tri[~ccw] = tri[~ccw][:, [0, 2, 1]]
    n = len(points)
    layer = lambda z: np.column_stack([points, np.full(n, z)])
    return np.vstack([layer(-length_mm / 2), layer(length_mm / 2)]), np.hstack([tri, tri + n])


def sample_circle(points, triangles, cell_values, radius, count=GAP_SAMPLES):
    """
    Values of the triangles that hold `count` points on a circle of `radius` (angles 0, 360/count,
    ... degrees). Returns (angles in degrees, values of the holding triangles).
    """
    points = np.asarray(points, dtype=float)[:, :2]
    p = points[np.asarray(triangles)]
    theta = np.arange(count) * 360.0 / count
    q = radius * np.column_stack([np.cos(np.radians(theta)), np.sin(np.radians(theta))])
    r = np.hypot(p[..., 0], p[..., 1])
    reach = np.flatnonzero((r.min(axis=1) <= radius * (1 + 1e-9)) & (r.max(axis=1) >= radius * (1 - 1e-9)))
    a, v0, v1 = p[reach, 0], p[reach, 1] - p[reach, 0], p[reach, 2] - p[reach, 0]
    det = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    holder = np.full(count, -1, dtype=np.int64)
    eps = 1e-9
    for start in range(0, count, 64):
        d = q[start:start + 64, None, :] - a[None]
        l1 = (d[..., 0] * v1[:, 1] - d[..., 1] * v1[:, 0]) / det
        l2 = (v0[:, 0] * d[..., 1] - v0[:, 1] * d[..., 0]) / det
        inside = (l1 >= -eps) & (l2 >= -eps) & (l1 + l2 <= 1 + eps)
        holder[start:start + 64] = np.where(inside.any(axis=1), reach[inside.argmax(axis=1)], -1)
    lost = holder < 0
    if np.any(lost):                                  # outside every triangle (rounding): nearest centroid
        centre = p.mean(axis=1)
        holder[lost] = [int(np.argmin(np.sum((centre - x) ** 2, axis=1))) for x in q[lost]]
    return theta, np.asarray(cell_values)[holder]


def nodal_average(count, triangles, area, values):
    """Area-weighted mean of the triangle values at every point."""
    values = np.asarray(values, dtype=float)
    flat = values.reshape(len(values), -1)
    total = np.zeros((count, flat.shape[1]))
    weight = np.zeros(count)
    for corner in range(3):
        np.add.at(total, triangles[:, corner], flat * area[:, None])
        np.add.at(weight, triangles[:, corner], area)
    mean = total / np.maximum(weight, 1e-300)[:, None]
    return mean.reshape((count,) + values.shape[1:])


def cylinder(radius, length_mm, theta_deg):
    """Points (2 n, 3) and quadrilaterals of a closed cylinder through the angles `theta_deg`."""
    phi = np.radians(theta_deg)
    n = len(phi)
    ring = np.column_stack([radius * np.cos(phi), radius * np.sin(phi)])
    points = np.vstack([np.column_stack([ring, np.full(n, -length_mm / 2)]),
                        np.column_stack([ring, np.full(n, length_mm / 2)])])
    i = np.arange(n)
    quads = np.column_stack([i, (i + 1) % n, n + (i + 1) % n, n + i])
    return points, quads


def polar(b, x, y):
    """Radial and tangential components of in-plane vectors b at the points (x, y)."""
    phi = np.arctan2(y, x)
    c, s = np.cos(phi), np.sin(phi)
    return b[:, 0] * c + b[:, 1] * s, -b[:, 0] * s + b[:, 1] * c


# ----------------------------------------------------------------------------- one rotor position

def material_of(region):
    if region["kind"] == "coil":
        return "copper"
    if region["kind"] == "magnet":
        return "magnet"
    if region["kind"] == "core":
        return "stator core" if region["side"] == "stator" else "rotor iron"
    return "air"


def read_position(posdir, meta, analysis, ampere_turns):
    """Mesh, fields and per-element quantities of one solved rotor position (points in mm, 2D)."""
    try:
        points, tri, body, potential = read_solution(posdir)
    except Exception as error:
        raise ExportError(f"No field file in {posdir}: {error}") from error
    ids = body_ids(posdir, meta["regions"])
    area, centre, b, _ = triangle_fields(points, tri, potential)
    b_abs = np.linalg.norm(b, axis=1)

    count = len(tri)
    material = np.zeros(count, dtype=np.int64)
    side = np.zeros(count, dtype=np.int64)
    phase = np.zeros(count, dtype=np.int64)
    solid = np.zeros(count, dtype=bool)
    mu = np.ones(count)
    saturation = np.zeros(count)
    magnetisation = np.zeros((count, 3))
    along = np.zeros(count)
    current = np.zeros((count, 3))
    curves = {"stator core": materials.material_curve(analysis, "stator_core"),
              "rotor iron": materials.material_curve(analysis, "rotor_iron")}
    linear = {"air": 1.0, "copper": 1.0, "magnet": analysis["magnet_mu_r"], "stator core": analysis["stator_core_mu_r"],
              "rotor iron": analysis["rotor_iron_mu_r"]}
    m0 = analysis["magnet_remanence_T"] / (MU0 * analysis["magnet_mu_r"])
    names = {}
    for name, region in meta["regions"].items():
        number = ids[name]
        sel = body == number
        kind = material_of(region)
        names[number] = (name, kind, region)
        material[sel] = MATERIAL_IDS[kind]
        side[sel] = 1 if region["side"] == "rotor" else 0
        solid[sel] = region["kind"] != "air"
        mu[sel], saturation[sel] = permeability(b_abs[sel], curves.get(kind), linear[kind])
        if region["kind"] == "magnet":
            if "magnetization" in region:          # axial slice of the raxial machine: given in the plane
                direction = np.array([region["magnetization"][0], region["magnetization"][1], 0.0])
            else:
                phi = math.radians(region["centre_deg"])
                direction = region["direction"] * np.array([math.cos(phi), math.sin(phi), 0.0])
            magnetisation[sel] = m0 * direction
            along[sel] = b[sel] @ direction[:2]
        elif region["kind"] == "coil":
            phase[sel] = region["phase"] + 1
            current[sel, 2] = region.get("share", 1.0) * region["sign"] * ampere_turns[region["phase"]] / region["area_mm2"]  # A/mm2

    nodal_b = nodal_average(len(points), tri, area, b)
    b_r, b_t = polar(nodal_b, points[:, 0], points[:, 1])
    return {
        "meta": meta, "names": names, "body": body, "ids": ids,
        "points": points * 1e3, "cells": tri, "solid": solid, "area_mm2": area * 1e6, "b": b,
        "point_data": {"B": np.column_stack([nodal_b, np.zeros(len(points))]),
                       "B_magnitude": np.linalg.norm(nodal_b, axis=1), "B_radial": b_r, "B_tangential": b_t,
                       "A_z": potential},
        "cell_data": {"region": body.astype(np.int64), "material": material, "side": side, "phase": phase,
                      "B_cell": np.column_stack([b, np.zeros(count)]), "mu_r": mu, "saturation": saturation,
                      "magnetization": magnetisation, "B_along_magnetization": along, "current_density": current},
    }


def extruded(step, mask, length_mm, point_names=None, cell_names=None):
    """The cells of `mask` extruded over the stack: (points, wedges, point data, cell data)."""
    pd = {n: a for n, a in step["point_data"].items() if point_names is None or n in point_names}
    cd = {n: a for n, a in step["cell_data"].items() if cell_names is None or n in cell_names}
    p, c, pd, cd = vtkio.subset(step["points"], step["cells"], mask, pd, cd)
    p3, wedges = extrude(p, c, length_mm)
    return p3, wedges, {n: np.concatenate([a, a]) for n, a in pd.items()}, cd


def gap_profile(step):
    """(angles in degrees, in-plane flux density) around the middle of the air gap, from the gap triangles."""
    gap = np.isin(step["body"], [n for n, (_, _, region) in step["names"].items() if region.get("gap")])
    radius = step["meta"]["radii"]["r_middle"]
    return sample_circle(step["points"], step["cells"][gap], step["b"][gap], radius)


def write_step(outdir, k, step, info, length_mm, skip_air=False):
    """Writes the files of one step. Returns ({series name: file path}, (angles, radial flux density in the gap))."""
    files = {}
    parts = [("machine", step["solid"], None)]
    if not skip_air:
        parts.append(("air", ~step["solid"], ("region", "material", "side", "B_cell")))
    for name, mask, cell_names in parts:
        p, c, pd, cd = extruded(step, mask, length_mm, None, cell_names)
        files[name] = os.path.join(outdir, name, f"{name}_{k:03d}.vtu")
        vtkio.write_vtu(files[name], p, c, vtkio.WEDGE, pd, cd, info)
    theta, b = gap_profile(step)
    radius = step["meta"]["radii"]["r_middle"]
    p, quads = cylinder(radius, length_mm, theta)
    b_r, b_t = polar(b, np.cos(np.radians(theta)), np.sin(np.radians(theta)))
    data = {"B": np.column_stack([b, np.zeros(len(b))]), "B_magnitude": np.linalg.norm(b, axis=1),
            "B_radial": b_r, "B_tangential": b_t, "theta_deg": theta}
    files["airgap"] = os.path.join(outdir, "airgap", f"airgap_{k:03d}.vtu")
    vtkio.write_vtu(files["airgap"], p, quads, vtkio.QUAD, {n: np.concatenate([a, a]) for n, a in data.items()},
                    None, info)
    return files, (theta, b_r)


# ----------------------------------------------------------------------------- axial slices (raxial machine, T56)

def wrap_slice(step, mask, meta, mirror=False):
    """Cells of an axial slice (x = r theta, y = z) as wedges on the ring r +- dr/2 at its radius, in
    machine coordinates (mm); mirror: the slice of the other disc (z -> -z). Returns (points, wedges,
    point data, cell data) with vectors turned into machine coordinates."""
    frame = meta["frame"]
    r, dr, theta0 = frame["radius"], frame["depth"], frame["theta0_rad"]
    pd = {"B": step["point_data"]["B"], "B_magnitude": step["point_data"]["B_magnitude"]}
    cd = {n: step["cell_data"][n] for n in ("region", "material", "side", "phase", "saturation", "B_cell",
                                            "current_density")}
    p, c, pd, cd = vtkio.subset(step["points"], step["cells"], mask, pd, cd)
    p3, wedges = extrude(p, c, dr)                       # x, y and the radial offset in z
    theta = p3[:, 0] / r + theta0
    radius = r + p3[:, 2]
    sign = -1.0 if mirror else 1.0
    xyz = np.column_stack([radius * np.cos(theta), radius * np.sin(theta), sign * p3[:, 1]])
    if mirror:                                           # a mirror image turns the cells inside out
        wedges = wedges[:, [0, 2, 1, 3, 5, 4]]

    def turn(vectors, angles, flip):                     # (b_theta, b_z) -> machine x, y, z
        c_, s_ = np.cos(angles), np.sin(angles)
        return np.column_stack([-s_ * vectors[:, 0], c_ * vectors[:, 0], flip * vectors[:, 1]])
    b_point = np.concatenate([pd["B"], pd["B"]])
    out_pd = {"B": turn(b_point, theta, -1.0 if mirror else 1.0), "B_magnitude": np.concatenate([pd["B_magnitude"]] * 2)}
    centres = p3[wedges].mean(axis=1)
    cell_theta = centres[:, 0] / r + theta0
    out_cd = dict(cd)
    out_cd["B_cell"] = turn(cd["B_cell"], cell_theta, -1.0 if mirror else 1.0)
    # the coil end sides carry current along r (out of the slice plane); the mirrored side the other way
    current = cd["current_density"][:, 2] * (-1.0 if mirror else 1.0)
    out_cd["current_density"] = np.column_stack([current * np.cos(cell_theta), current * np.sin(cell_theta),
                                                 np.zeros(len(current))])
    return xyz, wedges, out_pd, out_cd


def axial_parts(posdir):
    return sorted(d for d in os.listdir(posdir) if d.startswith("axial") and os.path.isdir(os.path.join(posdir, d)))


def write_axial(outdir, k, posdir, analysis, ampere_turns, info):
    """The axial slices of one step on both discs as one file axial/axial_<k>.vtu (solid parts)."""
    pieces = []
    for name in axial_parts(posdir):
        folder = os.path.join(posdir, name)
        with open(os.path.join(folder, "section.regions.json")) as f:
            meta = json.load(f)
        step = read_position(folder, meta, analysis, ampere_turns)
        for mirror in (False, True):
            pieces.append(wrap_slice(step, step["solid"], meta, mirror))
    path = os.path.join(outdir, "axial", f"axial_{k:03d}.vtu")
    points, cells, pd, cd = merge(pieces)
    vtkio.write_vtu(path, points, cells, vtkio.WEDGE, pd, cd, info)
    return path


def write_axial_core(outdir, posdir, analysis, peak, density, material):
    """core_loss_axial.vtu: peak flux density and loss density of the axial slices (both discs)."""
    pieces, offset = [], 0
    p_all, d_all = [], []
    for name in axial_parts(posdir):
        folder = os.path.join(posdir, name)
        with open(os.path.join(folder, "section.regions.json")) as f:
            meta = json.load(f)
        step = read_position(folder, meta, analysis, np.zeros(1 + max(r["phase"] for r in meta["regions"].values()
                                                                     if r["kind"] == "coil")))
        mask = step["body"] == step["ids"]["stator_core"]
        n = int(mask.sum())
        for mirror in (False, True):
            xyz, wedges, _, cd = wrap_slice(step, mask, meta, mirror)
            pieces.append((xyz, wedges, {}, {"region": cd["region"]}))
            p_all.append(peak[offset:offset + n]), d_all.append(density[offset:offset + n])
        offset += n
    points, cells, _, cd = merge(pieces)
    d = np.concatenate(d_all)
    cd.update({"B_peak": np.concatenate(p_all), "loss_density_W_per_kg": d,
               "loss_density_W_per_m3": d * material["density_kg_m3"]})
    vtkio.write_vtu(os.path.join(outdir, "core_loss_axial.vtu"), points, cells, vtkio.WEDGE, None, cd)


def merge(pieces):
    """Joins (points, cells, point data, cell data) pieces with the same arrays into one."""
    points, cells, pdata, cdata, offset = [], [], {}, {}, 0
    for p, c, pd, cd in pieces:
        points.append(p)
        cells.append(c + offset)
        offset += len(p)
        for n, a in (pd or {}).items():
            pdata.setdefault(n, []).append(a)
        for n, a in (cd or {}).items():
            cdata.setdefault(n, []).append(a)
    return (np.vstack(points), np.vstack(cells), {n: np.concatenate(a) for n, a in pdata.items()} or None,
            {n: np.concatenate(a) for n, a in cdata.items()} or None)


def shares_of(samples):
    """Mean torque of each part of the quasi-3D model (radial section, axial slices with both discs)."""
    names = samples[0].extras["parts"].keys()
    return {n: float(np.mean([s.extras["parts"][n]["torque_Nm"] for s in samples])) for n in names}


# ----------------------------------------------------------------------------- the sweeps

def phase_ampere_turns(peak, steps, phases, current_angle_deg=0.0):
    """Ampere-turns of every phase at `steps` positions over one electrical period, as in the
    evaluation sweep: phase k carries -peak sin(theta - 2 pi k / m + beta)."""
    theta = 2 * math.pi * np.arange(steps) / steps
    beta = math.radians(current_angle_deg)
    return np.column_stack([-peak * np.sin(theta - 2 * math.pi * k / phases + beta) for k in range(phases)])


def sweep_period(parameters, analysis, workdir, ampere_turns, jobs, core_field, geometry="rfm.section2d",
                 solver="elmer2d"):
    """Solves the positions of one electrical period (rows of `ampere_turns`), fields kept.
    Returns (rotor angles in degrees, field samples in the order of the angles)."""
    p = int(parameters["sweep"]["pole_pairs"])
    steps = len(ampere_turns)
    angles = (360.0 / p) * np.arange(steps) / steps
    builder = registry.create("geometry", geometry)
    field_solver = registry.create("solver", solver, settings=analysis, core_field=core_field)
    request = GeometryRequest(geometry, parameters)

    def task(angle, posdir, index):
        os.makedirs(posdir, exist_ok=True)
        mesh = builder.build(request, angle, posdir)
        at = tuple(float(v) for v in ampere_turns[int(index)])
        return field_solver.solve(mesh, Excitation(rotor_angle_deg=angle, ampere_turns=at), posdir)

    shutil.rmtree(workdir, ignore_errors=True)
    samples, failed = run_positions(task, angles, workdir, jobs, currents=np.arange(steps))
    if failed:
        raise ExportError(f"{len(failed)} of {steps} rotor positions failed in {workdir}: {failed[0][1].splitlines()[0]}")
    return angles, samples


# ----------------------------------------------------------------------------- the export

def export(spec, values, outdir, turns=None, no_load=True, skip_air=False, keep_raw=False, log=print):
    """
    Runs the sweeps and writes every field file of the export. Returns a dictionary with the
    waveforms, key numbers and file names, with the keys of fieldexport.export (summary.json).
    """
    log = log or (lambda *a, **k: None)
    os.makedirs(outdir, exist_ok=True)
    for name in ("machine", "air", "airgap"):
        shutil.rmtree(os.path.join(outdir, name), ignore_errors=True)
    machine = design.machine_of(spec)
    d = machine.derive(spec, values)
    request = machine.geometry(spec, values)
    if request.kind not in ("rfm.section2d", "rafm.quasi3d"):
        raise ExportError(f"The section export needs a 2D section geometry, not {request.kind}.")
    hybrid = request.kind == "rafm.quasi3d"          # raxial machine (T56): radial section and axial slices
    geometry, solver = (("rafm.quasi3d", "elmer_quasi3d") if hybrid else ("rfm.section2d", "elmer2d"))
    shutil.rmtree(os.path.join(outdir, "axial"), ignore_errors=True)
    parameters = request.parameters
    plan = parameters["sweep"]
    analysis = dict(ANALYSIS_DEFAULTS)
    analysis.update(parameters["analysis"])
    analysis.update({"coil_turns": 1, "keep_fields": True})
    phases, p = int(plan["phases"]), int(plan["pole_pairs"])
    positions = int(spec["fidelity"]["positions"])
    steps = 2 * positions
    length = float(parameters["rafm"]["radial_tooth_length"] if hybrid else parameters["rfm"]["stack_length"])
    ni_peak = d["ampere_turns_peak"]
    jobs = int(spec["optimizer"]["jobs"])
    raw = os.path.join(outdir, "raw")

    log(f"Loaded sweep: {steps} rotor positions over one electrical period, all {phases} phases")
    at = phase_ampere_turns(ni_peak, steps, phases, plan.get("current_angle_deg", 0.0))
    angles, samples = sweep_period(parameters, analysis, os.path.join(raw, "loaded"), at, jobs, True, geometry, solver)
    electrical_deg = 360.0 * np.arange(steps) / steps
    total = np.array([s.torque_Nm for s in samples])
    flux = np.array([list(s.flux_linkage_Wb) for s in samples])            # per turn, every phase

    core_files = [s.field_file for s in samples]
    iron = losses.iron_loss(spec, d, core_files)
    heat = temperatures(spec, machine, values, d, iron["iron_loss_W"], iron["rotor_loss_W"])
    winding = machine.winding(spec, values)
    copper = spec["materials"]["copper"]
    if turns is None:
        turns = winding_model.turns_for(winding, copper, spec["limits"], flux[:positions, 0], d["electrical_frequency_Hz"],
                                        ni_peak, heat["winding_C"], spec["winding"]["strip_min_thickness_mm"])["turns"]
    omega_e = 2 * math.pi * d["electrical_frequency_Hz"]
    r_phase = winding_model.resistance(winding_model.winding_resistance(copper, winding, heat["winding_C"]), turns)
    phase_current = at[:, 0] / turns
    terminal = r_phase * phase_current + turns * omega_e * slope_full_period(flux[:, 0])

    series = {"machine": [], "air": [], "airgap": [], "axial": []}
    part = "radial" if hybrid else ""
    magnet_min, saturated = [], []
    step0 = best_step = None
    first_profile = None
    for k in range(steps):
        posdir = os.path.join(raw, "loaded", f"pos_{k:03d}", part)
        with open(os.path.join(posdir, "section.regions.json")) as f:
            meta = json.load(f)
        step = read_position(posdir, meta, analysis, at[k])
        if hybrid:
            series["axial"].append((electrical_deg[k], write_axial(outdir, k, os.path.dirname(posdir), analysis, at[k],
                                                                   {"rotor_angle_deg": angles[k], "torque_Nm": total[k]})))
        info = {"rotor_angle_deg": angles[k], "electrical_angle_deg": electrical_deg[k],
                "phase_current_A": phase_current[k], "torque_Nm": total[k], "machine_torque_Nm": total[k],
                "flux_linkage_Wb": turns * flux[k, 0]}
        files, profile = write_step(outdir, k, step, info, length, skip_air)
        for name, path in files.items():
            series[name].append((electrical_deg[k], path))
        cd = step["cell_data"]
        magnets = cd["material"] == MATERIAL_IDS["magnet"]
        magnet_min.append((cd["B_along_magnetization"][magnets], step["area_mm2"][magnets]))
        core = cd["material"] == MATERIAL_IDS["stator core"]
        saturated.append(float(np.sum(step["area_mm2"][core & (cd["saturation"] > 0.8)]) / np.sum(step["area_mm2"][core])))
        if k == 0:
            step0, first_profile = step, profile
        if k == int(np.argmax(total)):
            best_step = step
    for name, entries in series.items():
        if entries:
            vtkio.write_pvd(os.path.join(outdir, name + ".pvd"), entries)

    # Core loss distribution on the mesh of the first step (the elements of its field file).
    core_mask = step0["body"] == step0["ids"]["stator_core"]
    material = spec["materials"]["stator_core"]
    _, density = losses.stator_loss_density(material, d["electrical_frequency_Hz"], core_files)
    _, peak = losses.core_peak_field(core_files)
    if hybrid:                                    # the core field holds the radial section first, then the slices
        axial_peak, axial_density = peak[int(core_mask.sum()):], density[int(core_mask.sum()):]
        peak, density = peak[:int(core_mask.sum())], density[:int(core_mask.sum())]
        write_axial_core(outdir, os.path.join(raw, "loaded", "pos_000"), analysis, axial_peak, axial_density, material)
    if int(core_mask.sum()) != len(peak):
        raise ExportError("The core loss field does not match the core mesh of the first step.")
    cp, cc, _, ccd = extruded(step0, core_mask, length, (), ("region",))
    ccd.update({"B_peak": peak, "loss_density_W_per_kg": density,
                "loss_density_W_per_m3": density * material["density_kg_m3"]})
    vtkio.write_vtu(os.path.join(outdir, "core_loss.vtu"), cp, cc, vtkio.WEDGE, None, ccd,
                    {"iron_loss_W_per_phase": iron["iron_loss_W"], "iron_loss_W_all_phases": phases * iron["iron_loss_W"],
                     "electrical_frequency_Hz": d["electrical_frequency_Hz"]})

    # The whole machine at the position of highest torque.
    rp, rc, rpd, rcd = extruded(best_step, best_step["solid"], length, ("B", "B_magnitude"),
                                ("region", "material", "saturation", "phase"))
    vtkio.write_vtu(os.path.join(outdir, "full_ring.vtu"), rp, rc, vtkio.WEDGE, rpd, rcd)

    # No load: cogging torque, induced voltage, air-gap field of the magnets alone.
    cogging = no_load_flux = induced = None
    profile, profile_source = first_profile, "loaded, first step"
    if no_load:
        log(f"No-load sweep: {steps} rotor positions")
        _, samples0 = sweep_period(parameters, analysis, os.path.join(raw, "no_load"), np.zeros_like(at), jobs, False,
                                   geometry, solver)
        cogging = np.array([s.torque_Nm for s in samples0])
        no_load_flux = np.array([s.flux_linkage_Wb[0] for s in samples0])
        induced = turns * omega_e * slope_full_period(no_load_flux)
        posdir = os.path.join(raw, "no_load", "pos_000", part)
        with open(os.path.join(posdir, "section.regions.json")) as f:
            meta0 = json.load(f)
        theta, b = gap_profile(read_position(posdir, meta0, analysis, np.zeros(phases)))
        profile = (theta, polar(b, np.cos(np.radians(theta)), np.sin(np.radians(theta)))[0])
        profile_source = "no load, d axis"
    if not keep_raw:
        shutil.rmtree(raw, ignore_errors=True)

    regions = [{"region": number, "name": name, "material": kind, "material_id": MATERIAL_IDS[kind],
                "side": region["side"], "kind": region["kind"]}
               for number, (name, kind, region) in sorted(step0["names"].items())]
    b_min = np.concatenate([b for b, _ in magnet_min])
    a_all = np.concatenate([a for _, a in magnet_min])
    theta, b_r = profile
    return {
        "model": "section2d", "ring_has_all_phases": True, "stack_length_mm": length,
        "hybrid": "rafm" if hybrid else None,
        "torque_shares_Nm": shares_of(samples) if hybrid else None,
        "radii_mm": {k: float(v) for k, v in step0["meta"]["radii"].items()},
        "turns": int(turns), "pole_pairs": p, "phases": phases, "steps": steps, "sectors": 1,
        "phase_pitch_mm": 0.0, "phase_turn_deg": 0.0,
        "speed_rpm": spec["operating_point"]["speed_rpm"], "ampere_turns_peak": ni_peak,
        "current_angle_deg": plan.get("current_angle_deg", 0.0),
        "rotor_angle_deg": angles, "electrical_angle_deg": electrical_deg, "phase_current_A": phase_current,
        "phase_torque_Nm": None, "machine_torque_Nm": total, "flux_linkage_Wb": turns * flux[:, 0],
        "flux_linkage_phases_Wb": turns * flux,
        "terminal_voltage_V": terminal, "cogging_torque_Nm": cogging, "phase_cogging_torque_Nm": None,
        "no_load_flux_linkage_Wb": None if no_load_flux is None else turns * no_load_flux,
        "induced_voltage_V": induced, "airgap_b_radial_under_leg_T": None,
        "profile": (theta, np.array([0.0]), b_r[None, :]), "profile_source": profile_source, "leg_z_mm": 0.0,
        "torque": torque.metrics(total), "iron": iron, "thermal": heat, "resistance_ohm": r_phase,
        "saturated_core_share": saturated,
        "magnet_min_T": float(b_min.min()),
        "magnet_share_below_0T": float(np.sum(a_all[b_min < 0.0]) / np.sum(a_all)),
        "magnet_share_below_0p3T": float(np.sum(a_all[b_min < 0.3]) / np.sum(a_all)),
        "regions": regions, "elements": int(len(step0["cells"])),
        "series": {name: len(entries) for name, entries in series.items()},
    }
