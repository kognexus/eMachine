"""A buildable reference design for the default specification, used by studies and tests."""

#: Outrunner with I-bridges, 80 mm outer diameter, 23 mm stack: close to the user's corrected motor,
#: with the hub collision removed (narrower cores, shallower slot).
REFERENCE_DESIGN = {
    "pole_pairs": 18,
    "tooth_arc_el_deg": 126.0,
    "leg_width_mm": 5.0,
    "slot_height_mm": 14.0,
    "yoke_height_mm": 5.0,
    "magnet_thickness_mm": 2.0,
    "current_density_A_mm2": 5.0,
    "rotor_iron_mm": 2.7,
    "bridge_height_mm": 3.0,
}
