"""Thermal network of one TFM phase: winding, stator core and rotor (magnets), with ambient."""

import math

from emachine.core.types import AMBIENT, ThermalNetwork


def machine_conductances(spec, values, d):
    """Conductances in W/K of the one-phase network: winding, core, rotor, ambient."""
    th = spec["thermal"]
    mm2 = 1e-6
    coverage = d["core_coverage"]                  # share of the circumference taken by stator iron
    # Winding to core: the coil touches the two legs and the yoke of every U-core.
    side_faces = 2.0 * math.pi * (d["coil_r1"] ** 2 - d["coil_r0"] ** 2)
    yoke_radius = d["coil_r0"] if d["outrunner"] else d["coil_r1"]
    yoke_face = 2.0 * math.pi * yoke_radius * d["coil_width"]
    contact = coverage * (side_faces + yoke_face) * mm2
    path = (th["insulation_thickness_mm"] * 1e-3 / th["insulation_conductivity_W_mK"]
            + 0.25 * min(d["coil_height"], d["coil_width"]) * 1e-3 / th["winding_conductivity_W_mK"])
    g_winding_core = contact / path

    # Core to rotor: convection across the air gap over the pole faces.
    pole_faces = d["pole_face_area_mm2"]
    g_core_rotor = th["h_air_gap_W_m2K"] * pole_faces * mm2

    # Core to ambient, and rotor to ambient.
    width = d["phase_width"]
    if d["outrunner"]:
        mount = coverage * 2.0 * math.pi * d["stator_far_radius"] * width * mm2
        g_core_ambient = th["h_mount_W_m2K"] * mount
        g_rotor_ambient = th["h_external_W_m2K"] * 2.0 * math.pi * d["outer_radius"] * width * mm2
    else:
        g_core_ambient = th["h_external_W_m2K"] * 2.0 * math.pi * d["outer_radius"] * width * mm2
        ends = 2.0 * math.pi * (d["rotor_gap_radius"] ** 2 - d["bore_radius"] ** 2) * mm2
        g_rotor_ambient = th["h_external_W_m2K"] * ends
    return [("winding", "core", g_winding_core), ("core", "rotor", g_core_rotor),
            ("core", AMBIENT, g_core_ambient), ("rotor", AMBIENT, g_rotor_ambient)]


def network(spec, values, d):
    return ThermalNetwork(conductances=tuple(machine_conductances(spec, values, d)),
                          ambient_C=spec["operating_point"]["ambient_C"])
