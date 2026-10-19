"""
Evaluation of one design on a given drive (T58, T61): DC-link voltage and phase currents fixed, the
winding (turns, parallel paths, AWG and strands) chosen by the voltage at the rated speed.

Synchronous machines (PM, IPM, SynRM, PMaSynRM, vernier), all phases solved at once:
    1. no load at two rotor positions: PM flux and the phase sequence of the rotation
    2. current angle of the most torque at a first estimate of the ampere-turns (6 angles, refined)
    3. flux at three ampere-turn levels at that angle -> the most effective turns the bus allows at
       the rated speed and current (and the efficiency limit) -> winding with fill 0.5 to 0.7
    4. rated sweep over half an electrical period: torque waveform (Arkkio), phase fluxes, core
       fields (iron and rotor losses), phase and line voltage waveforms
    5. peak current: the current angle of the most torque at 42 A (fundamental torque from the flux)
    skew (design variable): continuous skew applied to the harmonics of torque and flux.

Switched reluctance: one phase alone, flux and torque over half a rotor pole pitch at six ampere-turn
levels; the dynamic model of physics.drive (asymmetric half bridge) chooses the firing angles and
the turns.

`evaluate(design, drive, settings, workdir)`; `design` comes from a topology of
machines/catalogue (params of the section, winding data, principle).
"""

import dataclasses
import json
import math
import os
import shutil
import time

import numpy as np

from emachine.core import registry
from emachine.core.types import Excitation, GeometryRequest
from emachine.physics import drive as D
from emachine.physics import losses

MU0 = 4e-7 * math.pi


class FieldRunner:
    """Field solutions of one design, one after the other in this process. Solutions at the same rotor
    angle share one mesh (meshed and converted once)."""

    def __init__(self, params, analysis, workdir, keep=False, kind="section2d", solver="elmer_sections"):
        self.params, self.analysis, self.workdir = params, dict(analysis, keep_fields=keep), workdir
        self.kind, self.solver_name = kind, solver
        self.builder = registry.create("geometry", kind)
        self.request = GeometryRequest(kind, params)
        self.count, self.seconds, self.meta = 0, 0.0, None
        self.meshes = {}
        os.makedirs(workdir, exist_ok=True)

    def _mesh(self, angle_deg):
        key = round(float(angle_deg), 9)
        if key not in self.meshes:
            folder = os.path.join(self.workdir, f"pos{len(self.meshes):03d}")
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            self.meshes[key] = (folder, self.builder.build(self.request, angle_deg, folder))
        return self.meshes[key]

    def solve(self, angle_deg, ampere_turns, core_field=False, tag=None, keep=None):
        began = time.time()
        folder, mesh = self._mesh(angle_deg)
        settings = dict(self.analysis, reuse_mesh=True)
        if keep is not None:
            settings["keep_fields"] = keep
        solver = registry.create("solver", self.solver_name, settings=settings, core_field=core_field)
        sample = solver.solve(mesh, Excitation(rotor_angle_deg=angle_deg, ampere_turns=tuple(float(x) for x in ampere_turns)),
                              folder)
        self.meta = mesh.meta
        if core_field and sample.field_file:          # keep the core field of this solution under its own name
            target = os.path.join(folder, f"core_field_{tag or self.count}.npz")
            os.replace(sample.field_file, target)
            sample = dataclasses.replace(sample, field_file=target)
        if settings["keep_fields"]:                   # field files of the parts under the name of the solution
            for part in mesh.meta["parts"]:
                src = os.path.join(folder, part["folder"], "fields.npz")
                if os.path.isfile(src):
                    os.replace(src, os.path.join(folder, part["folder"], f"fields_{tag or self.count}.npz"))
        self.count += 1
        self.seconds += time.time() - began
        return sample


def region_areas(meta):
    """Areas (mm2) times depth (mm) summed over the parts: volumes in mm3 by kind of region."""
    out = {"magnet": 0.0, "stator_core": 0.0, "rotor_core": 0.0, "coil": 0.0}
    for part in meta["parts"]:
        depth = part["stack_length_mm"]
        for name, region in part["regions"].items():
            key = "magnet" if region["kind"] == "magnet" else ("coil" if region["kind"] == "coil" else name)
            if key in out:
                out[key] += region["area_mm2"] * depth
    return out


