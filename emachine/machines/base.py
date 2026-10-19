"""
Shared parts of machine plugins: a radial or axial machine described by its main dimensions, with
estimates of the winding, the thermal network and the feasibility that are good enough to rank
designs and check a specification. A machine is a flux path and a torque principle (subclasses in
machines/<flux_path>/<principle>.py); its rotor layouts (machines/<flux_path>/rotors/<layout>.py)
add their variables, checks and geometry. Names: docs/naming.md.
"""

import math

from emachine.core.interfaces import Machine
from emachine.core.types import AMBIENT, Check, ExcitationPlan, ThermalNetwork, Variable, Winding
from emachine.spec import SpecError, copper_fill
from emachine.spec.loader import number
from emachine.spec.names import standard_values

from . import winding_layout


class NotSolvableYet(NotImplementedError):
    """The machine is known (variables, checks) but its geometry is not built yet."""


def apply_fixed(spec, variables):
    """Bounds of the spec section `variables` (number = fixed, [min, max] = range) applied to a list of Variable."""
    out, known = [], {v.name for v in variables}
    for name in spec["variables"]:
        if name not in known:
            raise SpecError(f"'variables.{name}' is not a design variable of this machine. Available: {sorted(known)}.")
    for v in variables:
        value = spec["variables"].get(v.name)
        if value is None:
            out.append(v)
            continue
        low, high = (value, value) if not isinstance(value, (list, tuple)) else value
        if v.kind == "int":
            low, high = int(math.ceil(low)), int(math.floor(high))
        out.append(Variable(v.name, low, high, v.kind, v.unit))
    return out


class RotorLayout:
    """
    One rotor layout of a machine (spec key machine.rotor): its variables, checks and geometry.
    A layout without a geometry yet raises NotSolvableYet with the ticket that builds it.
    """

    name = ""
    ticket = ""
    solvable = False

    def options(self):
        """Defaults of the layout's own options in the spec section `machine`."""
        return {}

    def validate(self, spec):
        pass

    def variables(self, spec):
        return []

    def checks(self, spec, values, d):
        return []

    def geometry(self, machine, spec, values, fidelity=None):
        raise NotSolvableYet(f"The {machine.key()} machine with the rotor layout {self.name!r} has no geometry yet: "
                             f"its variables and checks work, solving it is ticket {self.ticket}.")


