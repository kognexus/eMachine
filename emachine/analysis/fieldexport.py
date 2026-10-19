"""
Field export of one design for ParaView.

The design is solved over a full electrical period with the fields kept. Every rotor position
becomes one step of three time series (solid parts, air, air-gap cylinder), and the scalar
results become tables: waveforms, harmonics, air-gap profile and the core loss distribution.

Lengths in the written files are millimetres; fields are in SI units unless the name says otherwise.
"""

import json
import math
import os
import shutil

import numpy as np

from emachine.io import vtk as vtkio
from emachine.physics import losses, torque
from emachine.physics import winding as winding_model
from emachine.pipeline import design_space as design
from emachine.pipeline import sweep as pipeline_sweep
from emachine.pipeline.evaluate import temperatures
from emachine.solvers.elmer import materials, results
from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS

MATERIAL_IDS = {"air": 1, "copper": 2, "magnet": 3, "stator core": 4, "rotor iron": 5, "rotor housing": 6}
MU0 = 4e-7 * math.pi


class ExportError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- material state

def permeability(b_magnitude, curve, mu_r):
    """
    Relative permeability and saturation level at flux densities `b_magnitude`.
    `curve` is a (B, H) table or None for a linear material with `mu_r`.
    Saturation level = polarisation / highest polarisation of the curve, between 0 and 1.
    """
    b = np.asarray(b_magnitude, dtype=float)
    if not curve:
        return np.full(b.shape, float(mu_r)), np.zeros(b.shape)
    table_b = np.array([p[0] for p in curve])
    table_h = np.array([p[1] for p in curve])
    initial = table_b[1] / (MU0 * table_h[1])
    h = np.interp(b, table_b, table_h)
    with np.errstate(divide="ignore", invalid="ignore"):
        mu = np.where(h > 0, b / (MU0 * h), initial)
    polarisation = np.maximum(b - MU0 * h, 0.0)
    return mu, np.clip(polarisation / np.max(table_b - MU0 * table_h), 0.0, 1.0)


# ----------------------------------------------------------------------------- one rotor position

def read_step(posdir, analysis, ampere_turns):
    """Mesh, fields and per-element quantities of one solved rotor position."""
    with open(os.path.join(posdir, "sector.regions.json")) as f:
        meta = json.load(f)
    bodies, _ = results.read_names(posdir)
    data = results.read_fields(posdir)
    if data is None:
        raise ExportError(f"No field file in {posdir}.")
    points, tets, body, fields = data
    b_name = results.flux_density_name(fields)
    a_name = next((n for n in fields if "vector potential" in n and fields[n].ndim == 2), None)
    if b_name is None or a_name is None:
        raise ExportError(f"The field file in {posdir} lacks the flux density or the vector potential.")
    b = fields[b_name]
    b_cell = b[tets].mean(axis=1)
    b_abs = np.linalg.norm(b_cell, axis=1)
    centroid = points[tets].mean(axis=1)

    count = len(tets)
    material = np.zeros(count, dtype=np.int64)
    side = np.zeros(count, dtype=np.int64)
    solid = np.zeros(count, dtype=bool)
    mu = np.ones(count)
    saturation = np.zeros(count)
    magnetisation = np.zeros((count, 3))
    along = np.zeros(count)
    current = np.zeros((count, 3))
    curves = {"stator core": materials.material_curve(analysis, "stator_core"),
              "rotor iron": materials.material_curve(analysis, "rotor_iron")}
    linear = {"air": 1.0, "copper": 1.0, "magnet": analysis["magnet_mu_r"], "stator core": analysis["stator_core_mu_r"],
              "rotor iron": analysis["rotor_iron_mu_r"], "rotor housing": analysis["rotor_housing_mu_r"]}
    m0 = analysis["magnet_remanence_T"] / (MU0 * analysis["magnet_mu_r"])
    stator = meta["parameters"]["stator"]
    coil_area = stator["coil_height"] * (stator["slot_width"] - 2 * stator["coil_clearance"])      # mm2
    names = {}
    for name, number in bodies.items():
        region = meta["regions"].get(name)
        if region is None:
            continue
        sel = body == number
        kind = materials.material_of(name, region)
        names[number] = (name, kind, region)
        material[sel] = MATERIAL_IDS[kind]
        side[sel] = 1 if region["side"] == "rotor" else 0
        solid[sel] = region["kind"] != "air"
        mu[sel], saturation[sel] = permeability(b_abs[sel], curves.get(kind), linear[kind])
        if region["kind"] == "magnet":
            if region.get("axis") == "axial":
                direction = np.array([0.0, 0.0, float(region["direction"])])
            else:
                phi = math.radians(region["centre_deg"] + region["beta_deg"])
                direction = np.array([math.cos(phi), math.sin(phi), 0.0])
            magnetisation[sel] = m0 * direction
            along[sel] = b_cell[sel] @ direction
        elif region["kind"] == "coil":
            x, y = centroid[sel, 0], centroid[sel, 1]
            r = np.maximum(np.hypot(x, y), 1e-30)
            density = ampere_turns / coil_area                                                     # A/mm2, azimuthal
            current[sel] = density * np.column_stack([-y / r, x / r, np.zeros(sel.sum())])

    r = np.maximum(np.hypot(points[:, 0], points[:, 1]), 1e-30)
    cos, sin = points[:, 0] / r, points[:, 1] / r
    return {
        "meta": meta, "names": names, "body": body,
        "points": points * 1e3, "cells": tets, "solid": solid, "volume_mm3": results.tet_volumes(points[tets]) * 1e9,
        "point_data": {
            "B": b, "B_magnitude": np.linalg.norm(b, axis=1), "A": fields[a_name],
            "B_radial": b[:, 0] * cos + b[:, 1] * sin, "B_tangential": -b[:, 0] * sin + b[:, 1] * cos,
            "B_axial": b[:, 2].copy(),
        },
        "cell_data": {
            "region": body.astype(np.int64), "material": material, "side": side, "B_cell": b_cell,
            "mu_r": mu, "saturation": saturation, "magnetization": magnetisation,
            "B_along_magnetization": along, "current_density": current,
        },
    }