def masses(design, meta, winding, materials):
    v = region_areas(meta)
    mag = materials["magnet"]["density_kg_m3"]
    copper_active = v["coil"] * (winding["fill"] if winding else 0.6)
    turn = design["turn_length_mm"]
    active = design.get("active_length_mm", design["params"].get("stack_length", 0.0))
    copper = copper_active * turn / (2 * active) if active > 0 else copper_active
    out = {"magnet_kg": v["magnet"] * 1e-9 * mag,
           "stator_core_kg": v["stator_core"] * 1e-9 * materials["stator_core"]["density_kg_m3"],
           "rotor_core_kg": v["rotor_core"] * 1e-9 * materials["rotor_iron"]["density_kg_m3"],
           "copper_kg": copper * 1e-9 * 8900.0}
    if design.get("ferrite_magnets"):
        out["magnet_kg"] = v["magnet"] * 1e-9 * 4900.0
    out["active_kg"] = sum(out.values())
    return out


def iron_losses(spec, files, frequency):
    """(stator, rotor) loss in W of the whole machine and core flux statistics from saved core fields."""
    if not files:
        return 0.0, 0.0, {}
    with np.load(files[0]) as first:
        has_stator = len(first["volume"]) > 0
    if not has_stator:
        return 0.0, 0.0, {}
    coeff = losses.iron_loss_coefficients(spec, files)
    stator, rotor = losses.loss_at(coeff, frequency, spec["materials"])
    phases = losses.phases_in_field(files[0])
    stats = {k: coeff[k] for k in ("core_b_max_T", "core_b_p95_T", "core_b_mean_T", "core_mass_kg") if k in coeff}
    return float(stator) * phases, float(rotor) * phases, stats


# ----------------------------------------------------------------------------- synchronous machines

def _best_angle(angles, torques):
    """The angle of the largest torque, refined by a parabola through it and its neighbours (degrees)."""
    k = int(np.argmax(torques))
    n = len(angles)
    if n < 3:
        return angles[k]
    a0, a1, a2 = angles[(k - 1) % n], angles[k], angles[(k + 1) % n]
    t0, t1, t2 = torques[(k - 1) % n], torques[k], torques[(k + 1) % n]
    step = (a2 - a0) % 360 / 2
    denom = t0 - 2 * t1 + t2
    if abs(denom) < 1e-15:
        return a1
    return (a1 + 0.5 * step * (t0 - t2) / denom) % 360


def _parabola(angles, torques):
    """Vertex of the parabola through three equally spaced angles (clipped to them)."""
    a0, a1, a2 = angles
    t0, t1, t2 = torques
    denom = t0 - 2 * t1 + t2
    if abs(denom) < 1e-15:
        return angles[int(np.argmax(torques))]
    x = a1 + 0.5 * (a1 - a0) * (t0 - t2) / denom
    return min(max(x, a0), a2)


