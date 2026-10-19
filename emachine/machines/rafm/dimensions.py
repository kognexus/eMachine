"""
Dimensions of the radial-axial ("raxial") machine with a toroidal winding (T53, docs/parameters.md).

Cross-section in the r-z plane (machine axis z, stack centred on z = 0), from the outside in:

    radial rotor   outer radius R (spec outer diameter / 2): rotor iron, radial magnets, air gap
    stator         radius R_s at the radial teeth; the radial teeth stand on the yoke between
                   r_yo and R_s over the axial length L_r; the yoke ring is r_yi .. r_yo, z = +-h_y/2;
                   the axial teeth stand on both end faces of the yoke (r_yi .. r_yo) up to the core
                   length L_c; inner teeth fill r_b .. r_yi (they carry the stator, not the flux)
    axial rotors   two discs facing the axial teeth across the axial gap: magnets, then disc iron;
                   the total axial length (spec stack length) closes the axial chain:
                   L_c = L - 2 (gap + axial magnet + disc iron)

Coils: one toroidal coil in each of the Q slots, a rectangular loop of thickness c around the yoke
section (clearance a): its outer side lies in the radial slot, its end sides in the axial slots,
its inner side between the inner teeth. Slots are parallel-sided (width w), with tooth tips that
leave an opening b0 over a height t at the gap faces.
"""

import math

COPPER_DENSITY = 8960.0      # kg/m3


