"""
Parameter sheet for the Onshape model.

The CAD model is built by two custom features, "TFM stator" (tfm_stator.fs) and "TFM rotor"
(tfm_rotor.fs). `sheet` lists the values of a design under the field names of those two dialogs,
in dialog order, and only the fields the dialog shows for the chosen options.
"""

import math

CORE_NAMES = {"u": "U-core", "ui": "U-core with I-bridge", "tr": "Toothed ring (Fig. 17)", "c": "C-core",
              "cp": "Claw-pole (CP) core", "e": "E-core", "z": "Z-core"}
CONFIGURATION_NAMES = {"inrunner": "Inrunner (rotor inside the stator)",
                       "outrunner": "Outrunner (rotor around the stator)"}
ROTOR_NAMES = {"surface": "Interleaved N-S surface magnets", "halbach": "Halbach array",
               "axial": "Axially magnetised ring between toothed discs",
               "flux_concentrating": "Flux concentrating (magnets interleaved with iron poles)"}

# Ranges the dialogs accept (from the bound specifications in the .fs files). Lengths in mm.
DIALOG_RANGES = {
    ("stator", "Pole pairs"): (4, 500),
    ("stator", "Tooth span / pole pitch"): (0.1, 1.0),
    ("stator", "I-bridge top width / slot width"): (0.05, 2.0),
    ("rotor", "Number of poles"): (2, 1000),
    ("rotor", "Segments per pole"): (2, 12),
    ("rotor", "Axial magnet rows"): (1, 12),
    ("rotor", "Magnet arc / pole pitch"): (0.1, 1.0),
    ("rotor", "Gap between rows"): (0.0, 500e3),
    ("rotor", "Shaft diameter"): (0.0, 500e3),
}
LENGTH_RANGE = (0.01, 500e3)


def _row(feature, field, value, kind):
    """kind: 'mm', 'ratio', 'count', 'switch' or 'choice'."""
    row = {"field": field, "kind": kind, "value": value, "note": ""}
    if kind == "mm":
        row["text"] = f"{value:.3f} mm"
    elif kind == "ratio":
        row["text"] = f"{value:.4f}"
    elif kind == "count":
        row["text"] = str(int(value))
    elif kind == "switch":
        row["text"] = "on" if value else "off"
    else:
        row["text"] = str(value)
    if kind in ("mm", "ratio", "count"):
        low, high = DIALOG_RANGES.get((feature, field), LENGTH_RANGE if kind == "mm" else (None, None))
        if low is not None and not (low - 1e-12 <= value <= high + 1e-12):
            row["note"] = f"outside the range the dialog accepts ({low:g} to {high:g})"
    return row


def stator_rows(stator, phases=1, spacing=0.0):
    f = "stator"
    core = stator["core_type"]
    rows = [
        _row(f, "Core structure", CORE_NAMES.get(core, core), "choice"),
        _row(f, "Arrangement", "Rotary ring", "choice"),
        _row(f, "Air-gap radius", stator["air_gap_radius"], "mm"),
        _row(f, "Pole pairs", stator["pole_pairs"], "count"),
        _row(f, "Inner stator (outer rotor)", bool(stator.get("inner_stator")), "switch"),
        _row(f, "Trim pole faces to air-gap cylinder", bool(stator.get("trim_pole_faces", True)), "switch"),
        _row(f, "Number of phases", phases, "count")]
    if phases > 1:
        rows.append(_row(f, "Phase spacing", spacing, "mm"))
    rows += [
        {"field": "Pole shift angle", "kind": "deg", "value": stator.get("pole_shift_deg", 0.0), "note": "",
         "text": f"{stator.get('pole_shift_deg', 0.0):.4f} deg"},
        _row(f, "Tooth span / pole pitch", stator["tooth_span"], "ratio"),
        _row(f, "Leg width", stator["leg_width"], "mm"),
        _row(f, "Slot width", stator["slot_width"], "mm"),
        _row(f, "Slot height", stator["slot_height"], "mm"),
        _row(f, "Yoke height", stator["yoke_height"], "mm"),
    ]
    if core == "ui":
        rows += [_row(f, "I-bridge height", stator["bridge_height"], "mm"),
                 _row(f, "I-bridge top width / slot width", stator.get("bridge_top_ratio", 0.8), "ratio")]
    if core == "tr":
        rows += [_row(f, "Ring tooth height", stator["ring_tooth_height"], "mm"),
                 _row(f, "Arched valleys between teeth", bool(stator.get("ring_arched_valleys", False)), "switch"),
                 _row(f, "Staggered teeth (back wall one pole pitch later)", bool(stator.get("ring_staggered_teeth", False)),
                      "switch")]
    if core == "cp":
        rows += [_row(f, "Claw root height", stator["claw_root_height"], "mm"),
                 _row(f, "Claw tip height", stator["claw_tip_height"], "mm"),
                 _row(f, "Claw tip gap", stator["claw_tip_gap"], "mm")]
    coil = bool(stator.get("include_coil", True))
    rows.append(_row(f, "Include coil", coil, "switch"))
    if coil:
        rows += [_row(f, "Coil height", stator["coil_height"], "mm"),
                 _row(f, "Coil clearance", stator["coil_clearance"], "mm")]
    return rows