def airgap_surface(step):
    """
    The cylinder in the middle of the air gap (the sliding surface), seen from the stator side.
    Returns (points, cells, cell type, point data, grid) where grid = (theta in degrees, z in mm,
    radial flux density as a (z, theta) array) or None when the nodes do not form a regular grid.
    """
    sector = step["meta"]["sector"]
    radius = sector["sliding_radius_mm"]
    numbers = [n for n, (_, _, region) in step["names"].items() if region["kind"] == "air" and region["side"] == "stator"]
    nodes = np.unique(step["cells"][np.isin(step["body"], numbers)])
    p = step["points"][nodes]
    nodes = nodes[np.abs(np.hypot(p[:, 0], p[:, 1]) - radius) < 1e-3]
    p = step["points"][nodes]
    theta = (np.degrees(np.arctan2(p[:, 1], p[:, 0])) - sector["start_deg"] + 180.0) % 360.0 - 180.0 + sector["start_deg"]
    key = np.round(np.column_stack([p[:, 2], theta]), 5)
    _, first = np.unique(key, axis=0, return_index=True)                 # sorted by z, then theta
    nodes, theta, z = nodes[first], theta[first], p[first, 2]
    data = {name: array[nodes] for name, array in step["point_data"].items()}
    data["theta_deg"] = theta
    n_theta, n_z = sector["sliding_cells_theta"] + 1, sector["sliding_cells_z"] + 1
    if len(nodes) != n_theta * n_z:
        return step["points"][nodes], np.arange(len(nodes)).reshape(-1, 1), vtkio.VERTEX, data, None
    index = np.arange(n_theta * n_z).reshape(n_z, n_theta)
    quads = np.column_stack([index[:-1, :-1].ravel(), index[:-1, 1:].ravel(), index[1:, 1:].ravel(), index[1:, :-1].ravel()])
    grid = (theta.reshape(n_z, n_theta)[0], z.reshape(n_z, n_theta)[:, 0], data["B_radial"].reshape(n_z, n_theta))
    return step["points"][nodes], quads, vtkio.QUAD, data, grid


