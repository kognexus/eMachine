"""What every axial flux machine shares: the active annulus and the arrangement of discs."""

import math

from emachine.core.types import AMBIENT, Check, ThermalNetwork, Variable
from emachine.spec import SpecError
from emachine.spec.names import standard_values

from ..base import SlottedMachine

ARRANGEMENTS = ("single", "double_rotor", "double_stator")
#: arrangement -> (stators, slotted faces, rotor discs, rotor faces with magnets or poles)
DISCS = {"single": (1, 1, 1, 1), "double_rotor": (1, 2, 2, 2), "double_stator": (2, 2, 1, 2)}


class AxialFlux(SlottedMachine):
    """
    Discs along the axis (docs/parameters.md): the active annulus lies between `inner_diameter_mm`
    and the outer diameter; each slotted stator face has `slots` rectangular slots (constant width,
    so the teeth are narrowest at the inner diameter) of axial depth `slot_height_mm` in front of
    the stator yoke. The rotor back iron is what the stators, gaps and magnets leave of the axial
    length (`stack_length_mm`). Geometry: the tickets of the rotor layouts.
    """

    flux_path = "afm"

    def extra_options(self):
        return dict(super().extra_options(), arrangement="double_rotor")

    def validate(self, spec):
        super().validate(spec)
        if spec["machine"]["arrangement"] not in ARRANGEMENTS:
            raise SpecError(f"'machine.arrangement' must be one of {ARRANGEMENTS}, got {spec['machine']['arrangement']!r}.")

    def common_variables(self, spec):
        lim, m = spec["limits"], spec["machine"]
        lo, hi = lim["iron_thickness_mm"]
        outer, length = m["outer_diameter_mm"], m["stack_length_mm"]
        inner_lo = min(max(m["bore_diameter_mm"] + 2 * lo, 0.3 * outer), 0.85 * outer)
        slot_lo, coil_lo = lim["min_slot_width_mm"], lim["min_coil_height_mm"]
        return [
            Variable("pole_pairs", lim["pole_pairs"][0], lim["pole_pairs"][1], "int"),
            Variable("inner_diameter_mm", inner_lo, 0.85 * outer, unit="mm"),
            Variable("slot_height_mm", coil_lo, max(coil_lo, 0.5 * length), unit="mm"),
            Variable("slot_width_mm", slot_lo, max(slot_lo, math.pi * outer / (2 * m["slots"])), unit="mm"),
            Variable("yoke_height_mm", lo, hi, unit="mm"),
            Variable("current_density_A_mm2", 1.0, max(1.0, lim["max_current_density_A_mm2"])),
        ]

    def derive(self, spec, values):
        values = standard_values(spec, values)
        m, op = spec["machine"], spec["operating_point"]
        stators, faces, rotors, rotor_faces = DISCS[m["arrangement"]]
        p, slots = int(values["pole_pairs"]), int(m["slots"])
        r_out, r_in = m["outer_diameter_mm"] / 2, values["inner_diameter_mm"] / 2
        r_mean = (r_out + r_in) / 2
        height, slot_width, yoke = values["slot_height_mm"], values["slot_width_mm"], values["yoke_height_mm"]
        # the stator: slotted faces in front of the yoke (double rotor: one yoke between two slotted faces)
        stator = (faces // stators) * height + yoke
        rotor_part = values.get("magnet_thickness_mm", values.get("rotor_pole_height_mm", 0.0))  # magnets or salient poles
        gaps = rotor_faces * (m["air_gap_mm"] + rotor_part)
        back_iron = (m["stack_length_mm"] - stators * stator - gaps) / rotors
        d = self._winding_dimensions(spec, values, {
            "pole_pairs": p, "slots": slots, "outer_radius": r_out, "inner_radius": r_in, "mean_radius": r_mean,
            "bore_radius": r_mean, "rotor_radius": r_out, "slot_depth": height, "slot_width": slot_width,
            "slot_pitch": 2 * math.pi * r_mean / slots, "tooth_width": 2 * math.pi * r_in / slots - slot_width,
            "slot_area_mm2": slot_width * height, "yoke_height": yoke, "stator_length": stator,
            "rotor_back_iron": back_iron, "stack_length": r_out - r_in,       # a turn's straight part is radial
            "axial_length": m["stack_length_mm"], "coil_height": height, "slotted_faces": faces, "rotor_discs": rotors,
            "electrical_frequency_Hz": op["speed_rpm"] / 60.0 * self.electrical_pole_pairs(spec, values)})
        d["coils_per_phase"] *= faces                          # every slotted face carries a winding
        return d

    def stator_checks(self, spec, d):
        """The tooth at the inner diameter, the slot, the annulus above the shaft, the rotor back iron
        (a double-stator rotor may have none: its magnets carry the flux through)."""
        lim, m = spec["limits"], spec["machine"]
        lo = lim["iron_thickness_mm"][0]
        back_lo = 0.0 if m["arrangement"] == "double_stator" else lo
        return [Check.at_least("tooth_width", d["tooth_width"], lo),
                Check.at_least("slot_width", d["slot_width"], lim["min_slot_width_mm"]),
                Check.at_least("inner_diameter", d["inner_radius"], m["bore_diameter_mm"] / 2 + lo, d["outer_radius"]),
                Check.at_least("rotor_back_iron", d["rotor_back_iron"], back_lo, d["axial_length"])]

    def thermal_network(self, spec, values):
        """Winding to stator through the slot insulation; stator to ambient over its rim; rotors to
        the stator across the gaps; rotors to ambient over their outer faces and rims."""
        d, th = self.derive(spec, values), spec["thermal"]
        mm2 = 1e-6
        annulus = math.pi * (d["outer_radius"] ** 2 - d["inner_radius"] ** 2)
        slot_wall = d["slotted_faces"] * d["slots"] * (2 * d["slot_depth"] + d["slot_width"]) * d["stack_length"] * mm2
        g_winding_core = slot_wall * th["insulation_conductivity_W_mK"] / (th["insulation_thickness_mm"] * 1e-3)
        g_core_ambient = th["h_external_W_m2K"] * 2 * math.pi * d["outer_radius"] * d["stator_length"] * mm2
        g_core_rotor = th["h_air_gap_W_m2K"] * d["slotted_faces"] * annulus * mm2
        g_rotor_ambient = th["h_external_W_m2K"] * d["rotor_discs"] * math.pi * d["outer_radius"] ** 2 * mm2
        return ThermalNetwork(conductances=(("winding", "core", g_winding_core), ("core", AMBIENT, g_core_ambient),
                                            ("core", "rotor", g_core_rotor), ("rotor", AMBIENT, g_rotor_ambient)),
                              ambient_C=spec["operating_point"]["ambient_C"])
