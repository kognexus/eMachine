"""
The dialog values of the Onshape feature "eMachine" (featurescript/emachine_main.fs) for a design:
every field the dialog shows for the machine, under the field name of the dialog, in dialog order.

    rows = sheet.emachine_rows(spec, values)      # [(field, text), ...]

The dialog takes the inputs of the specification and the design variables (lengths and arcs,
docs/parameters.md); the feature derives the other dimensions as the Python model does. `checks` lists derived dimensions to compare with
the finished model.
"""

import math

from emachine.machines.base import stator_pole_arc_deg
from emachine.pipeline import design_space

#: standard names (docs/naming.md) -> the entries of the dialog's enums
FLUX_PATHS = {"tfm": "TFM: transverse flux", "rfm": "RFM: radial flux", "afm": "AFM: axial flux",
              "rafm": "RAFM: radial-axial flux"}
PRINCIPLES = {"pmsm": "PMSM: permanent magnet synchronous", "synrm": "SynRM: synchronous reluctance",
              "srm": "SRM: switched reluctance", "vernier": "Vernier (PM vernier, flux modulation)"}
ROTORS = {"halbach": "Halbach array", "surface": "Surface magnets (SPM)", "inset": "Inset magnets",
          "interior": "Interior magnets (IPM, V)", "spoke": "Spoke (flux concentrating)",
          "axial_ring": "Axial ring magnet between toothed discs", "flux_barrier": "Flux barriers (SynRM)",
          "flux_barrier_pm": "Flux barriers with magnets (PMaSynRM)", "salient": "Salient iron poles (SRM)"}
STATORS = {"u_core": "U-core", "ui_core": "U-core with I-bridge", "c_core": "C-core", "e_core": "E-core",
           "z_core": "Z-core", "claw_pole": "Claw pole", "toothed_ring": "Toothed ring (Fig. 17)"}
PLACEMENTS = {"inner": "Inner rotor", "outer": "Outer rotor"}
SPANS = {"concentrated": "Concentrated (tooth coils)", "distributed": "Distributed (overlapping coils)"}
def mm(value):
    return f"{value:.4f} mm"


def deg(value):
    return f"{value:.4f} deg"


def emachine_rows(spec, values):
    """(field of the eMachine dialog, value as text): the inputs of the specification and the design
    variables, in dialog order. The feature derives every other dimension from these."""
    m, w = spec["machine"], spec["winding"]
    tfm, srm = m["flux_path"] == "tfm", m["principle"] == "srm"
    rotor = m["rotor"]
    rows = [("Flux path", FLUX_PATHS[m["flux_path"]]), ("Torque principle", PRINCIPLES[m["principle"]]),
            ("Rotor layout", ROTORS[rotor]), ("Rotor placement", PLACEMENTS[m["rotor_placement"]]),
            ("Number of phases", str(m["phases"])), ("Outer diameter", mm(m["outer_diameter_mm"])),
            ("Stack length (all phases)", mm(m["stack_length_mm"])), ("Air gap", mm(m["air_gap_mm"])),
            ("Bore diameter (shaft, or the free bore inside an inner stator)", mm(m["bore_diameter_mm"]))]
    if not srm:
        rows.append(("Pole pairs", str(int(values["pole_pairs"]))))
    rows += [("Yoke height", mm(values["yoke_height_mm"])), ("Slot height", mm(values["slot_height_mm"]))]
    if tfm:
        stator = m["stator"]
        rows += [("Stator layout", STATORS[stator]), ("Phase spacing", mm(m["phase_spacing_mm"])),
                 ("Pole shift (electrical)", f"{m['pole_shift_el_deg']:g} deg"),
                 ("Tooth arc (electrical, 180: whole pole pitch)", deg(values["tooth_arc_el_deg"])),
                 ("Leg width", mm(values["leg_width_mm"]))]
        if m["rotor_placement"] == "outer":
            rows.append(("Rotor iron (housing behind the magnets)", mm(values["rotor_iron_mm"])))
        if stator == "ui_core":
            rows.append(("I-bridge height", mm(values["bridge_height_mm"])))
        if stator == "toothed_ring":
            rows += [("Ring tooth height", mm(values["ring_tooth_height_mm"])),
                     ("Arched valleys between teeth", "on" if m["ring_arched_valleys"] else "off"),
                     ("Staggered teeth (back wall one pole pitch later)", "on" if m["ring_staggered_teeth"] else "off")]
        if stator == "claw_pole":
            rows += [("Claw root height", mm(values["claw_root_height_mm"])),
                     ("Claw tip height", mm(values["claw_tip_height_mm"])), ("Claw tip gap", mm(values["claw_tip_gap_mm"]))]
        rows += [("Coil clearance", mm(w["coil_clearance_mm"])),
                 ("Coil margin (to the pole face or the I-bridge)", mm(w["coil_margin_mm"]))]
        if rotor == "spoke":
            rows.append(("Spoke magnet radial height", mm(values["magnet_height_mm"])))
    else:
        rows += [("Slots", str(m["slots"])), ("Slot width (parallel-sided slot)", mm(values["slot_width_mm"])),
                 ("Winding span", SPANS[w["span"]]), ("Winding layers", str(w["layers"])),
                 ("Coil pitch in slots (0: 1 or full pitch)", str(w["pitch_slots"] or 0))]
    if tfm or rotor in ("surface", "interior"):
        rows.append(("Magnet thickness (spoke: magnet width)", mm(values["magnet_thickness_mm"])))
    if rotor in ("surface", "axial_ring"):
        rows.append(("Magnet arc (electrical, 180: whole pole)", deg(values["magnet_arc_el_deg"])))
    if rotor == "interior":
        rows += [("Magnet length (each bar of the V)", mm(values["magnet_length_mm"])),
                 ("V angle (180: one flat bar)", deg(values["v_angle_deg"])),
                 ("Bridge to the rotor surface", mm(values["bridge_mm"]))]
    if rotor in ("flux_barrier", "flux_barrier_pm"):
        rows += [("Flux barriers per pole", str(m["barriers"])), ("Barrier width", mm(values["barrier_width_mm"])),
                 ("Rib", mm(values["rib_mm"]))]
        if rotor == "flux_barrier_pm":
            rows.append(("Magnet width (across the q axis)", mm(values["magnet_width_mm"])))
    if srm:
        rows += [("Rotor poles", str(m["rotor_poles"])), ("Rotor pole arc (mechanical)", deg(values["rotor_pole_arc_deg"])),
                 ("Rotor pole height", mm(values["rotor_pole_height_mm"]))]
    return rows