class SlottedMachine(Machine):
    """
    A slotted stator with a three-phase (or m-phase) winding in `slots` slots, and a rotor of
    `pole_pairs` pole pairs. The common variables are those of the stator; the principle and the
    rotor layout add theirs. Dimensions in mm. Radial flux: stator inside the outer diameter, rotor
    in the bore. Axial flux: the same quantities on the mean radius of the active annulus.
    """

    #: the rotor layouts (RotorLayout classes); the first is the default
    ROTORS = ()
    #: options of every slotted machine in the spec section `machine`
    COMMON = {"stator": "slotted", "slots": 12}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.rotors = tuple(layout.name for layout in cls.ROTORS)
        cls.solvable = any(layout.solvable for layout in cls.ROTORS)
        open_tickets = [layout.ticket for layout in cls.ROTORS if not layout.solvable]
        cls.ticket = open_tickets[0] if open_tickets else (cls.ROTORS[0].ticket if cls.ROTORS else "")

    @classmethod
    def rotor_status(cls, rotor):
        layout = {layout.name: layout for layout in cls.ROTORS}[rotor]
        return layout.solvable, layout.ticket

    def rotor_layout(self, spec):
        """The RotorLayout of the spec (machine.rotor)."""
        name = spec["machine"].get("rotor") or self.rotors[0]
        return {layout.name: layout for layout in self.ROTORS}[name]()

    def options(self):
        out = dict(self.COMMON, **self.extra_options())
        for layout in self.ROTORS:
            out.update(layout().options())
        return out

    def extra_options(self):
        """Options of the principle."""
        return {}

    def validate(self, spec):
        m = spec["machine"]
        if m["stator"] != "slotted":
            raise SpecError(f"'machine.stator' of a {self.key()} machine must be 'slotted', got {m['stator']!r}.")
        number(spec, "machine.slots", low=3, integer=True)
        w = spec["winding"]
        if w["layers"] == 1 and m["slots"] % 2:
            raise SpecError(f"A single-layer winding needs an even number of slots, not {m['slots']}.")
        if w["pitch_slots"] is not None and w["pitch_slots"] >= m["slots"]:
            raise SpecError(f"'winding.pitch_slots' ({w['pitch_slots']}) must be below the slots ({m['slots']}).")
        if m["slots"] % m["phases"]:
            raise SpecError(f"'machine.slots' ({m['slots']}) must be a multiple of the phases ({m['phases']}).")
        self.rotor_layout(spec).validate(spec)

    def common_variables(self, spec):
        """The stator in lengths (docs/parameters.md): slot height and width, yoke height."""
        lim, m = spec["limits"], spec["machine"]
        lo, hi = lim["iron_thickness_mm"]
        room = (m["outer_diameter_mm"] - m["bore_diameter_mm"]) / 2
        slot_lo = lim["min_slot_width_mm"]
        return [
            Variable("pole_pairs", lim["pole_pairs"][0], lim["pole_pairs"][1], "int"),
            Variable("slot_height_mm", lim["min_coil_height_mm"], max(lim["min_coil_height_mm"], 0.5 * room), unit="mm"),
            Variable("slot_width_mm", slot_lo, max(slot_lo, math.pi * m["outer_diameter_mm"] / (2 * m["slots"])), unit="mm"),
            Variable("yoke_height_mm", lo, hi, unit="mm"),
            Variable("current_density_A_mm2", 1.0, max(1.0, lim["max_current_density_A_mm2"])),
        ]

    def principle_variables(self, spec):
        return []

    def variables(self, spec):
        return apply_fixed(spec, self.common_variables(spec) + self.principle_variables(spec)
                           + self.rotor_layout(spec).variables(spec))

    # ---- dimensions

    def derive(self, spec, values):
        """Dimensions of a radial machine: from the outer diameter inwards yoke, slot, air gap, rotor.
        Parallel-sided slots, open at the bore, as the mesher (rfm/section.py) and the CAD draw them."""
        values = standard_values(spec, values)
        m, op = spec["machine"], spec["operating_point"]
        p = int(values["pole_pairs"])
        slots = int(m["slots"])
        r_out = m["outer_diameter_mm"] / 2
        height, slot_width, yoke = values["slot_height_mm"], values["slot_width_mm"], values["yoke_height_mm"]
        r_bore = r_out - yoke - height
        slot_pitch = 2 * math.pi * r_bore / slots
        tooth = slot_pitch - slot_width                       # at the bore, the narrowest place of the tooth
        slot_area = slot_section_area(r_bore, r_bore + height, slot_width)
        return self._winding_dimensions(spec, values, {
            "pole_pairs": p, "slots": slots, "outer_radius": r_out, "bore_radius": r_bore,
            "rotor_radius": r_bore - m["air_gap_mm"], "slot_depth": height, "tooth_width": tooth,
            "slot_pitch": slot_pitch, "slot_width": slot_width, "slot_area_mm2": slot_area, "yoke_height": yoke,
            "back_radius": r_bore + height + yoke, "stack_length": m["stack_length_mm"],
            "coil_height": height, "electrical_frequency_Hz": op["speed_rpm"] / 60.0 * self.electrical_pole_pairs(spec, values)})

    def _winding_dimensions(self, spec, values, d):
        """Coils of the slots in d (slots, slot_area_mm2, slot_pitch, slot_width, slot_depth,
        stack_length, bore_radius): their number, area, turn length and ampere-turns."""
        w = spec["winding"]
        layers = int(w["layers"])
        coils_per_phase = d["slots"] * layers // (2 * int(spec["machine"]["phases"]))  # double layer: a coil per slot
        coil_area = d["slot_area_mm2"] if layers == 1 else d["slot_area_mm2"] / 2   # a side fills the slot, or half
        if w["pitch_slots"] is not None:
            span = w["pitch_slots"] * d["slot_pitch"]
        else:
            span = d["slot_pitch"] if w["span"] == "concentrated" else math.pi * d["bore_radius"] / d["pole_pairs"]
        turn_length = 2 * d["stack_length"] + 2 * (span + 0.5 * d["slot_depth"])  # straight parts and end windings
        ni_rms = values["current_density_A_mm2"] * coil_area * copper_fill(spec)
        return dict(d, coil_area_mm2=coil_area, coils_per_phase=coils_per_phase, turn_length_mm=turn_length,
                    coil_width=d["slot_width"] / layers, ampere_turns_rms=ni_rms, ampere_turns_peak=ni_rms * math.sqrt(2))

    def electrical_pole_pairs(self, spec, values):
        """Electrical cycles per mechanical revolution (pole pairs; rotor poles for an SRM)."""
        return int(values["pole_pairs"])

    def checks(self, spec, values):
        values = standard_values(spec, values)
        d = self.derive(spec, values)
        return self.stator_checks(spec, d) + self.slot_class_checks(spec, d) + self.principle_checks(spec, values, d) \
            + self.rotor_layout(spec).checks(spec, values, d)

    def stator_checks(self, spec, d):
        """The tooth at its narrowest place, the slot, the rotor around the shaft."""
        lim, m = spec["limits"], spec["machine"]
        lo = lim["iron_thickness_mm"][0]
        return [Check.at_least("tooth_width", d["tooth_width"], lo),
                Check.at_least("slot_width", d["slot_width"], lim["min_slot_width_mm"]),
                Check.at_least("rotor_radius", d["rotor_radius"], m["bore_diameter_mm"] / 2 + lo, d["outer_radius"])]

    def slot_class_checks(self, spec, d):
        """winding.slot_class: q = slots / (2 p phases) whole (integral) or not (fractional)."""
        wanted = spec["winding"]["slot_class"]
        if wanted == "any":
            return []
        q = winding_layout.slots_per_pole_phase(d["slots"], d["pole_pairs"], spec["machine"]["phases"])
        ok = (q.denominator == 1) == (wanted == "integral")
        return [Check.at_least("slot_class", 1.0 if ok else 0.0, 1.0)]

    def winding_layout(self, spec, values):
        """The coils of the design (winding_layout.Layout); ValueError when the winding is not balanced."""
        m, w = spec["machine"], spec["winding"]
        d = self.derive(spec, values)
        return winding_layout.layout(int(m["slots"]), int(d["pole_pairs"]), int(m["phases"]), w["span"],
                                     int(w["layers"]), w["pitch_slots"])

    def winding_description(self, spec, values):
        """Label (FSCW, FSDW, ISDW), q, layers and winding factors of the design (docs/naming.md)."""
        m, w = spec["machine"], spec["winding"]
        d = self.derive(spec, values)
        try:
            coils = self.winding_layout(spec, values)
        except ValueError:
            coils = None
        return winding_layout.describe(w["span"], coils, d["slots"], d["pole_pairs"], m["phases"], w["layers"])

    def principle_checks(self, spec, values, d):
        return []

    def winding(self, spec, values):
        d = self.derive(spec, values)
        w = spec["winding"]
        return Winding(phases=spec["machine"]["phases"], turns=w["turns"], coil_area_mm2=d["coil_area_mm2"],
                       mean_turn_length_mm=d["turn_length_mm"], fill_factor=copper_fill(spec),
                       coils_per_phase=d["coils_per_phase"], conductor=w["conductor"],
                       coil_height_mm=d["coil_height"], coil_width_mm=d["coil_width"], wire=w.get("wire"))

    def thermal_network(self, spec, values):
        """Winding to stator core through the slot insulation; core to ambient over the outer
        surface; rotor to core across the air gap; rotor to ambient over its end faces."""
        d, th = self.derive(spec, values), spec["thermal"]
        mm2 = 1e-6
        slot_wall = d["slots"] * (2 * d["slot_depth"] + d["slot_width"]) * d["stack_length"] * mm2
        g_winding_core = slot_wall * th["insulation_conductivity_W_mK"] / (th["insulation_thickness_mm"] * 1e-3)
        g_core_ambient = th["h_external_W_m2K"] * 2 * math.pi * d["outer_radius"] * d["stack_length"] * mm2
        g_core_rotor = th["h_air_gap_W_m2K"] * 2 * math.pi * d["rotor_radius"] * d["stack_length"] * mm2
        g_rotor_ambient = th["h_external_W_m2K"] * 2 * math.pi * d["rotor_radius"] ** 2 * mm2
        return ThermalNetwork(conductances=(("winding", "core", g_winding_core), ("core", AMBIENT, g_core_ambient),
                                            ("core", "rotor", g_core_rotor), ("rotor", AMBIENT, g_rotor_ambient)),
                              ambient_C=spec["operating_point"]["ambient_C"])

    def excitation(self, spec, values):
        return ExcitationPlan(mode="all_phases", phases=spec["machine"]["phases"],
                              electrical_period_deg=360.0 / self.electrical_pole_pairs(spec, values),
                              positions=int(spec["fidelity"]["positions"]))

    def geometry(self, spec, values, fidelity=None):
        return self.rotor_layout(spec).geometry(self, spec, standard_values(spec, values), fidelity)


