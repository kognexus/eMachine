"""
Torque of the whole machine from the torque waveform of one phase, and ripple metrics.

When the phases are magnetically independent (axially stacked phases of a TFM), the machine
torque is the phase waveform plus copies shifted by the phase spacing: 360 / phases electrical
degrees, 90 for two phases. Machines solved with all phases at once give the machine torque
directly.
"""

import math

import numpy as np


def phase_spacing_deg(phases):
    return 90.0 if phases == 2 else 360.0 / phases


def machine_torque(phase_torque, phases, period="half"):
    """
    Total torque waveform, same sampling as the input. `period` says what the samples cover: "half"
    (half an electrical period; the phase torque of a sinusoidal drive repeats every half period)
    or "full".
    """
    t = np.asarray(phase_torque, dtype=float)
    if phases == 1:
        return t.copy()
    n = len(t)
    span = 180.0 if period == "half" else 360.0
    total = np.zeros_like(t)
    for k in range(phases):
        shift = k * phase_spacing_deg(phases) / span * n
        if abs(shift - round(shift)) > 1e-9:
            raise ValueError(f"{phases} phases need a number of positions per {period} period that "
                             f"places every phase on a sample, got {n}.")
        total += np.roll(t, -int(round(shift)) % n)
    return total


def metrics(waveform):
    """Mean, extremes, peak-to-peak and ripple (peak-to-peak / mean) of a torque waveform."""
    t = np.asarray(waveform, dtype=float)
    mean = float(t.mean())
    peak_to_peak = float(t.max() - t.min())
    ripple = peak_to_peak / mean if mean > 1e-12 else math.inf
    return {"mean": mean, "min": float(t.min()), "max": float(t.max()),
            "peak_to_peak": peak_to_peak, "ripple": ripple}