def evaluate_synchronous(design, drive, settings, workdir, log=None):
    params, pe = design["params"], int(design["pe"])
    phases = 3
    runner = FieldRunner(params, settings["analysis"], workdir, keep=bool(settings.get("keep_workdir")),
                         kind=design.get("geometry_kind", "section2d"), solver=design.get("solver", "elmer_sections"))
    i_r, i_p = drive["rated_current_A"], drive["peak_current_A"]
    f_e = drive["speed_rpm"] / 60.0 * pe
    w_e = 2 * math.pi * f_e
    v_phase_max = drive["modulation"] * drive["bus_voltage_V"] / math.sqrt(3)
    v_target = settings.get("voltage_margin", 0.97) * v_phase_max     # harmonics add to the fundamental
    copper, temp = settings["materials"]["copper"], drive["winding_temp_C"]
    rho = copper["resistivity_20C_ohm_m"] * (1 + copper["temp_coefficient_per_K"] * (temp - 20))
    n_c, side, turn = design["coils_per_phase"], design["side_area_mm2"], design["turn_length_mm"]
    fill_hi = settings["fill_range"][1]

    def r_of(n_eff):                       # phase resistance for a fill at the top of the range (paths 1)
        return rho * turn * 1e-3 * n_c * n_eff ** 2 / (fill_hi * side * 1e-6)

    # 1. no load
    step_mech = 30.0 / pe
    s0 = runner.solve(0.0, (0.0,) * phases)
    s1 = runner.solve(step_mech, (0.0,) * phases)
    seq = D.sequence_from_flux(s0.flux_linkage_Wb, s1.flux_linkage_Wb, math.radians(30.0))
    if seq == 0:
        seq = design.get("sequence_hint", 1)
    pa, pb = D.clarke(s0.flux_linkage_Wb)
    phi_pm = math.hypot(pa, pb)
    cogging_probe = (s0.torque_Nm, s1.torque_Nm)

    # 2. first estimate of the turns and the current angle. Torque: Arkkio's, the mean of two positions
    #    30 el. deg apart (the 6th harmonic of the ripple cancels); flux for the voltage at position 0.
    ni_cap = 0.6 * side * 8.0 * math.sqrt(2)            # 8 A/mm2 rms in a 0.6 fill: upper bound of a rated point
    if phi_pm > 0:
        n0 = 0.8 * v_phase_max / (w_e * phi_pm)
        ni0 = min(n0 * i_r, ni_cap)
    else:
        ni0 = 0.6 * ni_cap
    ni0 = max(ni0, 0.05 * ni_cap)

    def point(ni, gamma_deg):
        """(mean torque of the two positions, flux per turn at position 0)."""
        out = []
        for angle in (0.0, step_mech):
            th = math.radians(pe * angle)
            out.append(runner.solve(angle, D.phase_currents(ni, th, math.radians(gamma_deg), seq)))
        return 0.5 * (out[0].torque_Nm + out[1].torque_Nm), out[0].flux_linkage_Wb

    angles = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0] if not design.get("known_axis") else [70.0, 90.0, 110.0]
    if phi_pm <= 0:
        # No magnet flux to tell the sequence: try both; with the wrong one the field turns against the
        # rotor and the torque averaged over three positions 30 el. deg apart cancels.
        best = None
        for trial in (1, -1):
            seq = trial
            g_try = _best_angle(angles, [point(ni0, g)[0] for g in angles])
            mean = np.mean([runner.solve(a, D.phase_currents(ni0, math.radians(pe * a), math.radians(g_try), trial)).torque_Nm
                            for a in (0.0, step_mech, 2 * step_mech)])
            if best is None or mean > best[0]:
                best = (mean, trial)
        seq = best[1]
    torques = [point(ni0, g)[0] for g in angles]
    if design.get("known_axis") and max(torques) <= 0:     # an outer rotor links the flux the other way round
        angles = [a + 180.0 for a in angles]
        torques = [point(ni0, g)[0] for g in angles]
    if design.get("known_axis"):
        gamma = _parabola(angles, torques)
    else:
        gamma = _best_angle(angles, torques)
        refine = [(gamma - 20.0) % 360, gamma, (gamma + 20.0) % 360]
        gamma = _best_angle(refine, [point(ni0, g)[0] for g in refine])
    if max(torques) <= 0:
        raise RuntimeError("no positive torque at any current angle")

    # 3. torque and flux at three levels at gamma -> turns
    levels = [0.0, 0.5 * ni0, ni0, 1.7 * ni0]
    psi_levels, t_levels = [list(s0.flux_linkage_Wb)], [0.0]
    for ni in levels[1:]:
        t, psi = point(ni, gamma)
        psi_levels.append(list(psi))
        t_levels.append(t)
    fmap = D.FluxMap(levels, psi_levels, t_levels)

    def voltage(n_eff):
        ni = n_eff * i_r
        i_abc = D.phase_currents(i_r, 0.0, math.radians(gamma), seq)
        return D.voltage_amplitude(fmap.at(ni), i_abc, n_eff, r_of(n_eff), f_e, 0.0, math.radians(gamma), seq)

    def torque_at(n_eff, current):
        ni = n_eff * current
        return float(np.interp(ni, fmap.ni, fmap.torque)) if ni <= fmap.ni[-1] else \
            fmap.torque[-1] + (fmap.torque[-1] - fmap.torque[-2]) / (fmap.ni[-1] - fmap.ni[-2]) * (ni - fmap.ni[-1])

    def efficiency(n_eff):
        t = torque_at(n_eff, i_r) * design.get("skew_factor", 1.0)
        p = t * 2 * math.pi * drive["speed_rpm"] / 60
        iron = settings["iron_loss_guess_W"] * drive["speed_rpm"] / 1000.0     # iron loss grows with the frequency
        return p / (p + 1.5 * i_r ** 2 * r_of(n_eff) + iron) if p > 0 else 0.0

    lo, hi = 0.01, 1.0
    while voltage(hi) < v_target and hi < 1e5:
        hi *= 2
    for _ in range(50):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if voltage(mid) <= v_target else (lo, mid)
    n_voltage = lo
    n_target = n_voltage
    eta_limit = settings["min_efficiency"]
    if efficiency(n_target) < eta_limit:          # fewer turns: less copper loss for less torque
        grid = [n_voltage * x for x in np.geomspace(0.05, 1.0, 30)]
        etas = [efficiency(n) for n in grid]
        ok = [n for n, e in zip(grid, etas) if e >= eta_limit]
        if ok:                                    # the most turns that still meet the limit
            lo2, hi2 = max(ok), n_voltage
            for _ in range(30):
                mid = math.sqrt(lo2 * hi2)
                lo2, hi2 = (mid, hi2) if efficiency(mid) >= eta_limit else (lo2, mid)
            n_target = lo2
        else:                                     # the limit is out of reach: the turns of the best efficiency
            n_target = grid[int(np.argmax(etas))]
    j_limit = settings.get("max_j_rated_rms_A_mm2")
    if j_limit:                                   # the rated current density (fill at most the top of the range)
        n_target = min(n_target, 0.98 * j_limit * fill_hi * side / (i_r / math.sqrt(2)))
    winding = D.winding_design(n_target, n_c, side, turn, copper, drive, temp, tuple(settings["fill_range"]))
    for _ in range(40):                           # the wire found may fill less: fewer turns until J is met
        if winding is None or not j_limit or winding["j_rated_rms_A_mm2"] <= j_limit:
            break
        n_target = 0.97 * min(n_target, winding["n_eff"])
        winding = D.winding_design(n_target, n_c, side, turn, copper, drive, temp, tuple(settings["fill_range"]))
    if winding is None:
        return {"analysed": False, "reason": "no winding with a fill in range", "n_eff_target": n_target,
                "solves": runner.count, "seconds": runner.seconds}
    n_eff, r_ph = winding["n_eff"], winding["resistance_ohm"]

    # 4. rated sweep
    n_pos = int(settings["positions"])
    angles_mech = [(180.0 / pe) * k / n_pos for k in range(n_pos)]
    torque_w, flux_w, files, currents = [], [], [], []
    for k, ang in enumerate(angles_mech):
        th = math.radians(pe * ang)
        i_abc = D.phase_currents(n_eff * i_r, th, math.radians(gamma), seq)
        s = runner.solve(ang, i_abc, core_field=True, tag=f"rated_{k:02d}")
        torque_w.append(s.torque_Nm)
        flux_w.append(list(s.flux_linkage_Wb))
        files.append(s.field_file)
        currents.append(list(i_abc / n_eff))
    torque_w, flux_w = np.array(torque_w), np.array(flux_w)
    skew_e = design.get("skew_e_rad", 0.0)
    k_sk1 = D.skew_factor(1, skew_e)
    if skew_e > 0:
        mean = float(np.mean(torque_w))
        torque_w = D.skewed(torque_w - mean, skew_e, antiperiodic=False) + mean * k_sk1
        flux_w = D.skewed(flux_w, skew_e, antiperiodic=True)
    stator_w, rotor_w, core_stats = iron_losses(settings["loss_spec"], files, f_e)
    wave = D.phase_waveforms(flux_w, np.array(currents), n_eff, r_ph, f_e)
    line_peak = float(np.max(np.abs(wave["line_voltage_V"])))
    v1, _ = D.harmonic(wave["voltage_V"][:, 0], 1)
    t_mean = float(np.mean(torque_w))
    copper_w = 1.5 * i_r ** 2 * r_ph
    p_out = t_mean * 2 * math.pi * drive["speed_rpm"] / 60
    loss_w = copper_w + stator_w + rotor_w
    eta = p_out / (p_out + loss_w) if p_out > 0 else 0.0

    # no-load waveform (back-EMF), only for finalists (settings["no_load_sweep"])
    emf = None
    if settings.get("no_load_sweep"):
        nl_t, nl_f = [], []
        for k, ang in enumerate(angles_mech):
            s = runner.solve(ang, (0.0,) * phases, tag=f"noload_{k:02d}")
            nl_t.append(s.torque_Nm)
            nl_f.append(list(s.flux_linkage_Wb))
        nl_t, nl_f = np.array(nl_t), np.array(nl_f)
        if skew_e > 0:
            nl_t = D.skewed(nl_t - nl_t.mean(), skew_e, antiperiodic=False) + nl_t.mean()
            nl_f = D.skewed(nl_f, skew_e, antiperiodic=True)
        e = D.emf_waveforms(nl_f, n_eff, f_e)
        emf = {"cogging_Nm": nl_t.tolist(), "cogging_pp_Nm": float(nl_t.max() - nl_t.min()),
               "flux_Wb": (nl_f * n_eff).tolist(), "emf_V": e.tolist(),
               "emf_phase_peak_V": float(np.max(np.abs(e[:, 0]))), "ke_Vs_rad": float(D.harmonic(e[:, 0], 1)[0] / (w_e / pe))}

    # 5. peak current: the current angle of the most torque, advanced from the rated one
    peak_angles = [gamma, gamma + 15.0, gamma + 30.0]
    peak_t = [point(n_eff * i_p, g)[0] for g in peak_angles]
    k_peak = int(np.argmax(peak_t))
    if k_peak == len(peak_angles) - 1:
        peak_angles.append(gamma + 45.0)
        peak_t.append(point(n_eff * i_p, gamma + 45.0)[0])
        k_peak = int(np.argmax(peak_t))
    t_peak = float(max(peak_t)) * k_sk1
    # rated torque from the fundamental at the rated point, for the ratio to the sweep
    record = {
        "analysed": True, "principle": design["principle"],
        "torque_Nm": t_mean, "peak_torque_Nm": t_peak, "ripple": D.ripple(torque_w),
        "torque_waveform_Nm": torque_w.tolist(), "torque_harmonics_Nm": D.torque_harmonics(torque_w),
        "kt_Nm_A": t_mean / i_r, "efficiency": eta, "output_power_W": p_out,
        "losses_W": {"copper": copper_w, "stator_iron": stator_w, "rotor": rotor_w, "total": loss_w},
        "copper_loss_20C_W": 1.5 * i_r ** 2 * winding["resistance_20C_ohm"],
        "km_Nm_sqrtW": t_mean / math.sqrt(1.5 * i_r ** 2 * winding["resistance_20C_ohm"]),
        "winding": winding, "n_eff_voltage": n_voltage, "n_eff_target": n_target,
        "gamma_deg": gamma, "gamma_peak_deg": peak_angles[k_peak],
        "torque_levels_Nm": list(map(float, t_levels)), "ampere_turn_levels": list(map(float, levels)), "sequence": seq, "skew_factor": k_sk1,
        "phi_pm_per_turn_Wb": phi_pm, "cogging_probe_Nm": cogging_probe,
        "voltage": {"phase_fundamental_V": float(v1), "line_peak_V": line_peak, "phase_limit_V": v_phase_max,
                    "line_limit_V": drive["modulation"] * drive["bus_voltage_V"],
                    "violation": max(0.0, line_peak / (drive["modulation"] * drive["bus_voltage_V"]) - 1.0)},
        "waveforms": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in wave.items()},
        "no_load": emf, "core": core_stats, "electrical_Hz": f_e,
        "solves": runner.count, "seconds": runner.seconds,
    }
    record["masses"] = masses(design, runner.meta, winding, settings["materials"])
    return record


