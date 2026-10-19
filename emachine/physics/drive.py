"""
A machine on a given drive (T58, T61): fixed DC-link voltage and phase current, the number of turns
chosen by the voltage at the rated speed. Pure functions; the field solutions come from the pipeline.

Conventions
    Field solutions are per turn: every coil of a phase has one turn, all coils in series, and the
    phase carries the ampere-turns of one coil. A winding with N_c turns per coil and a parallel paths
    has N_eff = N_c / a: coil ampere-turns N_eff * I, phase flux linkage N_eff * Phi.
    Currents (three phases, sequence s = +1 or -1, angle gamma):  i_k = I cos(theta_e + gamma - s 2 pi k / 3).
    Voltages are compared line to line with the DC link: space-vector modulation reaches a line-to-line
    peak of V_dc; `modulation` (0.95) keeps a margin.
"""

import math

import numpy as np

from .winding import awg_diameter_mm, copper_resistivity


# ----------------------------------------------------------------------------- three-phase quantities

def clarke(abc):
    """Amplitude-invariant Clarke transform of three phase values (last axis)."""
    a, b, c = np.moveaxis(np.asarray(abc, dtype=float), -1, 0)
    return (2.0 / 3.0) * (a - 0.5 * b - 0.5 * c), (2.0 / 3.0) * (math.sqrt(3) / 2) * (b - c)


def phase_currents(amplitude, theta_e, gamma, sequence=1, phases=3):
    """Phase currents i_k = I cos(theta_e + gamma - s 2 pi k / m) (radians)."""
    return np.array([amplitude * math.cos(theta_e + gamma - sequence * 2 * math.pi * k / phases) for k in range(phases)])


def flux_torque(psi_abc, i_abc, pole_pairs):
    """Torque of the fundamental from the space vectors: 3/2 p (psi_alpha i_beta - psi_beta i_alpha)."""
    pa, pb = clarke(psi_abc)
    ia, ib = clarke(i_abc)
    return 1.5 * pole_pairs * (pa * ib - pb * ia)


def sequence_from_flux(psi_0, psi_1, step_e):
    """+1 when the flux space vector turns forwards (with the rotor) between two positions step_e apart
    (electrical radians), -1 when backwards (a vernier machine with P_r = N_s - P_w), 0 if no flux."""
    a0, b0 = clarke(psi_0)
    a1, b1 = clarke(psi_1)
    if math.hypot(a0, b0) < 1e-12 or math.hypot(a1, b1) < 1e-12:
        return 0
    turn = math.atan2(a0 * b1 - b0 * a1, a0 * a1 + b0 * b1)
    return 1 if turn * step_e > 0 else -1


# ----------------------------------------------------------------------------- waveforms

def full_period(half, antiperiodic=True):
    """Samples over half a period completed to a full one: f(t + T/2) = -f(t) (or +f for torque)."""
    half = np.asarray(half, dtype=float)
    return np.concatenate([half, -half if antiperiodic else half], axis=0)