def write_step(outdir, k, step, info, sectors=1, skip_air=False):
    """Writes the files of one step. Returns {series name: file path} and the air-gap grid."""
    angle = 360.0 / step["meta"]["sector"]["periodicity"]
    files = {}
    parts = [("machine", step["solid"], step["cell_data"])]
    if not skip_air:
        air_data = {name: step["cell_data"][name] for name in ("region", "material", "side", "B_cell")}
        parts.append(("air", ~step["solid"], air_data))
    for name, mask, cell_data in parts:
        p, c, pd, cd = vtkio.subset(step["points"], step["cells"], mask, step["point_data"], cell_data)
        p, c, pd, cd = vtkio.repeat_sector(p, c, pd, cd, sectors, angle)
        files[name] = os.path.join(outdir, name, f"{name}_{k:03d}.vtu")
        vtkio.write_vtu(files[name], p, c, vtkio.TETRA, pd, cd, info)
    p, c, cell_type, pd, grid = airgap_surface(step)
    p, c, pd, _ = vtkio.repeat_sector(p, c, pd, {}, sectors, angle)
    files["airgap"] = os.path.join(outdir, "airgap", f"airgap_{k:03d}.vtu")
    vtkio.write_vtu(files["airgap"], p, c, cell_type, pd, None, info)
    return files, grid


# ----------------------------------------------------------------------------- waveforms