#: dialog of the "Raxial machine" feature (hybrid_design.fs, T54): field -> design variable (mm unless an arc)
RAXIAL_FIELDS = (
    ("Radial rotor iron", "rotor_iron_mm"), ("Radial magnet thickness", "magnet_thickness_mm"),
    ("Radial magnet arc (electrical, 180: whole pole)", "magnet_arc_el_deg"),
    ("Radial tooth height", "radial_tooth_height_mm"), ("Radial tooth axial length", "radial_tooth_length_mm"),
    ("Yoke width (radial)", "yoke_width_mm"), ("Axial tooth height", "axial_tooth_height_mm"),
    ("Disc iron", "disc_iron_mm"), ("Axial magnet thickness", "axial_magnet_thickness_mm"),
    ("Axial magnet arc (electrical, 180: whole pole)", "axial_magnet_arc_el_deg"),
    ("Slot width (parallel-sided)", "slot_width_mm"), ("Slot opening", "slot_opening_mm"),
    ("Tooth tip height", "tooth_tip_height_mm"), ("Coil thickness (around the yoke)", "coil_thickness_mm"))


def raxial_rows(spec, values):
    """(field of the "Raxial machine" dialog, value as text) for a rafm/pmsm design."""
    m = spec["machine"]
    rows = [("Outer diameter (radial rotor)", mm(m["outer_diameter_mm"])), ("Total axial length", mm(m["stack_length_mm"])),
            ("Air gap (radial and axial)", mm(m["air_gap_mm"])), ("Bore diameter (stator support)", mm(m["bore_diameter_mm"])),
            ("Number of phases", str(m["phases"])), ("Slots", str(m["slots"])), ("Pole pairs", str(int(values["pole_pairs"])))]
    rows += [(field, deg(values[key]) if key.endswith("_deg") else mm(values[key])) for field, key in RAXIAL_FIELDS]
    return rows + [("Coil clearance", mm(spec["winding"]["coil_clearance_mm"]))]


def raxial_checks(spec, values):
    d = design_space.machine_of(spec).derive(spec, values)
    return [("Stator diameter at the radial teeth", mm(2 * d["stator_radius"])),
            ("Yoke radii", f"{d['yoke_inner_radius']:.4f} .. {d['yoke_outer_radius']:.4f} mm"),
            ("Stator core length", mm(d["core_length"])), ("Yoke axial length", mm(d["yoke_length"])),
            ("Volumes (mm3): stator core, coils, magnets",
             f"{d['core_volume_mm3']:.0f}, {d['copper_volume_mm3'] / spec['winding']['fill_factor']:.0f}, "
             f"{d['magnet_volume_mm3']:.0f}")]


def checks(spec, values):
    """Dimensions the feature derives, to compare with the finished model."""
    m = spec["machine"]
    if m["flux_path"] == "tfm":
        from emachine.machines.tfm import design
        p = design.to_parameters(spec, values)
        st, ro = p["stator"], p["rotor"]
        gap_d = ro["inner_diameter"] if m["rotor_placement"] == "outer" else ro["outer_diameter"]
        return [("Stator air-gap radius", mm(st["air_gap_radius"])), ("Rotor diameter at the air gap", mm(gap_d)),
                ("Slot width", mm(st["slot_width"])), ("Coil height", mm(st["coil_height"])),
                ("Axial width of one phase", mm(ro["stack_length"]))]
    d = design_space.machine_of(spec).derive(spec, values)
    out = [("Bore diameter (stator)", mm(2 * d["bore_radius"])), ("Rotor outer diameter", mm(2 * d["rotor_radius"])),
           ("Tooth width at the bore", mm(d["tooth_width"]))]
    if m["principle"] == "srm":
        out.append(("Stator pole arc at the bore", deg(stator_pole_arc_deg(d["slots"], d["slot_width"], d["bore_radius"]))))
    core = math.pi * (d["back_radius"] ** 2 - d["bore_radius"] ** 2) - d["slots"] * d["slot_area_mm2"]
    return out + [("Stator core area of the section (x stack = volume)", f"{core:.1f} mm2")]


def to_text(rows, heading):
    width = max(len(field) for field, _ in rows)
    return "\n".join([heading, "=" * len(heading), ""] + [f"  {field:<{width}}  {text}" for field, text in rows])


def to_markdown(rows, heading):
    return "\n".join([f"# {heading}", "", "| Field | Value |", "|---|---|"]
                     + [f"| {field} | {text} |" for field, text in rows]) + "\n"