def derive(spec, values):
    """All dimensions of one design (mm, mm2, mm3; kg for masses)."""
    m, w = spec["machine"], spec["winding"]
    v = values
    gap, a = m["air_gap_mm"], w["coil_clearance_mm"]
    slots, p = int(m["slots"]), int(v["pole_pairs"])
    R = m["outer_diameter_mm"] / 2
    L = m["stack_length_mm"]
    r_b = m["bore_diameter_mm"] / 2
    # radial chain
    r_magnet_in = R - v["rotor_iron_mm"] - v["magnet_thickness_mm"]
    R_s = r_magnet_in - gap
    r_yo = R_s - v["radial_tooth_height_mm"]
    r_yi = r_yo - v["yoke_width_mm"]
    # axial chain: the core length closes it
    L_c = L - 2 * (gap + v["axial_magnet_thickness_mm"] + v["disc_iron_mm"])
    h_y = L_c - 2 * v["axial_tooth_height_mm"]
    L_r = v["radial_tooth_length_mm"]
    c, slot_w, b0, t = v["coil_thickness_mm"], v["slot_width_mm"], v["slot_opening_mm"], v["tooth_tip_height_mm"]
    # coil loop around the yoke section (r_yi .. r_yo, +-h_y/2), clearance a, thickness c
    inner_r, inner_z = r_yo - r_yi + 2 * a, h_y + 2 * a       # sides of the hole of the loop
    loop = 2 * (inner_r + c) + 2 * (inner_z + c)              # mean turn length
    coil_w = slot_w - 2 * a                                   # circumferential width of a coil
    coil_area = coil_w * c                                    # cross-section of the conductors of one coil
    # teeth widths at their narrowest radius (parallel-sided slots)
    pitch = 2 * math.pi / slots
    radial_tooth = pitch * r_yo - slot_w                      # radial tooth at its root
    axial_tooth = pitch * r_yi - slot_w                       # axial tooth at the inner edge of its face
    tip_radial = pitch * R_s - b0                             # tip of a radial tooth at the gap
    tip_axial = pitch * r_yi - b0
    # rooms the coil must fit
    room_radial = R_s - t - r_yo                              # radial slot below the tips
    room_axial = (L_c - h_y) / 2 - t                          # axial slot below the tips
    room_inner = r_yi - r_b                                   # between bore and yoke, for the inner side
    # magnets
    pole = math.pi / p
    radial_magnet = (math.pi * ((r_magnet_in + v["magnet_thickness_mm"]) ** 2 - r_magnet_in ** 2) * L_r
                     * v["magnet_arc_el_deg"] / 180.0)
    axial_magnets = 2 * math.pi * (r_yo ** 2 - r_yi ** 2) * v["axial_magnet_thickness_mm"] * v["axial_magnet_arc_el_deg"] / 180.0
    # stator core (SMC): yoke, radial teeth, axial teeth (two faces), inner teeth
    yoke = math.pi * (r_yo ** 2 - r_yi ** 2) * h_y
    slot_radial = slot_w * (room_radial) + b0 * t
    teeth_radial = L_r * (math.pi * (R_s ** 2 - r_yo ** 2) - slots * slot_radial)
    slot_axial = (r_yo - r_yi) * (slot_w * (room_axial) + b0 * t)
    teeth_axial = 2 * (((L_c - h_y) / 2) * math.pi * (r_yo ** 2 - r_yi ** 2) - slots * slot_axial)
    teeth_inner = L_c * (math.pi * (r_yi ** 2 - r_b ** 2) - slots * slot_w * (r_yi - r_b))
    core = yoke + teeth_radial + teeth_axial + teeth_inner
    # rotor steel: radial ring over the whole length, two discs from the axial magnets' inner edge
    disc_in = r_yi - 5.0
    rotor_ring = math.pi * (R ** 2 - (R - v["rotor_iron_mm"]) ** 2) * L
    discs = 2 * math.pi * ((R - v["rotor_iron_mm"]) ** 2 - disc_in ** 2) * v["disc_iron_mm"]
    mat = spec["materials"]
    fill = w["fill_factor"]
    frequency = spec["operating_point"]["speed_rpm"] / 60.0 * p
    ni_rms = v["current_density_A_mm2"] * coil_area * fill
    return {
        "pole_pairs": p, "slots": slots, "outer_radius": R, "bore_radius": r_b,
        "rotor_gap_radius": r_magnet_in, "stator_radius": R_s, "yoke_outer_radius": r_yo, "yoke_inner_radius": r_yi,
        "core_length": L_c, "yoke_length": h_y, "radial_tooth_length": L_r, "axial_length": L,
        "axial_gap_z": L_c / 2, "axial_magnet_r0": r_yi, "axial_magnet_r1": r_yo, "pole_angle_rad": pole,
        "slot_width": slot_w, "slot_opening": b0, "tooth_tip_height": t, "coil_thickness": c, "coil_width": coil_w,
        "coil_area_mm2": coil_area, "coils_per_phase": slots // int(m["phases"]), "turn_length_mm": loop,
        "radial_tooth_width": radial_tooth, "axial_tooth_width": axial_tooth,
        "radial_tip_width": tip_radial, "axial_tip_width": tip_axial,
        "room_radial": room_radial, "room_axial": room_axial, "room_inner": room_inner,
        "magnet_volume_mm3": radial_magnet + axial_magnets, "radial_magnet_volume_mm3": radial_magnet,
        "axial_magnet_volume_mm3": axial_magnets, "core_volume_mm3": core,
        "copper_volume_mm3": slots * loop * coil_area * fill,
        "rotor_steel_volume_mm3": rotor_ring + discs,
        "magnet_mass_kg": (radial_magnet + axial_magnets) * 1e-9 * mat["magnet"]["density_kg_m3"],
        "core_mass_kg": core * 1e-9 * mat["stator_core"]["density_kg_m3"],
        "copper_mass_kg": slots * loop * coil_area * fill * 1e-9 * COPPER_DENSITY,
        "rotor_steel_mass_kg": (rotor_ring + discs) * 1e-9 * mat["rotor_iron"]["density_kg_m3"],
        "machine_volume_mm3": math.pi * R ** 2 * L,
        "ampere_turns_rms": ni_rms, "ampere_turns_peak": ni_rms * math.sqrt(2),
        "electrical_frequency_Hz": frequency,
        # for the shared code of slotted machines
        "stack_length": L_r, "slot_depth": c, "coil_height": c,
    }
