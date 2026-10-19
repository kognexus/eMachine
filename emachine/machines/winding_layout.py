"""
Windings of slotted machines from the star of slots: which coil belongs to which phase, with which
sign; winding factors; slots per pole and phase q and the label of the winding (docs/naming.md).

Coil k has its "in" side in slot k and its "out" side y slots further (y = pitch): y = 1 for a
concentrated (tooth-coil) winding, y = full pitch (slots / 2p, rounded) for a distributed winding
unless a pitch is given (short pitching). The phasor of coil k points at p * k * 360 / Q electrical
degrees (k slot pitches along the bore). Phasors fall into 60-degree belts A+, C-, B+, A-, C+, B-
(three phases), or into 360/(2m) belts in general; a coil in a negative belt is connected with the
opposite sign.

Double layer: a coil starts in every slot, so every slot holds two coil sides (one in each half).
Single layer: half of these coils, chosen so that every slot holds one coil side; that side fills
the slot, and is described as both halves of the slot, each with half of the coil (`share` 0.5).
"""

import cmath
import math
from dataclasses import dataclass
from fractions import Fraction

SPANS = ("concentrated", "distributed")
#: spans without coil sides in two slots: one ring coil per phase (TFM), one coil around the yoke per slot (RAFM)
SINGLE_SIDED = ("ring", "toroidal")


@dataclass(frozen=True)
class Coil:
    slot_in: int          # slot of the side carrying +current (its counter-clockwise half)
    slot_out: int         # slot of the side carrying -current (its clockwise half)
    phase: int
    sign: int             # +1 or -1: direction of connection
    angle_deg: float      # electrical angle of the coil phasor


@dataclass(frozen=True)
class Layout:
    slots: int
    pole_pairs: int
    phases: int
    pitch: int            # coil span in slots
    coils: tuple
    layers: int = 2

    def sides(self):
        """
        Every coil side: (slot, half, phase, sign) for a double layer, (slot, half, phase, sign, share)
        for a single layer; half 0 is the clockwise, half 1 the counter-clockwise half of a slot. A coil
        goes in on the counter-clockwise half of its first slot and comes back on the clockwise half of
        its last one, so a tooth coil (pitch 1) lies around the tooth between them. A single-layer side
        fills its slot: both halves, each carrying half of the coil (share 0.5).
        """
        out = []
        for c in self.coils:
            if self.layers == 2:
                out.append((c.slot_in, 1, c.phase, c.sign))
                out.append((c.slot_out % self.slots, 0, c.phase, -c.sign))
            else:
                for half in (0, 1):
                    out.append((c.slot_in, half, c.phase, c.sign, 0.5))
                    out.append((c.slot_out % self.slots, half, c.phase, -c.sign, 0.5))
        return sorted(out)


def full_pitch(slots, pole_pairs):
    """Coil span of a full-pitch distributed coil, in slots (one pole pitch, rounded)."""
    return max(1, round(slots / (2 * pole_pairs)))


def slots_per_pole_phase(slots, pole_pairs, phases):
    """q = Q / (2 p m) as a fraction."""
    return Fraction(int(slots), 2 * int(pole_pairs) * int(phases))


def label(span, slots, pole_pairs, phases):
    """FSCW, FSDW, ISDW or ISCW from the span and q; "ring" or "toroidal" for those windings."""
    if span in SINGLE_SIDED:
        return span
    q = slots_per_pole_phase(slots, pole_pairs, phases)
    return ("IS" if q.denominator == 1 else "FS") + ("CW" if span == "concentrated" else "DW")