def slope_full_period(values):
    """d(values)/d(electrical angle) of samples over one full period, by spectral differentiation."""
    v = np.asarray(values, dtype=float)
    n = len(v)
    k = np.fft.fftfreq(n, d=1.0 / n)
    spectrum = np.fft.fft(v) * (1j * k)
    if n % 2 == 0:
        spectrum[n // 2] = 0.0
    return np.real(np.fft.ifft(spectrum))


def harmonics(values, count=None):
    """Amplitudes of the harmonics of samples over one period: list of (order, amplitude). Order 0 is the mean."""
    v = np.asarray(values, dtype=float)
    spectrum = np.fft.rfft(v) / len(v)
    amplitude = 2 * np.abs(spectrum)
    amplitude[0] = abs(spectrum[0])
    if len(v) % 2 == 0:
        amplitude[-1] = abs(spectrum[-1])
    rows = list(enumerate(amplitude.tolist()))
    return rows if count is None else rows[:count]


def machine_torque_full(phase_torque, phases):
    """Torque of all phases from the torque of one phase over a full electrical period."""
    t = np.asarray(phase_torque, dtype=float)
    if phases == 1:
        return t.copy()
    if len(t) % 3:
        raise ValueError("The number of positions per period must be a multiple of 3 for three phases.")
    return sum(np.roll(t, -k * len(t) // 3) for k in range(3))


# ----------------------------------------------------------------------------- the export

def sweep(spec, values, workdir, ampere_turns_peak, positions, core_field):
    """Solves a full electrical period with the fields kept. Returns (parameters, analysis, angles, currents, rows)."""
    parameters = design.parameters(spec, values)
    analysis = dict(ANALYSIS_DEFAULTS)
    analysis.update(parameters["analysis"])
    analysis.update({"coil_turns": 1, "keep_fields": True})
    p = int(parameters["stator"]["pole_pairs"])
    steps = 2 * positions
    angles = (360.0 / p) * np.arange(steps) / steps
    currents = -ampere_turns_peak * np.sin(2 * math.pi * np.arange(steps) / steps)
    shutil.rmtree(workdir, ignore_errors=True)
    rows, failed = pipeline_sweep.run_rows(parameters, analysis, angles, workdir, int(spec["optimizer"]["jobs"]),
                                          currents=currents, core_field=core_field)
    if failed:
        raise ExportError(f"{len(failed)} of {steps} rotor positions failed in {workdir}: {failed[0][1].splitlines()[0]}")
    return parameters, analysis, angles, currents, rows


def _phase_pitch(spec):
    """Axial distance between neighbouring phases of a TFM (phases stacked along the axis); 0 otherwise."""
    if spec["machine"]["flux_path"] != "tfm":
        return 0.0
    from emachine.machines.tfm.design import phase_width
    return phase_width(spec) + spec["machine"]["phase_spacing_mm"]


def export(spec, values, outdir, turns=None, sectors=1, no_load=True, skip_air=False, keep_raw=False, log=print):
    """
    Runs the sweeps and writes every file of the export. Returns a dictionary with the waveforms,
    key numbers and file names (also saved as summary.json).
    """
    log = log or (lambda *a, **k: None)
    os.makedirs(outdir, exist_ok=True)
    for name in ("machine", "air", "airgap"):
        shutil.rmtree(os.path.join(outdir, name), ignore_errors=True)
    machine = design.machine_of(spec)
    d = machine.derive(spec, values)
    winding = machine.winding(spec, values)
    copper = spec["materials"]["copper"]
    phases, p = spec["machine"]["phases"], d["pole_pairs"]
    positions = int(spec["fidelity"]["positions"])
    steps = 2 * positions
    ni_peak = d["ampere_turns_peak"]
    raw = os.path.join(outdir, "raw")

    log(f"Loaded sweep: {steps} rotor positions over one electrical period")
    parameters, analysis, angles, currents, rows = sweep(spec, values, os.path.join(raw, "loaded"), ni_peak, positions, True)
    electrical_deg = 360.0 * np.arange(steps) / steps
    phase_torque = np.array([r["torque_Nm"] for r in rows])
    flux = np.array([r["flux_linkage_Wb"] for r in rows])                  # per turn
    total = machine_torque_full(phase_torque, phases)

    core_files = [r["core_field_file"] for r in rows]
    iron = losses.iron_loss(spec, d, core_files)
    heat = temperatures(spec, machine, values, d, iron["iron_loss_W"], iron["rotor_loss_W"])
    if turns is None:
        turns = winding_model.turns_for(winding, copper, spec["limits"], flux[:positions], d["electrical_frequency_Hz"],
                                        d["ampere_turns_peak"], heat["winding_C"],
                                        spec["winding"]["strip_min_thickness_mm"])["turns"]
    omega_e = 2 * math.pi * d["electrical_frequency_Hz"]
    r_phase = winding_model.resistance(winding_model.winding_resistance(copper, winding, heat["winding_C"]), turns)
    phase_current = currents / turns
    terminal = r_phase * phase_current + turns * omega_e * slope_full_period(flux)

    # Field files of the loaded sweep.
    series = {"machine": [], "air": [], "airgap": []}
    magnet_min, saturated, gap_under_leg = [], [], []
    leg_z = d["slot_width"] / 2 + d["leg_width"] / 2
    first_grid = step0 = best_step = None
    for k in range(steps):
        step = read_step(os.path.join(raw, "loaded", f"pos_{k:03d}"), analysis, float(currents[k]))
        info = {"rotor_angle_deg": angles[k], "electrical_angle_deg": electrical_deg[k],
                "phase_current_A": phase_current[k], "torque_Nm": phase_torque[k],
                "machine_torque_Nm": total[k], "flux_linkage_Wb": turns * flux[k]}
        files, grid = write_step(outdir, k, step, info, sectors, skip_air)
        for name, path in files.items():
            series[name].append((electrical_deg[k], path))
        cd = step["cell_data"]
        magnets = cd["material"] == MATERIAL_IDS["magnet"]
        magnet_min.append((cd["B_along_magnetization"][magnets], step["volume_mm3"][magnets]))
        core = cd["material"] == MATERIAL_IDS["stator core"]
        saturated.append(float(np.sum(step["volume_mm3"][core & (cd["saturation"] > 0.8)]) / np.sum(step["volume_mm3"][core])))
        if grid is not None:
            theta, z, b_radial = grid
            row = int(np.argmin(np.abs(z - leg_z)))
            gap_under_leg.append(float(b_radial[row, int(np.argmin(np.abs(theta)))]))
            first_grid = first_grid or grid
        if k == 0:
            step0 = step
        if k == int(np.argmax(phase_torque)):
            best_step = step
    for name, entries in series.items():
        if entries:
            vtkio.write_pvd(os.path.join(outdir, name + ".pvd"), entries)

    # Core loss distribution on the mesh of the first step.
    core_numbers = [n for n, (_, _, region) in step0["names"].items() if region["side"] == "stator" and region["kind"] == "core"]
    core_mask = np.isin(step0["body"], core_numbers)
    volume, peak = losses.core_peak_field(core_files)
    material = spec["materials"]["stator_core"]
    _, density = losses.stator_loss_density(material, d["electrical_frequency_Hz"], core_files)
    cp, cc, _, ccd = vtkio.subset(step0["points"], step0["cells"], core_mask, None,
                                  {"region": step0["cell_data"]["region"]})
    if len(cc) != len(peak):
        raise ExportError("The core loss field does not match the core mesh of the first step.")
    ccd.update({"B_peak": peak, "loss_density_W_per_kg": density,
                "loss_density_W_per_m3": density * material["density_kg_m3"]})
    vtkio.write_vtu(os.path.join(outdir, "core_loss.vtu"), cp, cc, vtkio.TETRA, None, ccd,
                    {"iron_loss_W_per_phase": iron["iron_loss_W"], "electrical_frequency_Hz": d["electrical_frequency_Hz"]})

    # Whole ring at the position of highest torque: solid parts with the main fields only.
    periodicity = best_step["meta"]["sector"]["periodicity"]
    rp, rc, rpd, rcd = vtkio.subset(best_step["points"], best_step["cells"], best_step["solid"],
                                    {n: best_step["point_data"][n] for n in ("B", "B_magnitude")},
                                    {n: best_step["cell_data"][n] for n in ("region", "material", "saturation")})
    rp, rc, rpd, rcd = vtkio.repeat_sector(rp, rc, rpd, rcd, periodicity, 360.0 / periodicity)
    vtkio.write_vtu(os.path.join(outdir, "full_ring.vtu"), rp, rc, vtkio.TETRA, rpd, rcd)

    # No-load sweep: cogging torque, induced voltage, air-gap field of the magnets alone.
    cogging = cogging_total = no_load_flux = induced = None
    profile_grid, profile_source = first_grid, "loaded, first step"
    if no_load:
        log(f"No-load sweep: {steps} rotor positions")
        _, analysis0, _, _, rows0 = sweep(spec, values, os.path.join(raw, "no_load"), 0.0, positions, False)
        cogging = np.array([r["torque_Nm"] for r in rows0])
        cogging_total = machine_torque_full(cogging, phases)
        no_load_flux = np.array([r["flux_linkage_Wb"] for r in rows0])
        induced = turns * omega_e * slope_full_period(no_load_flux)
        grid0 = airgap_surface(read_step(os.path.join(raw, "no_load", "pos_000"), analysis0, 0.0))[4]
        if grid0 is not None:
            profile_grid, profile_source = grid0, "no load, aligned position"
    if not keep_raw:
        shutil.rmtree(raw, ignore_errors=True)

    regions = [{"region": number, "name": name, "material": kind, "material_id": MATERIAL_IDS[kind],
                "side": region["side"], "kind": region["kind"]}
               for number, (name, kind, region) in sorted(step0["names"].items())]
    tm = torque.metrics(total)
    b_min = np.concatenate([b for b, _ in magnet_min])
    v_all = np.concatenate([v for _, v in magnet_min])
    result = {
        "turns": int(turns), "pole_pairs": p, "phases": phases, "steps": steps, "sectors": sectors,
        # Layout of the phases along the axis, for drawing the whole machine from one phase: phase k is
        # moved k * phase_pitch_mm along +Z, and its stator turned by k * phase_turn_deg (120 or 90
        # electrical degrees); the rotor is not turned.
        "phase_pitch_mm": _phase_pitch(spec),
        "phase_turn_deg": (90.0 if phases == 2 else 360.0 / phases) / p if phases > 1 else 0.0,
        "speed_rpm": spec["operating_point"]["speed_rpm"], "ampere_turns_peak": ni_peak,
        "rotor_angle_deg": angles, "electrical_angle_deg": electrical_deg, "phase_current_A": phase_current,
        "phase_torque_Nm": phase_torque, "machine_torque_Nm": total, "flux_linkage_Wb": turns * flux,
        "terminal_voltage_V": terminal, "cogging_torque_Nm": cogging_total, "phase_cogging_torque_Nm": cogging,
        "no_load_flux_linkage_Wb": None if no_load_flux is None else turns * no_load_flux,
        "induced_voltage_V": induced,
        "airgap_b_radial_under_leg_T": np.array(gap_under_leg) if len(gap_under_leg) == steps else None,
        "profile": profile_grid, "profile_source": profile_source, "leg_z_mm": leg_z,
        "torque": tm, "iron": iron, "thermal": heat, "resistance_ohm": r_phase,
        "saturated_core_share": saturated,
        "magnet_min_T": float(b_min.min()),
        "magnet_share_below_0T": float(np.sum(v_all[b_min < 0.0]) / np.sum(v_all)),
        "magnet_share_below_0p3T": float(np.sum(v_all[b_min < 0.3]) / np.sum(v_all)),
        "regions": regions, "elements": int(len(step0["cells"])),
        "series": {name: len(entries) for name, entries in series.items()},
    }
    return result