# ----------------------------------------------------------------------------- switched reluctance

def srm_iron_loss(spec, field_files, frequency):
    """Iron loss estimate of an SRM: every stator and rotor element at the peak flux density it reaches at
    the aligned position, at the phase frequency (alternating-loss formula of the stator material)."""
    material = spec["materials"]["stator_core"]
    total = 0.0
    for path in field_files:
        with np.load(path) as d:
            b = np.linalg.norm(d["b"], axis=1)
            total += float(np.sum(d["volume"] * material["density_kg_m3"] * losses.iron_loss_density(material, frequency, b)))
            rb = np.linalg.norm(d["rotor_b"], axis=1)
            sel = d["rotor_kind"] == 0
            total += float(np.sum(d["rotor_volume"][sel] * material["density_kg_m3"]
                                  * losses.iron_loss_density(material, frequency, rb[sel])))
    return total


def evaluate_srm(design, drive, settings, workdir, log=None):
    params = design["params"]
    nr = int(design["rotor_poles"])
    phases = 3
    runner = FieldRunner(params, settings["analysis"], workdir, keep=bool(settings.get("keep_workdir")),
                         kind=design.get("geometry_kind", "section2d"), solver=design.get("solver", "elmer_sections"))
    side, n_c, turn = design["side_area_mm2"], design["coils_per_phase"], design["turn_length_mm"]
    ni_top = settings["fill_range"][1] * side * 30.0           # 30 A/mm2 in the copper: beyond any peak point
    levels = [ni_top * x for x in (0.04, 0.12, 0.25, 0.45, 0.7, 1.0)]
    pitch_deg = 360.0 / nr
    n_th = int(settings.get("srm_positions", 9))
    thetas = [0.5 * pitch_deg * k / (n_th - 1) for k in range(n_th)]
    flux = np.zeros((n_th, len(levels)))
    torque = np.zeros((n_th, len(levels)))
    aligned_files = []
    for i, th in enumerate(thetas):
        for j, ni in enumerate(levels):
            core = i == 0 and j >= len(levels) - 3
            s = runner.solve(th, (ni, 0.0, 0.0), core_field=core, tag=f"map_{i:02d}_{j}")
            flux[i, j], torque[i, j] = s.flux_linkage_Wb[0], s.torque_Nm
            if core:
                aligned_files.append((ni, s.field_file))
    pmap = D.SRMPhaseMap(np.radians(thetas), levels, flux, torque, nr)
    copper, temp = settings["materials"]["copper"], drive["winding_temp_C"]
    f_ph = drive["speed_rpm"] / 60.0 * nr
    i_rms = drive["rated_current_A"] / math.sqrt(2)
    rho = copper["resistivity_20C_ohm_m"] * (1 + copper["temp_coefficient_per_K"] * (temp - 20))
    n_max = settings["fill_range"][1] * side / D.awg_area_mm2(32)
    n_min = max(1.0, 0.002 * n_max)
    candidates = np.geomspace(n_min, n_max, 9)
    best = None
    for n_try in candidates:
        winding = D.winding_design(n_try, n_c, side, turn, copper, drive, temp, tuple(settings["fill_range"]))
        if winding is None:
            continue
        if settings.get("max_j_rated_rms_A_mm2") and winding["j_rated_rms_A_mm2"] > settings["max_j_rated_rms_A_mm2"]:
            continue
        n_eff, r = winding["n_eff"], winding["resistance_ohm"]
        res = D.srm_best(pmap, n_eff, r, drive["modulation"] * drive["bus_voltage_V"], drive["speed_rpm"], phases,
                         i_rms, drive["peak_current_A"])
        p = res["mean_torque_Nm"] * 2 * math.pi * drive["speed_rpm"] / 60
        cu = phases * res["rms_current_A"] ** 2 * r
        ni_peak = res["peak_current_A"] * n_eff
        k = int(np.argmin([abs(ni - ni_peak) for ni, _ in aligned_files]))
        fe = srm_iron_loss(settings["loss_spec"], [aligned_files[k][1]], f_ph)
        eta = p / (p + cu + fe) if p > 0 else 0.0
        ok = eta >= settings["min_efficiency"]
        score = (ok, res["mean_torque_Nm"] if ok else eta)
        if best is None or score > best[0]:
            best = (score, winding, res, cu, fe, eta, p)
    if best is None:
        return {"analysed": False, "reason": "no winding with a fill in range", "solves": runner.count, "seconds": runner.seconds}
    _, winding, res, cu, fe, eta, p = best
    n_eff, r = winding["n_eff"], winding["resistance_ohm"]
    peak_mean, peak_ripple, _ = D.srm_ideal(pmap, n_eff * drive["peak_current_A"], phases)
    peak = {"mean_torque_Nm": peak_mean, "ripple": peak_ripple, "rms_current_A": drive["peak_current_A"] * math.sqrt(2.0 / 3.0)}
    t = res["torque_Nm"]
    shift = len(t) // phases
    wave = {"time_s": res["time_s"].tolist(),
            "current_A": np.stack([np.roll(res["current_A"], k * shift) for k in range(phases)], axis=1).tolist(),
            "flux_Wb": np.stack([np.roll(res["flux_Wb"], k * shift) for k in range(phases)], axis=1).tolist(),
            "voltage_V": np.stack([np.roll(res["voltage_V"], k * shift) for k in range(phases)], axis=1).tolist()}
    rec = {"analysed": True, "principle": "srm", "torque_Nm": res["mean_torque_Nm"], "peak_torque_Nm": peak["mean_torque_Nm"],
           "ripple": res["ripple"], "torque_waveform_Nm": t.tolist(), "kt_Nm_A": res["mean_torque_Nm"] / drive["rated_current_A"],
           "efficiency": eta, "output_power_W": p, "losses_W": {"copper": cu, "stator_iron": fe, "rotor": 0.0, "total": cu + fe},
           "copper_loss_20C_W": phases * res["rms_current_A"] ** 2 * winding["resistance_20C_ohm"],
           "km_Nm_sqrtW": res["mean_torque_Nm"] / math.sqrt(phases * res["rms_current_A"] ** 2 * winding["resistance_20C_ohm"]),
           "winding": winding, "srm": {"theta_on_deg": math.degrees(res["theta_on"]), "theta_off_deg": math.degrees(res["theta_off"]),
                                        "i_ref_A": res["i_ref"], "rms_current_A": res["rms_current_A"],
                                        "peak_current_A": res["peak_current_A"], "peak_point_ripple": peak["ripple"],
                                        "peak_point_rms_A": peak["rms_current_A"],
                                        "map_ampere_turns": levels, "map_theta_deg": thetas,
                                        "map_flux_Wb": flux.tolist(), "map_torque_Nm": torque.tolist()},
           "voltage": {"line_limit_V": drive["modulation"] * drive["bus_voltage_V"], "violation": 0.0},
           "waveforms": wave, "electrical_Hz": f_ph, "solves": runner.count, "seconds": runner.seconds}
    rec["masses"] = masses(design, runner.meta, winding, settings["materials"])
    return rec


def evaluate(design, drive, settings, workdir, log=None):
    """Record of one design (see the module text); analysis failures come back as analysed = False."""
    began = time.time()
    try:
        if design["principle"] == "srm":
            rec = evaluate_srm(design, drive, settings, workdir, log)
        else:
            rec = evaluate_synchronous(design, drive, settings, workdir, log)
    except Exception as error:               # meshing or solver failure: the design is discarded
        rec = {"analysed": False, "reason": f"analysis failed: {str(error).splitlines()[0] if str(error) else type(error).__name__}"}
    rec["wall_s"] = time.time() - began
    if not settings.get("keep_workdir"):
        shutil.rmtree(workdir, ignore_errors=True)
    return rec


def save(path, record):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(record, f)
    os.replace(tmp, path)