def slot_section_area(r0, r1, width):
    """Area of a parallel-sided slot of the given width between the circles r0 (bore) and r1."""
    if r1 <= 0:
        return 0.0
    half = min(width / 2, r0 if r0 > 0 else r1)

    def under(r):                     # area under sqrt(r^2 - y^2) for |y| <= half
        return half * math.sqrt(r * r - half * half) + r * r * math.asin(half / r)
    return under(r1) - under(r0) if r0 > 0 else under(r1)


def pole_arc_variables(spec):
    """Rotor pole arc beta_r (mechanical degrees) and rotor pole height."""
    pitch = 360.0 / spec["machine"]["rotor_poles"]
    return [Variable("rotor_pole_arc_deg", 0.3 * pitch, 0.5 * pitch, unit="deg"),
            Variable("rotor_pole_height_mm", 1.0, max(1.0, 0.15 * spec["machine"]["outer_diameter_mm"]), unit="mm")]


def lawrenson_checks(spec, beta_s, beta_r):
    """Feasible pole arcs of an SRM (Lawrenson 1980): self-starting in either direction needs both
    arcs at least one stroke, 360 / (phases x rotor poles); the stator and the rotor pole must fit
    in one rotor pole pitch."""
    m = spec["machine"]
    stroke = 360.0 / (m["phases"] * m["rotor_poles"])
    pitch = 360.0 / m["rotor_poles"]
    return [Check.at_least("stator_pole_arc", beta_s, stroke, pitch), Check.at_least("rotor_pole_arc", beta_r, stroke, pitch),
            Check.at_most("pole_arcs", beta_s + beta_r, pitch, pitch)]


