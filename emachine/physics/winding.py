"""
Winding and electrical model from explicit quantities.

The field solution is in ampere-turns. At fixed ampere-turns every voltage term scales linearly
with the number of turns N, and the current scales with 1/N. The number of turns is therefore
chosen after the field solution, to satisfy the current cut-off and the bus voltage together.

Angles: samples k = 0..n-1 at electrical angle pi * k / n (half a period). Flux reverses over
the other half period under sinusoidal drive.
"""

import math

import numpy as np


def electrical_angles(n, shift=0.0):
    """Sample angles over half a period. `shift` moves all samples by a fraction of a step."""
    return np.pi * (np.arange(n) + shift) / n


def current_shape(n, shift=0.0):
    """Current waveform for unit peak: i = -sin(angle), in phase with the induced voltage."""
    return -np.sin(electrical_angles(n, shift))


def copper_resistivity(copper, temp_C):
    """Resistivity in ohm m of copper (material dict with resistivity_20C_ohm_m, temp_coefficient_per_K)."""
    return copper["resistivity_20C_ohm_m"] * (1.0 + copper["temp_coefficient_per_K"] * (temp_C - 20.0))


def one_turn_resistance(copper, copper_area_mm2, turn_length_mm, temp_C):
    """Resistance in ohm of a single turn that uses the whole copper area of the coil."""
    return copper_resistivity(copper, temp_C) * turn_length_mm * 1e-3 / (copper_area_mm2 * 1e-6)


def resistance(one_turn_ohm, turns):
    """Resistance of the coil wound with `turns` turns."""
    return one_turn_ohm * turns ** 2


def copper_loss(one_turn_ohm, ampere_turns_rms):
    """Copper loss in W at given rms ampere-turns. It does not depend on the number of turns."""
    return one_turn_ohm * ampere_turns_rms ** 2


