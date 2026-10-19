"""
Torque, speed and efficiency map of one design with a fixed winding.

The magnetostatic field depends on the ampere-turns but not on the speed. The field is therefore
solved at a few load levels, and every speed is derived from them:

    torque            from the load level (interpolated in ampere-turns)
    induced voltage   speed * d(flux)/d(angle)
    iron loss         stator core a_h * f + a_e * f^2 + a_x * f^1.5 and rotor eddy currents
                      (rotor iron, housing, magnets) a * f^2, with the coefficients of the load level
    copper loss       resistance at the winding temperature of the thermal network

Assumptions: sinusoidal current in phase with the induced voltage (no field weakening); copper,
stator iron and rotor eddy-current losses (no mechanical loss); phases magnetically independent.
"""

import hashlib
import json
import math
import os
import shutil

import numpy as np

from emachine.physics import losses, torque
from emachine.physics import thermal as thermal_network
from emachine.physics import winding as winding_model
from emachine.physics.interpolation import pchip  # noqa: F401  (also used by callers as effmap.pchip)
from emachine.pipeline import design_space as design
from emachine.pipeline import evaluate
from emachine.pipeline.sweep import field_analysis


# ----------------------------------------------------------------------------- field solutions

def ampere_turn_ceiling(spec, values, turns, overload):
    """
    Highest ampere-turns (peak) of the map: the current cut-off, or `overload` times the
    ampere-turns of the current-density limit, whichever is lower.
    """
    winding = design.machine_of(spec).winding(spec, values)
    lim = spec["limits"]
    by_cutoff = turns * lim["max_current_A"]
    by_density = (overload * math.sqrt(2) * lim["max_current_density_A_mm2"] * winding.coil_area_mm2
                  * winding.fill_factor)
    return min(by_cutoff, by_density), by_cutoff <= by_density


def choose_levels(rated, ceiling, count):
    """Ampere-turn levels from zero to the ceiling, with the rated value among them."""
    levels = list(np.linspace(0.0, ceiling, max(count, 2)))
    if 0 < rated < ceiling and min(abs(rated - v) for v in levels) > 0.03 * ceiling:
        levels.append(rated)
    elif 0 < rated <= ceiling:
        k = int(np.argmin([abs(rated - v) for v in levels]))
        if 0 < k < len(levels) - 1:
            levels[k] = rated            # move the nearest inner level onto the rated value
    return sorted(float(v) for v in levels)


def _signature(spec, values):
    relevant = evaluate.keyed_spec(spec, ("machine", "materials", "winding", "fidelity"))
    text = json.dumps({"spec": relevant, "values": evaluate.keyed_values(spec, values), "model": evaluate.MODEL_VERSION},
                      sort_keys=True)
    return hashlib.sha1(text.encode()).hexdigest()[:20]


def solve_level(spec, values, ampere_turns_peak, workdir, analyse=None):
    """Field solution of one load level, reduced to what the map needs."""
    request = design.geometry(spec, values)
    if analyse is None:
        analyse = field_analysis(request.kind)
    parameters = request.parameters
    parameters["analysis"]["coil_current_A"] = float(ampere_turns_peak)
    result = analyse(parameters, int(spec["fidelity"]["positions"]), workdir, int(spec["optimizer"]["jobs"]))
    files = [f for f in result.get("core_field_files", []) if f]
    iron = losses.iron_loss_coefficients(spec, files) if files else {
        **{name: 0.0 for name in losses.COEFFICIENTS},
        "core_b_max_T": None, "core_b_p95_T": None, "core_b_mean_T": None, "core_mass_kg": None}
    level = {"ampere_turns_peak": float(ampere_turns_peak),
             "torque_Nm": [float(v) for v in result["torque_Nm"]],
             "flux_per_turn_Wb": [float(v) for v in result["flux_per_turn_Wb"]],
             "seconds": float(result.get("seconds") or 0.0),
             "elements": result.get("elements"), **iron}
    shutil.rmtree(workdir, ignore_errors=True)
    return level