def rotor_rows(rotor, phases=1, spacing=0.0):
    f = "rotor"
    kind = rotor["type"]
    inrunner = rotor["configuration"] == "inrunner"
    rows = [_row(f, "Configuration", CONFIGURATION_NAMES[rotor["configuration"]], "choice"),
            _row(f, "Rotor type", ROTOR_NAMES[kind], "choice")]
    if inrunner:
        rows += [_row(f, "Outer diameter (air gap)", rotor["outer_diameter"], "mm"),
                 _row(f, "Shaft diameter", rotor["shaft_diameter"], "mm")]
    else:
        rows += [_row(f, "Inner diameter (air gap)", rotor["inner_diameter"], "mm"),
                 _row(f, "Outer diameter", rotor["outer_diameter"], "mm")]
    rows.append(_row(f, "Stack length", rotor["stack_length"], "mm"))
    rows.append(_row(f, "Number of phases", phases, "count"))
    if phases > 1:
        rows.append(_row(f, "Phase spacing", spacing, "mm"))
    rows.append(_row(f, "Number of poles", rotor["poles"], "count"))
    if kind == "flux_concentrating":
        rows += [_row(f, "Magnet radial height", rotor["fc_magnet_height"], "mm"),
                 _row(f, "Magnet width", rotor["fc_magnet_width"], "mm")]
    else:
        rows.append(_row(f, "Magnet thickness", rotor["magnet_thickness"], "mm"))
    if kind in ("surface", "axial"):
        rows.append(_row(f, "Magnet arc / pole pitch", rotor["magnet_arc_ratio"], "ratio"))
    if kind == "halbach":
        rows.append(_row(f, "Segments per pole", rotor.get("segments_per_pole", 2), "count"))
    if kind == "axial":             # the dialog shows only the length of the ring magnet under this name
        rows.append(_row(f, "Gap between rows", rotor.get("row_gap", 0.0), "mm"))
    else:
        rows += [_row(f, "Axial magnet rows", rotor.get("magnet_rows", 1), "count"),
                 _row(f, "Gap between rows", rotor.get("row_gap", 0.0), "mm"),
                 _row(f, "Alternate polarity between rows", bool(rotor.get("alternate_rows", True)), "switch")]
    return rows


def check_rows(parameters):
    """Dimensions that follow from the dialog values, for checking the finished CAD model."""
    stator, rotor = parameters["stator"], parameters["rotor"]
    machine = parameters.get("machine") or {}
    radius = stator["air_gap_radius"]
    height = stator["slot_height"] + stator["yoke_height"] + (stator["claw_root_height"] if stator["core_type"] == "cp" else 0.0)
    width = 2 * stator["leg_width"] + stator["slot_width"]
    rows = []
    if rotor["configuration"] == "inrunner":
        rows += [("Air gap", abs(radius - rotor["outer_diameter"] / 2), "mm"),
                 ("Overall outer diameter (stator)", 2 * (radius + height), "mm"),
                 ("Innermost diameter (shaft)", rotor["shaft_diameter"], "mm")]
    else:
        rows += [("Air gap", abs(rotor["inner_diameter"] / 2 - radius), "mm"),
                 ("Overall outer diameter (rotor)", rotor["outer_diameter"], "mm"),
                 ("Innermost diameter (inner end of the stator cores)", 2 * (radius - height), "mm")]
    rows += [("Axial width of one stator ring", width, "mm"),
             ("Thickness of one stator core along the circumference",
              stator["tooth_span"] * math.pi * radius / stator["pole_pairs"], "mm")]
    phases = int(machine.get("phases", 1))
    if phases > 1:
        spacing = float(machine.get("phase_spacing_mm", 0.0))
        rows += [("Phases", phases, "count"),
                 ("Axial distance between neighbouring phases, centre to centre", width + spacing, "mm"),
                 ("Total axial length", phases * width + (phases - 1) * spacing, "mm"),
                 ("Angle between neighbouring phases (turn the stator ring or the rotor ring)",
                  120.0 / stator["pole_pairs"], "deg")]
    else:
        rows.append(("Total axial length", width, "mm"))
    return [{"field": name, "value": value, "kind": unit, "note": "",
             "text": str(int(value)) if unit == "count" else f"{value:.3f} {unit}"} for name, value, unit in rows]


