"""
Radial-axial flux PMSM with a toroidal winding ("rafm/pmsm", T53): the ARF-PMSM of Zhang, Liu, Wu,
Electronics 2023, 12, 2867. An SMC ring yoke carries teeth that face an outer rotor radially and
two rotor discs axially; one toroidal coil around the yoke in every slot works on all three gaps.
Dimensions: dimensions.py; names and variables: docs/naming.md, docs/parameters.md.
"""

import cmath
import math

from emachine.core.interfaces import Machine
from emachine.core.registry import register
from emachine.core.types import AMBIENT, Check, ExcitationPlan, GeometryRequest, ThermalNetwork, Variable, Winding
from emachine.spec import SpecError, copper_fill
from emachine.spec.loader import number
from emachine.spec.names import standard_values

from .. import winding_layout
from ..base import analysis_settings, apply_fixed
from . import dimensions


@register("machine", "rafm/pmsm")
class RadialAxialFluxPMSM(Machine):
    """Toroidal winding, surface magnets on the outer rotor ring and on both rotor discs."""

    flux_path = "rafm"
    principle = "pmsm"
    rotors = ("surface",)
    winding_spans = ("toroidal",)
    solvable = True
    ticket = "T55"
    #: axial slices of the quasi-3D field model across the axial magnets (T55)
    SLICES = 3

    def options(self):
        return {"stator": "toroidal", "slots": 24}

    def validate(self, spec):
        m = spec["machine"]
        if m["stator"] != "toroidal":
            raise SpecError(f"'machine.stator' of a rafm/pmsm machine must be 'toroidal', got {m['stator']!r}.")
        if m["rotor_placement"] != "outer":
            raise SpecError("The radial-axial machine has its radial rotor outside the stator: "
                            "'machine.rotor_placement' must be 'outer'.")
        number(spec, "machine.slots", low=3, integer=True)
        if m["slots"] % m["phases"]:
            raise SpecError(f"'machine.slots' ({m['slots']}) must be a multiple of the phases ({m['phases']}).")

    def variables(self, spec):
        lim, m = spec["limits"], spec["machine"]
        lo, hi = lim["iron_thickness_mm"]
        R, L = m["outer_diameter_mm"] / 2, m["stack_length_mm"]
        slot_lo, coil_lo = lim["min_slot_width_mm"], lim["min_coil_height_mm"]
        mm = "mm"
        return apply_fixed(spec, [
            Variable("pole_pairs", lim["pole_pairs"][0], lim["pole_pairs"][1], "int"),
            Variable("rotor_iron_mm", lo, max(hi, 0.1 * R), unit=mm),
            Variable("magnet_thickness_mm", 1.0, 8.0, unit=mm),
            Variable("magnet_arc_el_deg", 108.0, 180.0, unit="el. deg"),
            Variable("radial_tooth_height_mm", 3.0, max(3.0, 0.25 * R), unit=mm),
            Variable("radial_tooth_length_mm", 5.0, max(5.0, L), unit=mm),
            Variable("yoke_width_mm", lo, max(lo, 0.3 * R), unit=mm),
            Variable("axial_tooth_height_mm", 3.0, max(3.0, 0.4 * L), unit=mm),
            Variable("disc_iron_mm", lo, max(hi, 0.15 * L), unit=mm),
            Variable("axial_magnet_thickness_mm", 1.0, 8.0, unit=mm),
            Variable("axial_magnet_arc_el_deg", 108.0, 180.0, unit="el. deg"),
            Variable("slot_width_mm", slot_lo, max(slot_lo, math.pi * m["outer_diameter_mm"] / (2 * m["slots"])), unit=mm),
            Variable("slot_opening_mm", 1.0, 10.0, unit=mm),
            Variable("tooth_tip_height_mm", 0.5, 5.0, unit=mm),
            Variable("coil_thickness_mm", coil_lo, max(coil_lo, 0.3 * R), unit=mm),
            Variable("current_density_A_mm2", 1.0, max(1.0, lim["max_current_density_A_mm2"])),
        ])

    def derive(self, spec, values):
        return dimensions.derive(spec, standard_values(spec, values))

    def checks(self, spec, values):
        values = standard_values(spec, values)
        d, lim, a = self.derive(spec, values), spec["limits"], spec["winding"]["coil_clearance_mm"]
        lo = lim["iron_thickness_mm"][0]
        out = [
            Check.at_least("radial_tooth_width", d["radial_tooth_width"], lo),
            Check.at_least("axial_tooth_width", d["axial_tooth_width"], lo),
            Check.at_least("slot_width", d["slot_width"], lim["min_slot_width_mm"]),
            Check.at_most("slot_opening", d["slot_opening"], d["slot_width"]),
            Check.at_least("yoke_length", d["yoke_length"], lo, d["axial_length"]),
            Check.at_most("radial_tooth_length", d["radial_tooth_length"], d["core_length"], d["axial_length"]),
            Check.at_most("coil_radial", d["coil_thickness"] + a, d["room_radial"], d["outer_radius"]),
            Check.at_most("coil_axial", d["coil_thickness"] + a, d["room_axial"], d["axial_length"]),
            Check.at_most("coil_inner", d["coil_thickness"] + a, d["room_inner"], d["outer_radius"]),
        ]
        try:
            self.layout(spec, values)
        except ValueError:
            out.append(Check.at_least("balanced_winding", 0.0, 1.0))
        return out

    def layout(self, spec, values):
        m = spec["machine"]
        return winding_layout.toroidal(int(m["slots"]), int(values["pole_pairs"]), int(m["phases"]))

    def winding_description(self, spec, values):
        m = spec["machine"]
        try:
            coils = self.layout(spec, values)
        except ValueError:
            coils = None
        return winding_layout.describe("toroidal", coils, int(m["slots"]), int(values["pole_pairs"]), m["phases"], 1)

    def winding(self, spec, values):
        d, w = self.derive(spec, values), spec["winding"]
        return Winding(phases=spec["machine"]["phases"], turns=w["turns"], coil_area_mm2=d["coil_area_mm2"],
                       mean_turn_length_mm=d["turn_length_mm"], fill_factor=copper_fill(spec),
                       coils_per_phase=d["coils_per_phase"], conductor=w["conductor"],
                       coil_height_mm=d["coil_thickness"], coil_width_mm=d["coil_width"], wire=w.get("wire"))

    def thermal_network(self, spec, values):
        """Coils to the core through the insulation (the face on the yoke and both slot walls); core
        to ambient through the stator support at the bore; core to rotor across the three gaps;
        rotor to ambient over its cylinder and both discs."""
        d, th = self.derive(spec, values), spec["thermal"]
        mm2 = 1e-6
        a = spec["winding"]["coil_clearance_mm"]
        hole = 2 * (d["yoke_outer_radius"] - d["yoke_inner_radius"] + d["yoke_length"] + 4 * a)
        contact = d["slots"] * (hole * d["coil_width"] + 2 * d["turn_length_mm"] * d["coil_thickness"]) * mm2
        g_winding_core = contact * th["insulation_conductivity_W_mK"] / (th["insulation_thickness_mm"] * 1e-3)
        g_core_ambient = th["h_mount_W_m2K"] * 2 * math.pi * d["bore_radius"] * d["core_length"] * mm2
        gaps = 2 * math.pi * d["stator_radius"] * d["radial_tooth_length"] + \
            2 * math.pi * (d["yoke_outer_radius"] ** 2 - d["yoke_inner_radius"] ** 2)
        g_core_rotor = th["h_air_gap_W_m2K"] * gaps * mm2
        outside = 2 * math.pi * d["outer_radius"] * d["axial_length"] + 2 * math.pi * d["outer_radius"] ** 2
        g_rotor_ambient = th["h_external_W_m2K"] * outside * mm2
        return ThermalNetwork(conductances=(("winding", "core", g_winding_core), ("core", AMBIENT, g_core_ambient),
                                            ("core", "rotor", g_core_rotor), ("rotor", AMBIENT, g_rotor_ambient)),
                              ambient_C=spec["operating_point"]["ambient_C"])

    def excitation(self, spec, values):
        return ExcitationPlan(mode="all_phases", phases=spec["machine"]["phases"],
                              electrical_period_deg=360.0 / int(values["pole_pairs"]),
                              positions=int(spec["fidelity"]["positions"]))

    def rotor_offset_deg(self, spec, values):
        """Rotor angle (mechanical degrees) at which the flux of phase 0 is largest (positive). A toroidal
        coil links the yoke flux at its slot, which peaks where a pole boundary passes the slot: 90
        electrical degrees from the coil's phasor p theta_k (winding_layout.toroidal); the sign of the
        flux of a north pole (magnet 0) in the yoke fixes which of the two (checked by the field model)."""
        coils = self.layout(spec, values)
        p = coils.pole_pairs
        total = sum(c.sign * cmath.exp(1j * math.radians(p * c.slot_in * 360.0 / coils.slots))
                    for c in coils.coils if c.phase == 0)
        return (math.degrees(cmath.phase(total)) + 90.0) / p

    def geometry(self, spec, values, fidelity=None):
        """The quasi-3D model (T55): a radial section at z = 0 and axial slices across the axial
        magnets, solved with the 2D solver and summed (geometry kind "rafm.quasi3d")."""
        values = standard_values(spec, values)
        d, m = self.derive(spec, values), spec["machine"]
        coils = self.layout(spec, values)
        level = spec["fidelity"]["levels"][fidelity or spec["fidelity"]["level"]]
        n = self.SLICES
        dr = (d["yoke_outer_radius"] - d["yoke_inner_radius"]) / n
        slices = [{"radius": d["yoke_inner_radius"] + (i + 0.5) * dr, "depth": dr} for i in range(n)]
        parameters = {
            "rafm": {"slots": d["slots"], "pole_pairs": d["pole_pairs"], "outer_radius": d["outer_radius"],
                     "magnet_inner_radius": d["rotor_gap_radius"], "magnet_thickness": values["magnet_thickness_mm"],
                     "magnet_arc_el_deg": values["magnet_arc_el_deg"], "stator_radius": d["stator_radius"],
                     "yoke_outer_radius": d["yoke_outer_radius"], "yoke_inner_radius": d["yoke_inner_radius"],
                     "bore_radius": d["bore_radius"], "slot_width": d["slot_width"], "slot_opening": d["slot_opening"],
                     "tooth_tip_height": d["tooth_tip_height"], "coil_thickness": d["coil_thickness"],
                     "coil_clearance": spec["winding"]["coil_clearance_mm"], "air_gap": m["air_gap_mm"],
                     "radial_tooth_length": d["radial_tooth_length"], "yoke_length": d["yoke_length"],
                     "core_length": d["core_length"], "axial_length": d["axial_length"],
                     "axial_magnet_thickness": values["axial_magnet_thickness_mm"],
                     "axial_magnet_arc_el_deg": values["axial_magnet_arc_el_deg"],
                     "rotor_iron": values["rotor_iron_mm"], "disc_iron": values["disc_iron_mm"],
                     "coils": [{"slot": c.slot_in, "phase": c.phase, "sign": c.sign} for c in coils.coils],
                     "rotor_offset_deg": self.rotor_offset_deg(spec, values), "slices": slices},
            "mesh": {"gap_cell": level["gap_cell_factor"] * m["air_gap_mm"] / 2, "size_max": level["size_max_mm"]},
            "sweep": {"mode": "all_phases", "pole_pairs": d["pole_pairs"], "phases": m["phases"],
                      "current_angle_deg": spec["operating_point"].get("current_angle_deg", 0.0)},
            "analysis": analysis_settings(spec, d["ampere_turns_peak"]),
            "design": dict(values),
        }
        return GeometryRequest("rafm.quasi3d", parameters)