def layout(slots, pole_pairs, phases=3, span="concentrated", layers=2, pitch=None):
    """
    The winding of `slots` slots for `pole_pairs` pole pairs: span "concentrated" or "distributed",
    1 or 2 layers, coil pitch in slots (None: 1 for concentrated, full pitch for distributed).
    ValueError when the combination gives no balanced winding.
    """
    if span not in SPANS:
        raise ValueError(f"Unknown winding span {span!r}.")
    if pitch is None:
        pitch = 1 if span == "concentrated" else full_pitch(slots, pole_pairs)
    if not 1 <= pitch < slots:
        raise ValueError(f"A coil pitch of {pitch} slots does not fit {slots} slots.")
    belt = 360.0 / (2 * phases)
    coils = []
    for k in range(slots):
        angle = (pole_pairs * k * 360.0 / slots) % 360.0
        # Belt number from the phasor angle: belts alternate +phase and -phase of the phase sequence
        # A+, C-, B+, A-, C+, B- for three phases (each phase 120 degrees after the previous).
        index = int(((angle + belt / 2) % 360.0) // belt)
        phase_axis = index * belt                     # electrical angle of this belt's centre
        sign = 1 if index % 2 == 0 else -1
        lag = (phase_axis - (0.0 if sign > 0 else 180.0)) % 360.0
        # A coil further along the bore sees the rotor later: its flux lags by p times the angle. Phase k
        # is the one whose axis lies k * 360 / m electrical degrees further on, so it lags phase 0.
        phase = int(round(lag / (360.0 / phases))) % phases
        coils.append(Coil(k, k + pitch, phase, sign, angle))
    if layers == 2:
        return _balanced(Layout(slots, pole_pairs, phases, pitch, tuple(coils), 2))
    if layers != 1:
        raise ValueError(f"A winding has 1 or 2 layers, not {layers}.")
    for choice in (lambda c: c.slot_in % 2 == 0, lambda c: c.slot_in % 2 == 1,
                   lambda c: c.sign > 0, lambda c: c.sign < 0):
        chosen = tuple(c for c in coils if choice(c))
        used = sorted([c.slot_in for c in chosen] + [c.slot_out % slots for c in chosen])
        if used != list(range(slots)):
            continue
        try:
            return _balanced(Layout(slots, pole_pairs, phases, pitch, chosen, 1))
        except ValueError:
            continue
    raise ValueError(f"{slots} slots and {2 * pole_pairs} poles give no balanced single-layer {phases}-phase winding "
                     f"with a pitch of {pitch} slots.")


def _balanced(winding):
    slots, p, phases = winding.slots, winding.pole_pairs, winding.phases
    counts = [sum(1 for c in winding.coils if c.phase == m) for m in range(phases)]
    if len(set(counts)) != 1 or counts[0] == 0:
        raise ValueError(f"{slots} slots and {2 * p} poles give no balanced {phases}-phase winding.")
    axes = [phase_axis_deg(winding, m) for m in range(phases)]
    if abs(_phasor(winding, 0)) < 1e-9:
        raise ValueError(f"{slots} slots and {2 * p} poles give no balanced {phases}-phase winding (no EMF).")
    for m in range(1, phases):
        if abs(((axes[m] - axes[0]) % 360.0) - m * 360.0 / phases) > 1e-6 and \
                abs(((axes[0] - axes[m]) % 360.0) - m * 360.0 / phases) > 1e-6:
            raise ValueError(f"{slots} slots and {2 * p} poles give no balanced {phases}-phase winding.")
    return winding


def toroidal(slots, pole_pairs, phases=3):
    """
    A toroidal ("annular", Gramme-ring) winding: one coil around the stator yoke in every slot. A coil
    has its active side(s) in its own slot only (the return side runs inside the yoke, away from the
    magnets), so coil k is a phasor at p * k * 360 / Q, sorted into the belts as above. Returned as a
    Layout with pitch 0 and one layer; coil.slot_in = coil.slot_out = its slot.
    """
    # the phase and sign of each slot are those of the coils of a tooth-coil winding starting there
    coils = tuple(Coil(c.slot_in, c.slot_in, c.phase, c.sign, c.angle_deg)
                  for c in layout(slots, pole_pairs, phases, "concentrated", 2, 1).coils)
    out = Layout(slots, pole_pairs, phases, 0, coils, 1)
    counts = [sum(1 for c in coils if c.phase == m) for m in range(phases)]
    if len(set(counts)) != 1 or toroidal_factor(out) < 1e-9:
        raise ValueError(f"{slots} slots and {2 * pole_pairs} poles give no balanced toroidal {phases}-phase winding.")
    return out


def toroidal_factor(winding, harmonic=1):
    """Winding factor of a toroidal winding: |sum of the coil phasors of phase 0| / coils of the phase."""
    total, n = 0j, 0
    for c in winding.coils:
        if c.phase == 0:
            total += c.sign * cmath.exp(1j * math.radians(harmonic * winding.pole_pairs * c.slot_in * 360.0 / winding.slots))
            n += 1
    return abs(total) / n


def double_layer(slots, pole_pairs, phases=3, kind="concentrated"):
    """The double-layer winding of T41 (layout with layers 2 and the default pitch)."""
    return layout(slots, pole_pairs, phases, kind, 2)


def _phasor(layout, phase, harmonic=1):
    total = 0j
    for c in layout.coils:
        if c.phase != phase:
            continue
        theta = math.radians(harmonic * layout.pole_pairs * c.slot_in * 360.0 / layout.slots)
        span = math.radians(harmonic * layout.pole_pairs * layout.pitch * 360.0 / layout.slots)
        # EMF of a coil: difference of its two sides; the pitch factor comes from their spacing.
        total += c.sign * (cmath.exp(1j * theta) - cmath.exp(1j * (theta + span)))
    return total


def winding_factor(layout, harmonic=1):
    """Fundamental (or harmonic) winding factor: |sum of coil EMF phasors| / (2 x number of coils of the phase)."""
    n = sum(1 for c in layout.coils if c.phase == 0)
    return abs(_phasor(layout, 0, harmonic)) / (2 * n)


def pitch_factor(layout, harmonic=1):
    """k_p = |sin(nu p y pi / Q)|: the EMF of one coil against that of a full-pitch coil."""
    return abs(math.sin(harmonic * layout.pole_pairs * layout.pitch * math.pi / layout.slots))


def distribution_factor(layout, harmonic=1):
    """k_d = k_w / k_p."""
    return winding_factor(layout, harmonic) / pitch_factor(layout, harmonic)


def describe(span, layout_or_none, slots, pole_pairs, phases, layers):
    """Winding description for reports: label, q, layers and the fundamental factors (None for a ring)."""
    q = slots_per_pole_phase(slots, pole_pairs, phases) if span != "ring" else None
    if span == "toroidal":
        out = {"label": "toroidal", "span": span, "layers": 1, "q": float(q), "q_text": str(q),
               "k_w1": None if layout_or_none is None else toroidal_factor(layout_or_none), "k_p1": None, "k_d1": None,
               "pitch_slots": 0}
        return out
    out = {"label": label(span, slots, pole_pairs, phases), "span": span, "layers": layers,
           "q": None if q is None else float(q), "q_text": None if q is None else str(q),
           "k_w1": None, "k_p1": None, "k_d1": None}
    if layout_or_none is not None:
        out.update(k_w1=winding_factor(layout_or_none), pitch_slots=layout_or_none.pitch)
        if layers == 2:     # a single layer has no unique split into pitch and distribution factor
            out.update(k_p1=pitch_factor(layout_or_none), k_d1=distribution_factor(layout_or_none))
    return out


def text(description):
    """One line: "FSCW, q = 2/5, 2 layers, k_w1 = 0.933"."""
    d = description
    if d["label"] == "ring":
        return "ring winding (one coil around the axis per phase)"
    if d["label"] == "toroidal":
        k = "" if d["k_w1"] is None else f", k_w1 = {d['k_w1']:.3f}"
        return f"toroidal winding (one coil around the yoke per slot), q = {d['q_text']}{k}"
    q = d["q"]
    q_text = f"{q:g}" if abs(q - round(q, 3)) < 1e-12 else d["q_text"]
    out = f"{d['label']}, q = {q_text}, {d['layers']} layer{'s' if d['layers'] != 1 else ''}"
    if d["k_w1"] is not None:
        out += f", pitch {d['pitch_slots']} slot{'s' if d['pitch_slots'] != 1 else ''}, k_w1 = {d['k_w1']:.3f}"
    return out


def phase_axis_deg(layout, phase):
    """Electrical angle of the EMF phasor of a phase."""
    return math.degrees(cmath.phase(_phasor(layout, phase))) % 360.0


def flux_axis_deg(layout, phase=0):
    """
    Mechanical angle at which a north pole centred on it gives the phase its largest positive flux.
    The axis of a coil (positive current in on the counter-clockwise side) points towards the axis of
    the machine, so a north pole links negative flux when it faces the coil centre: the angle is
    (direction of sum(sign * exp(j p theta_c)) + 180 deg) / p, theta_c the coil centre.
    """
    total = 0j
    for c in layout.coils:
        if c.phase == phase:
            centre = (c.slot_in + layout.pitch / 2) * 360.0 / layout.slots
            total += c.sign * cmath.exp(1j * math.radians(layout.pole_pairs * centre))
    return (math.degrees(cmath.phase(total)) + 180.0) / layout.pole_pairs