def stator_pole_arc_deg(slots, slot_width, radius):
    """Arc (degrees) of the stator pole, the tooth, at the given radius: the slot pitch less the
    angle of the parallel-sided slot there."""
    half = min(1.0, slot_width / (2 * radius)) if radius > 0 else 1.0
    return 360.0 / slots - 2 * math.degrees(math.asin(half))


class SwitchedReluctance:
    """The switched reluctance principle on a slotted machine of any flux path (mix in before the
    flux path class): salient stator and rotor poles, concentrated coils, no magnets, phases
    switched one after the other. The pole count is an option (rotor_poles), not a variable."""

    principle = "srm"
    winding_spans = ("concentrated",)       # coils around the salient stator poles

    def extra_options(self):
        return dict(super().extra_options(), rotor_poles=8)

    def validate(self, spec):
        super().validate(spec)
        number(spec, "machine.rotor_poles", low=2, integer=True)

    def common_variables(self, spec):
        return [v for v in super().common_variables(spec) if v.name != "pole_pairs"]

    def derive(self, spec, values):
        return super().derive(spec, dict(values, pole_pairs=spec["machine"]["rotor_poles"] // 2))

    def electrical_pole_pairs(self, spec, values):
        return spec["machine"]["rotor_poles"]          # one stroke per rotor pole and phase


def analysis_settings(spec, ampere_turns_peak):
    """The material and drive settings of the field solvers from the specification."""
    mat = spec["materials"]
    return {"magnet_remanence_T": mat["magnet"]["remanence_T"], "magnet_mu_r": mat["magnet"]["mu_r"],
            "stator_core_mu_r": mat["stator_core"]["mu_r"], "rotor_iron_mu_r": mat["rotor_iron"]["mu_r"],
            "rotor_housing_mu_r": mat["rotor_housing"]["mu_r"],
            "stator_core_saturation_T": mat["stator_core"]["saturation_T"],
            "stator_core_bh_curve": mat["stator_core"]["bh_curve"],
            "rotor_iron_saturation_T": mat["rotor_iron"]["saturation_T"],
            "rotor_iron_bh_curve": mat["rotor_iron"]["bh_curve"],
            "coil_turns": 1, "coil_current_A": ampere_turns_peak}