def spectral_derivative(samples, period):
    """d/dx of periodic samples over one period (first axis)."""
    f = np.asarray(samples, dtype=float)
    n = f.shape[0]
    k = np.fft.fftfreq(n, d=1.0 / n)
    spec = np.fft.fft(f, axis=0) * (1j * 2 * math.pi * k / period).reshape((-1,) + (1,) * (f.ndim - 1))
    if n % 2 == 0:
        spec[n // 2] = 0.0
    return np.real(np.fft.ifft(spec, axis=0))


def harmonic(samples, order):
    """Amplitude and phase of a harmonic of periodic samples (one period, first axis)."""
    f = np.asarray(samples, dtype=float)
    c = np.fft.fft(f, axis=0)[order] * 2.0 / f.shape[0]
    return np.abs(c), np.angle(c)


def phase_waveforms(flux_half, current_half, n_eff, resistance_ohm, electrical_Hz):
    """
    Phase quantities over one electrical period from a sweep over half a period:
    flux linkage psi = N_eff Phi, current i, voltage v = R i + d psi / dt, and the line voltages.
    flux_half (positions x phases) per turn, current_half (positions x phases) phase current in A.
    """
    psi = full_period(np.asarray(flux_half) * n_eff)
    current = full_period(current_half)
    period = 1.0 / electrical_Hz
    v = resistance_ohm * current + spectral_derivative(psi, period)
    phases = psi.shape[1]
    line = np.stack([v[:, k] - v[:, (k + 1) % phases] for k in range(phases)], axis=1)
    t = np.arange(psi.shape[0]) * period / psi.shape[0]
    return {"time_s": t, "flux_Wb": psi, "current_A": current, "voltage_V": v, "line_voltage_V": line}


def emf_waveforms(flux_half, n_eff, electrical_Hz):
    psi = full_period(np.asarray(flux_half) * n_eff)
    return spectral_derivative(psi, 1.0 / electrical_Hz)


# ----------------------------------------------------------------------------- winding

AWG_RANGE = (12, 32)
MAX_STRANDS = 8


def awg_area_mm2(awg):
    return math.pi * awg_diameter_mm(awg) ** 2 / 4


def divisors(n):
    return [d for d in range(1, n + 1) if n % d == 0]


def winding_options(coils_per_phase, n_eff_max, parallel_allowed=True, tolerance=0.05):
    """(turns per coil, parallel paths) with N_c / a <= n_eff_max. Fewer parallel paths come first as long as
    they reach within `tolerance` of the largest N_eff (more paths only to place the turns more finely)."""
    out = []
    for a in (divisors(coils_per_phase) if parallel_allowed else [1]):
        n_c = int(math.floor(n_eff_max * a + 1e-9))
        if n_c >= 1:
            out.append((n_c / a, a, n_c))
    if not out:
        return []
    best = max(o[0] for o in out)
    good = sorted([o for o in out if o[0] >= (1 - tolerance) * best], key=lambda o: o[1])
    rest = sorted([o for o in out if o[0] < (1 - tolerance) * best], key=lambda o: (-o[0], o[1]))
    return [(n_c, a) for _, a, n_c in good + rest]


def choose_conductor(side_area_mm2, turns_per_coil, fill_range=(0.5, 0.7), awg_range=AWG_RANGE,
                     max_strands=MAX_STRANDS, fill_slack=0.04):
    """The AWG and number of strands in hand for the coil side: copper fill (turns x strands x wire area /
    side area) within the range; of the fills within `fill_slack` of the best, the fewest strands and then
    the thickest wire. Returns dict or None when nothing reaches the lower fill."""
    found = []
    for awg in range(awg_range[0], awg_range[1] + 1):
        a1 = awg_area_mm2(awg)
        for strands in range(1, max_strands + 1):
            fill = turns_per_coil * strands * a1 / side_area_mm2
            if fill > fill_range[1] + 1e-9:
                break
            if fill >= fill_range[0] - 1e-9:
                found.append((fill, strands, awg, a1))
    if not found:
        return None
    best = max(f[0] for f in found)
    fill, strands, awg, a1 = min((f for f in found if f[0] >= best - fill_slack), key=lambda f: (f[1], f[2]))
    return {"awg": awg, "strands": strands, "wire_diameter_mm": awg_diameter_mm(awg), "conductor_area_mm2": strands * a1,
            "fill": fill}


def phase_resistance(coils_per_phase, turns_per_coil, paths, turn_length_mm, conductor_area_mm2, copper, temp_C):
    """Resistance of a phase: coils in series per path, `paths` paths in parallel."""
    rho = copper_resistivity(copper, temp_C)
    per_coil = rho * turns_per_coil * turn_length_mm * 1e-3 / (conductor_area_mm2 * 1e-6)
    return per_coil * coils_per_phase / paths ** 2


def winding_design(n_eff_max, coils_per_phase, side_area_mm2, turn_length_mm, copper, drive, temp_C,
                   fill_range=(0.5, 0.7)):
    """
    The winding with the most effective turns up to n_eff_max whose wire fills the side within the
    range. Returns the winding (turns per coil, paths, AWG, strands, fill, N_eff, resistance at temp_C and
    20 C, current densities at the rated and peak currents) or None.
    """
    for n_c, a in winding_options(coils_per_phase, n_eff_max):
        wire = choose_conductor(side_area_mm2, n_c, fill_range)
        if wire is None:
            continue
        r = phase_resistance(coils_per_phase, n_c, a, turn_length_mm, wire["conductor_area_mm2"], copper, temp_C)
        r20 = phase_resistance(coils_per_phase, n_c, a, turn_length_mm, wire["conductor_area_mm2"], copper, 20.0)
        area = a * wire["conductor_area_mm2"]
        return dict(wire, turns_per_coil=n_c, paths=a, n_eff=n_c / a, series_turns=n_c * coils_per_phase / a,
                    coils_per_phase=coils_per_phase, resistance_ohm=r, resistance_20C_ohm=r20,
                    j_rated_rms_A_mm2=drive["rated_current_A"] / math.sqrt(2) / area,
                    j_peak_rms_A_mm2=drive["peak_current_A"] / math.sqrt(2) / area)
    return None


# ----------------------------------------------------------------------------- dq machine model

class FluxMap:
    """Flux per turn (alpha, beta, every level) at one rotor position for currents of one angle gamma, at
    several coil ampere-turns, interpolated linearly (and extrapolated) in the ampere-turns."""

    def __init__(self, ampere_turns, psi_abc, torque=None):
        order = np.argsort(ampere_turns)
        self.ni = np.asarray(ampere_turns, dtype=float)[order]
        self.psi = np.asarray(psi_abc, dtype=float)[order]
        self.torque = None if torque is None else np.asarray(torque, dtype=float)[order]

    def at(self, ni):
        return np.array([np.interp(ni, self.ni, self.psi[:, k], left=None, right=None) if self.ni[0] <= ni <= self.ni[-1]
                         else self._extrapolate(ni, k) for k in range(self.psi.shape[1])])

    def _extrapolate(self, ni, k):
        if ni < self.ni[0]:
            x0, x1 = 0, 1
        else:
            x0, x1 = len(self.ni) - 2, len(self.ni) - 1
        slope = (self.psi[x1, k] - self.psi[x0, k]) / (self.ni[x1] - self.ni[x0])
        return self.psi[x0, k] + slope * (ni - self.ni[x0])


def voltage_amplitude(psi_abc_turn, i_abc, n_eff, resistance, electrical_Hz, theta_e, gamma, sequence):
    """Fundamental phase voltage amplitude in the steady state from the flux space vector at one position:
    v = R i + j omega psi (space vectors, amplitude invariant)."""
    pa, pb = clarke(np.asarray(psi_abc_turn) * n_eff)
    ia, ib = clarke(i_abc)
    w = 2 * math.pi * electrical_Hz * sequence
    va = resistance * ia - w * pb
    vb = resistance * ib + w * pa
    return math.hypot(va, vb)


def skew_factor(order, skew_rad):
    """Skew factor of a harmonic: sin(n theta / 2) / (n theta / 2), theta the skew in electrical radians."""
    x = order * skew_rad / 2
    return 1.0 if abs(x) < 1e-12 else math.sin(x) / x


def skewed(samples_half, skew_e_rad, antiperiodic):
    """Continuous skew over skew_e_rad (electrical) applied to samples over half a period: every harmonic of
    the full-period signal is multiplied by its skew factor (the torque is periodic in half a period)."""
    f = np.asarray(samples_half, dtype=float)
    full = full_period(f, antiperiodic)
    n = full.shape[0]
    spec = np.fft.fft(full, axis=0)
    k = np.abs(np.fft.fftfreq(n, d=1.0 / n))
    factors = np.array([skew_factor(int(kk), skew_e_rad) for kk in k]).reshape((-1,) + (1,) * (f.ndim - 1))
    return np.real(np.fft.ifft(spec * factors, axis=0))[:f.shape[0]]


def ripple(torque):
    t = np.asarray(torque, dtype=float)
    mean = float(np.mean(t))
    return (float(np.max(t) - np.min(t)) / abs(mean)) if abs(mean) > 1e-9 else float("inf")


def torque_harmonics(torque_half, orders=(6, 12, 18, 24)):
    """Amplitudes of electrical harmonics of the torque from a sweep over half a period (180 el. deg)."""
    t = np.asarray(torque_half, dtype=float)
    c = np.fft.rfft(t) * 2.0 / len(t)
    out = {}
    for order in orders:                      # over 180 el. deg the harmonic index is order / 2
        idx = order // 2
        out[order] = float(abs(c[idx])) if idx < len(c) else 0.0
    return out


# ----------------------------------------------------------------------------- switched reluctance

class SRMPhaseMap:
    """Flux per turn Phi(theta, NI) and torque T(theta, NI) of one phase alone, over a rotor pole pitch
    (theta from the aligned position, mechanical radians), from samples over half a pitch (aligned to
    unaligned), mirrored: Phi(-theta) = Phi(theta), T(-theta) = -T(theta)."""

    def __init__(self, theta_half, ampere_turns, flux, torque, rotor_poles):
        self.pitch = 2 * math.pi / rotor_poles
        th = np.asarray(theta_half, dtype=float)                      # 0 (aligned) .. pitch / 2 (unaligned)
        flux, torque = np.asarray(flux, dtype=float), np.asarray(torque, dtype=float)   # (theta, NI)
        back = slice(len(th) - 2, 0, -1)                               # mirrored, without both ends
        self.theta = np.concatenate([th, self.pitch - th[back]])
        self.flux = np.concatenate([flux, flux[back]], axis=0)
        self.torque = np.concatenate([torque, -torque[back]], axis=0)
        ni = np.asarray(ampere_turns, dtype=float)
        if ni[0] > 0:                          # zero current: no flux, no torque
            ni = np.concatenate([[0.0], ni])
            self.flux = np.concatenate([np.zeros((len(self.theta), 1)), self.flux], axis=1)
            self.torque = np.concatenate([np.zeros((len(self.theta), 1)), self.torque], axis=1)
        self.ni = ni

    def _row(self, table, theta):
        x = theta % self.pitch
        th = np.concatenate([self.theta, [self.pitch]])
        tab = np.concatenate([table, table[:1]], axis=0)
        j = int(np.searchsorted(th, x, side="right") - 1)
        j = min(max(j, 0), len(th) - 2)
        w = (x - th[j]) / (th[j + 1] - th[j])
        return (1 - w) * tab[j] + w * tab[j + 1]

    def flux_at(self, theta, ni):
        return float(np.interp(ni, self.ni, self._row(self.flux, theta)))

    def torque_at(self, theta, ni):
        return float(np.interp(ni, self.ni, self._row(self.torque, theta)))

    def ni_at(self, theta, phi):
        """Ampere-turns giving the flux per turn phi at theta (the flux rises with the current)."""
        row = self._row(self.flux, theta)
        row = np.maximum.accumulate(row)
        if phi <= row[0]:
            return 0.0
        if phi >= row[-1]:                     # beyond the last level: extrapolate with the last slope
            slope = (row[-1] - row[-2]) / (self.ni[-1] - self.ni[-2])
            return float(self.ni[-1] + (phi - row[-1]) / max(slope, 1e-12))
        return float(np.interp(phi, row, self.ni))


def srm_simulate(phase_map, n_eff, resistance, vdc, speed_rpm, theta_on, theta_off, i_ref, phases,
                 steps_per_stroke=300, periods=3, hysteresis=0.05, max_steps=1500):
    """
    One phase of an SRM on an asymmetric half bridge at constant speed: +V_dc from theta_on (electrical
    position of the phase, mechanical radians from its aligned position, negative before alignment)
    until theta_off with current chopping at i_ref (hysteresis band), then -V_dc until the current
    is zero. The other phases are the same shifted by a stroke. Returns time, theta, current, flux and
    torque of phase 0 and the machine torque over one rotor pole pitch (steady state).
    """
    pitch = phase_map.pitch
    stroke = pitch / phases
    omega = 2 * math.pi * speed_rpm / 60.0
    psi_ref = n_eff * phase_map.flux_at(0.0, max(i_ref, 1e-3) * n_eff)        # aligned flux at the chopping current
    if psi_ref > 0:                                    # at most 1.5 % of it per step (low speeds need many steps)
        steps_per_stroke = int(min(max_steps, max(steps_per_stroke, math.ceil(vdc * stroke / omega / (0.015 * psi_ref)))))
    n = steps_per_stroke * phases
    dtheta = pitch / n
    dt = dtheta / omega
    psi = 0.0           # phase flux linkage (Wb) = n_eff * Phi
    on_state = True
    record = []
    total = periods * n
    for step in range(total):
        theta = -pitch / 2 + step * dtheta                  # from the unaligned position (-pitch/2)
        rel = (theta + pitch / 2) % pitch - pitch / 2        # in (-pitch/2, pitch/2]
        ni = phase_map.ni_at(rel, psi / n_eff) if psi > 0 else 0.0
        i = ni / n_eff
        conducting = theta_on <= rel < theta_off
        if conducting:
            if i > i_ref * (1 + hysteresis):
                on_state = False
            elif i < i_ref * (1 - hysteresis):
                on_state = True
            v = vdc if on_state else 0.0                    # soft chopping (zero voltage loop)
        else:
            v = -vdc if psi > 0 else 0.0
        if step >= total - n:
            record.append((step * dt, rel, i, psi, v))       # current and flux of the same instant
        psi = max(0.0, psi + (v - resistance * i) * dt)
    rec = np.array(record)
    i_phase = rec[:, 2]
    t_phase = np.array([phase_map.torque_at(r, i * n_eff) if i > 0 else 0.0 for r, i in zip(rec[:, 1], i_phase)])
    shift = n // phases
    machine = sum(np.roll(t_phase, k * shift) for k in range(phases))
    return {"time_s": rec[:, 0] - rec[0, 0], "theta": rec[:, 1], "current_A": i_phase, "flux_Wb": rec[:, 3],
            "voltage_V": rec[:, 4], "phase_torque_Nm": t_phase, "torque_Nm": machine,
            "rms_current_A": float(np.sqrt(np.mean(i_phase ** 2))), "peak_current_A": float(np.max(i_phase)),
            "mean_torque_Nm": float(np.mean(machine)), "ripple": ripple(machine)}


def srm_ideal(phase_map, ampere_turns, phases, samples=180):
    """Torque with ideal flat-top phase currents (the phase conducts wherever its torque is positive): the
    static capability at low speed. Returns (mean torque, ripple, waveform over one stroke)."""
    pitch = phase_map.pitch
    stroke = pitch / phases
    theta = np.linspace(0.0, stroke, samples, endpoint=False)
    total = np.zeros(samples)
    for k in range(phases):
        t = np.array([phase_map.torque_at(th + k * stroke, ampere_turns) for th in theta])
        total += np.maximum(t, 0.0)
    return float(np.mean(total)), ripple(total), total


def srm_best(phase_map, n_eff, resistance, vdc, speed_rpm, phases, rms_limit, peak_limit, grid=5):
    """Turn-on and turn-off angles and the chopping current that give the most mean torque with the phase
    rms current at most rms_limit and the peak at most peak_limit. Coarse grid, then the current by bisection."""
    pitch = phase_map.pitch
    best = None
    ons = np.linspace(-0.5 * pitch, -0.15 * pitch, grid)
    dwells = np.linspace(0.25 * pitch, 0.55 * pitch, grid)
    for on in ons:
        for dwell in dwells:
            off = on + dwell
            if off > 0.05 * pitch:
                continue
            lo, hi = 0.0, peak_limit
            result = srm_simulate(phase_map, n_eff, resistance, vdc, speed_rpm, on, off, hi, phases, steps_per_stroke=60,
                                  periods=2, max_steps=250)
            if result["rms_current_A"] > rms_limit:
                for _ in range(7):
                    mid = (lo + hi) / 2
                    r = srm_simulate(phase_map, n_eff, resistance, vdc, speed_rpm, on, off, mid, phases,
                                     steps_per_stroke=60, periods=2, max_steps=250)
                    if r["rms_current_A"] > rms_limit:
                        hi = mid
                    else:
                        lo, result = mid, r
                i_ref = lo
            else:
                i_ref = hi
            if best is None or result["mean_torque_Nm"] > best[0]:
                best = (result["mean_torque_Nm"], on, off, i_ref)
    _, on, off, i_ref = best
    final = srm_simulate(phase_map, n_eff, resistance, vdc, speed_rpm, on, off, i_ref, phases)
    final.update({"theta_on": on, "theta_off": off, "i_ref": i_ref})
    return final