def resistance_text(ohm):
    return f"{ohm * 1e3:.2f} milliohm" if ohm < 1.0 else f"{ohm:.4f} ohm"


def winding_rows(parameters):
    """Winding data of a pick, when the parameter file carries it."""
    summary = parameters.get("summary") or {}
    if "turns" not in summary:
        return []
    area = summary["wire_area_mm2"]
    if summary.get("conductor") == "strip":
        rows = [("Conductor", "flat copper strip, wound as stacked rings (one ring per layer)"),
                ("Layers (turns) per phase coil", str(int(summary["turns"]))),
                ("Strip copper, axial width x radial thickness",
                 f"{summary['strip_width_mm']:.2f} mm x {summary['strip_thickness_mm']:.3f} mm"),
                ("Copper area per layer", f"{area:.3f} mm2")]
    else:
        rows = [("Turns per phase coil", str(int(summary["turns"]))),
                ("Copper area per turn", f"{area:.4f} mm2"),
                ("Round wire with this copper area", f"{math.sqrt(4 * area / math.pi):.3f} mm diameter")]
    rows += [("Peak phase current", f"{summary['peak_current_A']:.3f} A"),
             ("RMS phase current", f"{summary['rms_current_A']:.3f} A"),
             ("Phase resistance at operating temperature", resistance_text(summary["resistance_ohm"])),
             ("Bus voltage needed at rated speed", f"{summary['required_bus_voltage_V']:.2f} V")]
    return [{"field": name, "text": text, "note": "", "kind": "text", "value": text} for name, text in rows]


def sheet(parameters):
    """Sections of the sheet: list of {title, rows}."""
    sections = [
        {"title": "Feature \"TFM stator v2\"", "rows": stator_rows(
            parameters["stator"], int((parameters.get("machine") or {}).get("phases", 1)),
            float((parameters.get("machine") or {}).get("phase_spacing_mm", 0.0)))},
        {"title": "Feature \"TFM rotor v2\"", "rows": rotor_rows(
            parameters["rotor"], int((parameters.get("machine") or {}).get("phases", 1)),
            float((parameters.get("machine") or {}).get("phase_spacing_mm", 0.0)))},
        {"title": "Checks on the finished model", "rows": check_rows(parameters)},
    ]
    winding = winding_rows(parameters)
    if winding:
        sections.append({"title": "Winding (not part of the CAD features)", "rows": winding})
    return sections


def flagged(sections):
    return [(s["title"], r["field"], r["note"]) for s in sections for r in s["rows"] if r["note"]]


def to_text(sections, heading=None):
    """Plain text with aligned columns, for the terminal."""
    width = max(len(r["field"]) for s in sections for r in s["rows"])
    out = [heading, "=" * len(heading)] if heading else []
    for section in sections:
        out += ["", section["title"], "-" * len(section["title"])]
        for r in section["rows"]:
            out.append(f"  {r['field']:<{width}}  {r['text']}" + (f"   <-- {r['note']}" if r["note"] else ""))
    return "\n".join(out)


def to_markdown(sections, heading=None, level=1):
    out = ["#" * level + " " + heading, ""] if heading else []
    for section in sections:
        out += ["#" * (level + 1) + " " + section["title"].replace('"', "`"), "",
                "| Field | Value | Note |", "|---|---|---|"]
        out += [f"| {r['field']} | {r['text']} | {r['note']} |" for r in section["rows"]]
        out.append("")
    return "\n".join(out)