def flux_slope(flux_half):
    """d(flux)/d(electrical angle) at the sample points, by spectral differentiation over a full period."""
    f = np.asarray(flux_half, dtype=float)
    full = np.concatenate([f, -f])                      # the flux reverses over the second half period
    n = len(full)
    k = np.fft.fftfreq(n, d=1.0 / n)                    # integer harmonic numbers
    spectrum = np.fft.fft(full) * (1j * k)
    if n % 2 == 0:
        spectrum[n // 2] = 0.0                          # the Nyquist term has no defined derivative
    return np.real(np.fft.ifft(spectrum))[:len(f)]


def volts_per_turn(one_turn_ohm, electrical_frequency_Hz, flux_per_turn_half, ampere_turns_peak):
    """Terminal voltage waveform divided by the number of turns, over half an electrical period."""
    n = len(flux_per_turn_half)
    induced = 2 * math.pi * electrical_frequency_Hz * flux_slope(flux_per_turn_half)
    return one_turn_ohm * ampere_turns_peak * current_shape(n) + induced


def phase_factor(phases):
    """Line voltage over phase voltage of the drive: 1 for a single phase (full bridge), sqrt 3 for star."""
    return 1.0 if phases == 1 else math.sqrt(3)


def usable_phase_voltage(phases, bus_voltage):
    """Peak phase voltage a drive can apply."""
    return bus_voltage / phase_factor(phases)


def choose_turns(volts_per_turn_peak, ampere_turns_peak, bus_voltage_V, max_current_A, phases,
                 one_turn_resistance_ohm, copper_area_mm2, fixed_turns=None, layer_cap=None):
    """
    Number of turns and the resulting electrical quantities.

    turns_min is the fewest turns the current cut-off allows, turns_max the most that the bus
    voltage (and, for a strip coil, the layer cap) allow. `fixed_turns` fixes the number; otherwise
    it is turns_max. `violation` is positive when the turns break a limit: the relative excess of
    the bus voltage, the current or the layer count, whichever is largest.
    """
    v1 = volts_per_turn_peak
    bus_min, bus_max = bus_voltage_V
    pf = phase_factor(phases)
    turns_min = max(1, int(math.ceil(ampere_turns_peak / max_current_A - 1e-9)))
    turns_by_voltage = int(math.floor(usable_phase_voltage(phases, bus_max) / v1 + 1e-9)) if v1 > 0 else 10 ** 6
    turns_max = min(turns_by_voltage, layer_cap) if layer_cap else turns_by_voltage
    if fixed_turns is None:
        feasible = turns_max >= turns_min
        turns = turns_max if feasible else turns_min
    else:
        turns = int(fixed_turns)
    required_bus = turns * v1 * pf
    if fixed_turns is None and not layer_cap:
        violation = max(0.0, turns_min * v1 * pf / bus_max - 1.0)
    else:
        violation = max(0.0, required_bus / bus_max - 1.0, turns_min / turns - 1.0,
                        (turns / layer_cap - 1.0) if layer_cap else 0.0)
        feasible = violation == 0.0
    peak_current = ampere_turns_peak / turns
    wire_area = copper_area_mm2 / turns
    gauge = wire_gauge(wire_area)
    return {
        "awg": gauge["awg"], "wire_diameter_mm": gauge["diameter_mm"], "awg_fill_share": gauge["area_mm2"] / wire_area,
        "turns": turns,
        "turns_min": turns_min,
        "turns_max": turns_max,
        "feasible": feasible,
        "violation": violation,
        "peak_current_A": peak_current,
        "rms_current_A": peak_current / math.sqrt(2),
        "volts_per_turn_peak": v1,
        "required_bus_voltage_V": required_bus,
        "below_minimum_bus": required_bus < bus_min,
        "resistance_ohm": resistance(one_turn_resistance_ohm, turns),
        "wire_area_mm2": wire_area,
        "current_density_rms_A_mm2": peak_current / math.sqrt(2) / wire_area,
    }


def awg_diameter_mm(awg):
    """Bare copper diameter of an American Wire Gauge number (AWG 36 = 0.127 mm, 39 steps per 92 x)."""
    return 0.127 * 92.0 ** ((36 - awg) / 39.0)


def wire_gauge(copper_area_mm2):
    """The thickest AWG wire (whole gauge numbers 0 to 40) whose copper fits the copper area of one turn,
    so that the turns keep the fill factor of the specification. Returns {awg, diameter_mm, area_mm2};
    the share of the area used is area_mm2 / copper_area_mm2 (at most 1). None below AWG 40."""
    for awg in range(0, 41):
        diameter = awg_diameter_mm(awg)
        area = math.pi * diameter ** 2 / 4
        if area <= copper_area_mm2:
            return {"awg": awg, "diameter_mm": diameter, "area_mm2": area}
    return {"awg": None, "diameter_mm": None, "area_mm2": 0.0}


#: fewest turns, as a share of the most the bus allows, that fit_awg tries
AWG_TURN_RANGE = 0.85


def fit_awg(out, v1, ampere_turns_peak, limits, winding, r1, copper_area_mm2):
    """Turns and wire gauge together (winding.wire = "awg", T57): among the turns from the most the
    bus voltage allows down to 85 % of them (not below the current's minimum), the number whose
    thickest fitting AWG wire fills the copper area best."""
    best, best_fill = out["turns"], -1.0
    low = max(out["turns_min"], int(math.floor(AWG_TURN_RANGE * out["turns"])))
    for turns in range(out["turns"], low - 1, -1):
        filled = turns * wire_gauge(copper_area_mm2 / turns)["area_mm2"]
        if filled > best_fill + 1e-12:
            best, best_fill = turns, filled
    if best == out["turns"]:
        return out
    return choose_turns(v1, ampere_turns_peak, limits["bus_voltage_V"], limits["max_current_A"], winding.phases,
                        r1, copper_area_mm2, fixed_turns=best)


def winding_resistance(copper, winding, temp_C):
    """
    Resistance of one phase per turn squared (core.types.Winding): the coils of the phase in series,
    each with all turns in its coil area. Multiply by turns^2 for the phase resistance.
    """
    one = one_turn_resistance(copper, winding.coil_area_mm2 * winding.fill_factor, winding.mean_turn_length_mm, temp_C)
    return one * winding.coils_per_phase if winding.coils_per_phase != 1 else one


def turns_for(winding, copper, limits, flux_per_turn_half, electrical_frequency_Hz, ampere_turns_peak, temp_C,
              strip_min_thickness_mm=None):
    """
    choose_turns for a Winding: the voltage per turn from the flux, the copper of the winding, the
    bus voltage and current limits (spec section `limits`), and for a strip coil the layer cap.
    """
    r1 = winding_resistance(copper, winding, temp_C)
    v1 = float(np.max(np.abs(volts_per_turn(r1, electrical_frequency_Hz, flux_per_turn_half, ampere_turns_peak))))
    fill = winding.fill_factor
    strip = winding.conductor == "strip"
    # Layers are stacked across the coil height: the copper height h * fill holds this many strips.
    layer_cap = max(1, int(np.floor(winding.coil_height_mm * fill / strip_min_thickness_mm + 1e-9))) if strip else None
    out = choose_turns(v1, ampere_turns_peak, limits["bus_voltage_V"], limits["max_current_A"], winding.phases,
                       r1, winding.coil_area_mm2 * fill, fixed_turns=winding.turns, layer_cap=layer_cap)
    if winding.wire == "awg" and not strip and winding.turns is None and out["feasible"]:
        out = fit_awg(out, v1, ampere_turns_peak, limits, winding, r1, winding.coil_area_mm2 * fill)
    out["conductor"] = winding.conductor
    if strip:
        out.update({"layer_cap": layer_cap, "strip_width_mm": winding.coil_width_mm,
                    "strip_thickness_mm": winding.coil_height_mm * fill / out["turns"]})
    return out