def solve_levels(spec, values, ampere_turns, outdir, analyse=None, log=print):
    """
    Field solutions for a list of load levels. Results are kept in <outdir>/load_levels.json and
    reused when the same design is asked for again.
    """
    os.makedirs(outdir, exist_ok=True)
    store = os.path.join(outdir, "load_levels.json")
    signature = _signature(spec, values)
    known = {}
    if os.path.isfile(store):
        with open(store) as f:
            data = json.load(f)
        if data.get("signature") == signature:
            known = {f"{l['ampere_turns_peak']:.6g}": l for l in data["levels"]}
    solved = 0
    for value in ampere_turns:
        key = f"{value:.6g}"
        if key in known:
            continue
        level = solve_level(spec, values, value, os.path.join(outdir, "field", f"level_{key}"), analyse)
        known[key] = level
        solved += 1
        if log:
            log(f"  load level {value:8.1f} A-turns: mean phase torque {np.mean(level['torque_Nm']):.4f} Nm "
                f"({level['seconds']:.0f} s)")
        tmp = store + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"signature": signature, "levels": sorted(known.values(), key=lambda l: l["ampere_turns_peak"])}, f)
        os.replace(tmp, store)
    shutil.rmtree(os.path.join(outdir, "field"), ignore_errors=True)
    wanted = {f"{v:.6g}" for v in ampere_turns}
    levels = sorted((l for k, l in known.items() if k in wanted), key=lambda l: l["ampere_turns_peak"])
    return levels, solved


# ----------------------------------------------------------------------------- the map

