"""Common parts of the topologies of the catalogue: variables, checks, winding helpers."""

import math

from emachine.core.types import Variable

from .. import winding_layout

#: Fractional-slot concentrated windings offered (slots, poles): k_w1 >= 0.9, balanced, symmetric
#: (gcd(Q, 2p) >= 2, no unbalanced magnetic pull), q from 1/4 to 1/2 (docs/design_principles.md).
FSCW = [(12, 10), (12, 14), (18, 16), (18, 20), (24, 20), (24, 22), (24, 26), (24, 28), (27, 24), (27, 30),
        (30, 26), (30, 28), (30, 32), (30, 34), (36, 30), (36, 32), (36, 34), (36, 38), (36, 40), (36, 42)]
#: Integer-slot windings with one slot per pole and phase (q = 1, the least distributed integer winding)
ISW_Q1 = [(12, 4), (18, 6), (24, 8), (30, 10), (36, 12)]


class GeometryError(ValueError):
    """The design cannot be drawn; `checks` lists the violated limits as (name, violation)."""

    def __init__(self, checks):
        super().__init__("; ".join(f"{n} ({v:.3g})" for n, v in checks))
        self.checks = checks

    @property
    def violation(self):
        return sum(v for _, v in self.checks)


class Checks:
    """Collects geometric limits; `raise_if_any` raises GeometryError with the relative violations."""

    def __init__(self):
        self.items = []

    def at_least(self, name, value, limit, scale=None):
        if value < limit:
            self.items.append((name, (limit - value) / (scale or max(abs(limit), 1.0))))

    def at_most(self, name, value, limit, scale=None):
        if value > limit:
            self.items.append((name, (value - limit) / (scale or max(abs(limit), 1.0))))

    def raise_if_any(self):
        if self.items:
            raise GeometryError(self.items)


def var(name, low, high, kind="real", unit=""):
    return Variable(name, low, high, kind, unit)


def fscw_sides(slots, pole_pairs, layers=2, span="concentrated"):
    """Coil sides of the slot-star winding (winding_layout) and its description."""
    layout = winding_layout.layout(slots, pole_pairs, 3, span, layers)
    desc = winding_layout.describe(span, layout, slots, pole_pairs, 3, layers)
    return [list(s) for s in layout.sides()], layout, desc


def phase_sequence(layout):
    """Phase sequence of the current that turns the field with the rotor (+1 or -1), from the EMF phasors of
    the winding: +1 when the phasor of phase 1 is 120 el. degrees ahead of phase 0 (checked against the
    sequence measured from the magnet flux of the PM machines of the study)."""
    a0 = winding_layout.phase_axis_deg(layout, 0)
    a1 = winding_layout.phase_axis_deg(layout, 1)
    d = (a1 - a0) % 360.0
    return 1 if abs(d - 120.0) < 1.0 else -1


def srm_sides(stator_poles, phases=3):
    """Concentrated coils around every stator pole; pole k belongs to phase k mod m, the poles of a phase
    alternate in polarity (short flux paths). Pole k lies between slot k and slot k + 1."""
    sides = []
    per_phase = {}
    for k in range(stator_poles):
        phase = k % phases
        n = per_phase.get(phase, 0)
        per_phase[phase] = n + 1
        sign = 1 if n % 2 == 0 else -1
        sides.append([k, 1, phase, sign, 1.0])
        sides.append([(k + 1) % stator_poles, 0, phase, -sign, 1.0])
    return sides


def gauss_slices(r0, r1, n=3):
    """Slice radii and depths: n Gauss-Legendre points and weights over r0..r1."""
    import numpy as np
    pts, wts = np.polynomial.legendre.leggauss(int(n))
    mid, half = (r0 + r1) / 2, (r1 - r0) / 2
    return [{"radius": mid + half * p, "depth": half * w} for p, w in zip(pts, wts)]


def cogging_period_el_rad(slots, poles_rotor, pe):
    """Electrical radians of one cogging period: 2 pi / LCM(Q, 2p) mechanical, times pe."""
    return 2 * math.pi / math.lcm(int(slots), int(poles_rotor)) * pe


class Topology:
    """One machine of the catalogue. Subclasses set the class attributes and implement
    `variables(env)` and `design(env, values)`."""

    key = ""
    title = ""
    flux_path = ""         # "rfm", "afm" or "rafm" (docs/naming.md)
    principle = ""         # "pm", "synrm", "pmasynrm", "srm", "vernier"
    summary = ""
    sources = ""           # literature that set the variable ranges

    def variables(self, env):
        raise NotImplementedError

    def design(self, env, values):
        raise NotImplementedError

    # ---- helpers

    @staticmethod
    def mesh(env, gap):
        level = env.get("fidelity", {})
        return {"gap_cell": level.get("gap_cell_factor", 0.5) * gap, "size_max": level.get("size_max_mm", 2.5),
                "reach": level.get("reach_mm", 6.0)}

    @staticmethod
    def base_design(**kw):
        d = {"sequence_hint": 1, "skew_e_rad": 0.0, "skew_factor": 1.0}
        d.update(kw)
        return d