class Machine:
    """A design with a fixed winding, described by its load-level results."""

    def __init__(self, spec, values, levels, turns):
        if len(levels) < 2:
            raise ValueError("A map needs at least two load levels.")
        self.spec, self.values, self.turns = spec, values, int(turns)
        machine = design.machine_of(spec)
        self.d = machine.derive(spec, values)
        self.winding = machine.winding(spec, values)
        # Torque of the machine: one phase solved and the others shifted, or all phases solved together.
        self.phase_sum = machine.excitation(spec, values).mode == "single_phase_shifted"
        self.phases = spec["machine"]["phases"]
        self.pole_pairs = self.d["pole_pairs"]
        self.ni = np.array([l["ampere_turns_peak"] for l in levels], dtype=float)
        self.level_torque = (self.phases if self.phase_sum else 1) * np.array([np.mean(l["torque_Nm"]) for l in levels])
        self.level_flux = np.array([l["flux_per_turn_Wb"] for l in levels], dtype=float)
        self.level_loss = {name: np.array([l.get(name, 0.0) for l in levels], dtype=float)
                           for name in losses.COEFFICIENTS}
        # Rotor eddy-current spectra (one row per level) and the part data that do not change with load.
        self.level_spectra = {}
        for name in losses.SPECTRA:
            rows = [l.get(name) or [] for l in levels]
            if rows[0] and len({len(r) for r in rows}) == 1:
                self.level_spectra[name] = np.array(rows, dtype=float)
        self.rotor_parts = {k: v for k, v in levels[0].items() if k.endswith("_width_m") or k.endswith("_b_dc_T")}
        self.samples = self.level_flux.shape[1]
        self.shape = winding_model.current_shape(self.samples)
        copper = spec["materials"]["copper"]
        self.alpha = copper["temp_coefficient_per_K"]
        self.r1_20 = winding_model.winding_resistance(copper, self.winding, 20.0)
        self.rise = thermal_network.response(machine.thermal_network(spec, values), ("winding", "core", "rotor"))
        self.ambient = spec["operating_point"]["ambient_C"]
        self.phase_factor = 1.0 if self.phases == 1 else math.sqrt(3)
        # Torque as a monotonic function of ampere-turns, for the inversion.
        self._ni_dense = np.linspace(self.ni[0], self.ni[-1], 801)
        self._torque_dense = np.maximum.accumulate(pchip(self.ni, self.level_torque, self._ni_dense))

    def torque(self, ampere_turns):
        return pchip(self.ni, self.level_torque, ampere_turns)

    def ampere_turns_for(self, torque_Nm):
        """Peak ampere-turns that give a mean machine torque (inverse of `torque`)."""
        return np.interp(torque_Nm, self._torque_dense, self._ni_dense)

    def no_load_speed(self):
        """Speed in rpm at which the induced voltage alone equals the maximum bus voltage."""
        slope = np.max(np.abs(winding_model.flux_slope(pchip(self.ni, self.level_flux, [0.0])[0])))
        omega_e = self.spec["limits"]["bus_voltage_V"][1] / (self.turns * self.phase_factor * slope)
        return omega_e * 60.0 / (2 * math.pi * self.pole_pairs)

    def grid(self, speeds_rpm, ampere_turns):
        """
        Operating points for every pair of speed and ampere-turns.
        Returns a dictionary of arrays with shape (speeds, ampere-turn values).
        """
        lim = self.spec["limits"]
        speeds = np.asarray(speeds_rpm, dtype=float)[:, None]
        ni = np.asarray(ampere_turns, dtype=float)
        machine_torque = self.torque(ni)[None, :] * np.ones_like(speeds)
        flux = pchip(self.ni, self.level_flux, ni)
        slope = np.array([winding_model.flux_slope(row) for row in flux])
        coefficients = {name: np.maximum(pchip(self.ni, series, ni), 0.0)[None, :]
                        for name, series in self.level_loss.items()}
        coefficients.update({name: np.maximum(pchip(self.ni, series, ni), 0.0)[None, :, :]
                             for name, series in self.level_spectra.items()})
        coefficients.update(self.rotor_parts)

        frequency = self.pole_pairs * speeds / 60.0
        iron, rotor = losses.loss_at(coefficients, frequency, self.spec["materials"])   # W per phase
        k = (self.r1_20 * (ni / math.sqrt(2)) ** 2)[None, :]            # copper loss per phase at 20 C
        (w_cu, w_fe, w_ro), (m_cu, m_fe, m_ro) = self.rise["winding"], self.rise["rotor"]
        gain = 1.0 - w_cu * k * self.alpha
        with np.errstate(divide="ignore", invalid="ignore"):
            steady_winding = (self.ambient + w_cu * k * (1 - 20.0 * self.alpha) + w_fe * iron + w_ro * rotor) / gain
        steady_winding = np.where(gain > 0, steady_winding, np.inf)    # no steady state: thermal runaway
        within_winding = steady_winding <= lim["max_winding_temp_C"] + 1e-9
        # Beyond the continuous limit the machine runs for a short time only; the copper loss is
        # then taken at the winding temperature limit.
        winding = np.where(within_winding, steady_winding, lim["max_winding_temp_C"])
        factor = 1.0 + self.alpha * (winding - 20.0)
        copper = k * factor
        magnet = self.ambient + m_cu * copper + m_fe * iron + m_ro * rotor

        omega_e = 2 * math.pi * frequency
        resistive = (self.r1_20 * factor)[:, :, None] * ni[None, :, None] * self.shape[None, None, :]
        induced = omega_e[:, :, None] * slope[None, :, :]
        volts_per_turn = np.max(np.abs(resistive + induced), axis=2)
        bus = self.turns * volts_per_turn * self.phase_factor
        current = (ni / self.turns)[None, :] * np.ones_like(speeds)
        density = (ni / math.sqrt(2) / (self.winding.coil_area_mm2 * self.winding.fill_factor))[None, :] \
            * np.ones_like(speeds)

        loss = self.phases * (copper + iron + rotor)
        output = machine_torque * 2 * math.pi * speeds / 60.0
        with np.errstate(divide="ignore", invalid="ignore"):
            efficiency = np.where(output > 0, output / (output + loss), 0.0)
        within_drive = (bus <= lim["bus_voltage_V"][1] * (1 + 1e-9)) & (current <= lim["max_current_A"] * (1 + 1e-9))
        continuous = (within_drive & within_winding & (magnet <= lim["max_magnet_temp_C"] + 1e-9)
                      & (density <= lim["max_current_density_A_mm2"] * (1 + 1e-9)))
        return {
            "speed_rpm": speeds * np.ones_like(machine_torque),
            "ampere_turns_peak": ni[None, :] * np.ones_like(speeds),
            "torque_Nm": machine_torque,
            "peak_current_A": current,
            "rms_current_A": current / math.sqrt(2),
            "current_density_A_mm2": density,
            "bus_voltage_needed_V": bus,
            "copper_loss_W": self.phases * copper,
            "iron_loss_W": self.phases * iron,
            "rotor_loss_W": self.phases * rotor,
            "loss_W": loss,
            "output_power_W": output,
            "input_power_W": output + loss,
            "efficiency": efficiency,
            "winding_C": winding,
            "steady_winding_C": steady_winding,
            "magnet_C": magnet,
            "within_drive_limits": within_drive,
            "continuous": continuous,
        }

    def envelope(self, speeds_rpm, resolution=801):
        """Highest torque inside the drive limits and inside the continuous limits, per speed."""
        ni = np.linspace(self.ni[0], self.ni[-1], resolution)
        g = self.grid(speeds_rpm, ni)
        torque_axis = self._torque_dense if resolution == 801 else np.maximum.accumulate(self.torque(ni))
        out = {"speed_rpm": np.asarray(speeds_rpm, dtype=float)}
        for name, mask in (("drive", g["within_drive_limits"]), ("continuous", g["continuous"])):
            # The region is the set of loads from zero up to the first violation.
            first_bad = np.where(mask.all(axis=1), mask.shape[1], np.argmin(mask, axis=1))
            last_ok = first_bad - 1
            out[name + "_torque_Nm"] = np.where(last_ok >= 0, torque_axis[np.maximum(last_ok, 0)], 0.0)
            out[name + "_ampere_turns"] = np.where(last_ok >= 0, ni[np.maximum(last_ok, 0)], 0.0)
        return out

    def point(self, speed_rpm, ampere_turns_peak):
        """One operating point as plain numbers."""
        g = self.grid([speed_rpm], [ampere_turns_peak])
        return {k: (bool(v[0, 0]) if v.dtype == bool else float(v[0, 0])) for k, v in g.items()}


def compute(machine, speeds_rpm, torque_count=61):
    """The map on a regular grid of speed and torque, with both envelopes."""
    speeds = np.asarray(speeds_rpm, dtype=float)
    torques = np.linspace(0.0, float(machine._torque_dense[-1]), torque_count)
    grid = machine.grid(speeds, machine.ampere_turns_for(torques))
    grid["torque_Nm"] = np.ones((len(speeds), 1)) * torques[None, :]      # exactly the regular axis
    grid["output_power_W"] = grid["torque_Nm"] * 2 * math.pi * grid["speed_rpm"] / 60.0
    grid["input_power_W"] = grid["output_power_W"] + grid["loss_W"]
    with np.errstate(divide="ignore", invalid="ignore"):
        grid["efficiency"] = np.where(grid["output_power_W"] > 0, grid["output_power_W"] / grid["input_power_W"], 0.0)
    return {"speeds_rpm": speeds, "torques_Nm": torques, "grid": grid, "envelope": machine.envelope(speeds)}


def level_table(machine, levels):
    """One row per load level: what the field solutions gave."""
    rows = []
    for level, machine_torque in zip(levels, machine.level_torque):
        ni = level["ampere_turns_peak"]
        waveform = np.asarray(level["torque_Nm"])
        total = torque.machine_torque(waveform, machine.phases) if machine.phase_sum else waveform
        rows.append({"ampere_turns_peak": ni, "peak_current_A": ni / machine.turns,
                     "torque_Nm": float(machine_torque),
                     "torque_per_kAt": float(machine_torque / ni * 1e3) if ni > 0 else None,
                     "ripple": torque.metrics(total)["ripple"] if machine_torque > 1e-9 else None,
                     "peak_to_peak_Nm": float(total.max() - total.min()),
                     **{name: level.get(name, 0.0) for name in losses.COEFFICIENTS},
                     "rotor_loss_W_at_rated_speed": float(losses.loss_at(
                         level, machine.d["electrical_frequency_Hz"], machine.spec["materials"])[1]),
                     "core_b_p95_T": level.get("core_b_p95_T")})
    return rows


def summary(machine, result, rated_speed, rated_ampere_turns):
    """Key numbers of a map."""
    g, env = result["grid"], result["envelope"]
    speeds = result["speeds_rpm"]
    inside = g["within_drive_limits"] & (g["output_power_W"] > 0)
    cont = g["continuous"] & (g["output_power_W"] > 0)
    out = {"rated": machine.point(rated_speed, rated_ampere_turns), "no_load_speed_rpm": machine.no_load_speed(),
           "standstill_peak_torque_Nm": float(env["drive_torque_Nm"][0]),
           "standstill_continuous_torque_Nm": float(env["continuous_torque_Nm"][0])}
    for name, mask in (("best", inside), ("best_continuous", cont)):
        if mask.any():
            eff = np.where(mask, g["efficiency"], -1.0)
            i, j = np.unravel_index(int(np.argmax(eff)), eff.shape)
            out[name] = {"efficiency": float(eff[i, j]), "speed_rpm": float(speeds[i]),
                         "torque_Nm": float(result["torques_Nm"][j]), "output_power_W": float(g["output_power_W"][i, j])}
    for name in ("drive", "continuous"):
        power = env[name + "_torque_Nm"] * 2 * math.pi * speeds / 60.0
        k = int(np.argmax(power))
        out[f"max_{name}_power"] = {"output_power_W": float(power[k]), "speed_rpm": float(speeds[k]),
                                    "torque_Nm": float(env[name + "_torque_Nm"][k])}
    # Corner speed: highest speed at which the standstill peak torque is still available.
    full = env["drive_torque_Nm"] >= env["drive_torque_Nm"][0] * (1 - 1e-6)
    out["corner_speed_rpm"] = float(speeds[np.nonzero(full)[0][-1]]) if full.any() else 0.0
    return out
