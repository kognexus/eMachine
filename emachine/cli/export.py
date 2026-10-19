"""
Field export of one design for ParaView.

    emachine export --run runs/opt1                      # best compromise of a run
    emachine export --run runs/opt1 --pick highest_torque --sectors 3
    emachine export --spec spec.json --design design.json --out runs/view1

The design is solved over one electrical period with the fields kept. Written to the output
folder (default <run>/post/<pick>/paraview):

    machine.pvd     solid parts, one step per rotor position: open this first
    air.pvd         air regions
    airgap.pvd      cylinder in the middle of the air gap with the radial flux density
    core_loss.vtu   stator core: peak flux density over the cycle and loss density
    full_ring.vtu   solid parts of the whole ring of one phase at the position of highest torque
    full_motor.vtu  the same for every phase, placed as in the machine
    waveforms.csv, harmonics.csv, airgap_profile.csv, regions.csv, waveforms.svg
    summary.md      key numbers, checks and how to use the files in ParaView
    open_in_paraview.py   builds the five standard views as tabs in the ParaView GUI
    paraview_views.py the view script it uses (also renders the views as pictures)
    efficiency_map.vtu, efficiency_limits.vtu, efficiency_map.csv, envelope.csv
                    with --map <folder of emachine map>: the efficiency map, for the fifth view

--refresh rewrites full_motor.vtu, the map files and the view scripts of an existing export without
solving again (needs --out, and --map for the map):

    emachine export --refresh --out runs/user_tr48/paraview --map runs/user_tr48/map

A radial flux machine (geometry rfm.section2d) is solved on its 2D cross-section with all phases;
the same files are written, the section extruded to the stack length (see analysis/section_export.py):

    emachine export --spec examples/rfm_spm_12s10p.json \
        --design examples/rfm_spm_12s10p_design.json --out runs/rfm_spm_12s10p/paraview --map runs/rfm_spm_12s10p/map

--sectors N repeats the sector N times in the time series (TFM only). --skip-no-load leaves out the second
sweep (no cogging torque, no induced voltage). --skip-air leaves out air.pvd.
"""

import argparse
import csv
import json
import os
import shutil
import sys
import time

import numpy as np

from emachine.analysis import fieldexport, section_export
from emachine.cli import describe
from emachine.io import paraview_files as paraviewfiles
from emachine.io import svg as svgplot
from emachine.machines.tfm.cad import sheet as onshape
from emachine.pipeline import design_space, picks

#: geometry kinds the export can read
EXPORTS = ("tfm.sector3d", "rfm.section2d", "rafm.quasi3d")
VIEWS_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "io", "paraview_views.py")

def write_csv(path, columns, rows):
    with open(path, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(columns)
        for row in rows:
            out.writerow(["" if v is None else (f"{v:.7g}" if isinstance(v, (float, np.floating)) else v) for v in row])


#: columns that a model may not have at all (the phase torque of an all-phase solution, the field
#: under a TFM leg): left out of waveforms.csv when absent; the others stay, empty when not computed
OPTIONAL_COLUMNS = ("phase_torque_Nm", "airgap_b_radial_under_leg_T")


def waveform_table(r):
    columns = ["step", "rotor_angle_deg", "electrical_angle_deg", "phase_current_A", "phase_torque_Nm",
               "machine_torque_Nm", "cogging_torque_Nm", "flux_linkage_Wb", "no_load_flux_linkage_Wb",
               "induced_voltage_V", "terminal_voltage_V", "airgap_b_radial_under_leg_T"]
    columns = [c for c in columns if not (c in OPTIONAL_COLUMNS and r.get(c) is None)]
    rows = []
    for k in range(r["steps"]):
        rows.append([k] + [None if r[c] is None else float(r[c][k]) for c in columns[1:]])
    return columns, rows


def harmonic_table(r):
    series = {"machine_torque_Nm": r["machine_torque_Nm"], "cogging_torque_Nm": r["cogging_torque_Nm"],
              "induced_voltage_V": r["induced_voltage_V"], "flux_linkage_Wb": r["flux_linkage_Wb"]}
    series = {name: fieldexport.harmonics(values) for name, values in series.items() if values is not None}
    orders = len(next(iter(series.values())))
    return ["order"] + list(series), [[k] + [series[name][k][1] for name in series] for k in range(orders)]


def draw(path, r):
    x = r["electrical_angle_deg"]
    charts = []
    c = svgplot.Chart((0, 360), _range(r["machine_torque_Nm"], r["phase_torque_Nm"], r["cogging_torque_Nm"]),
                      "Electrical angle (deg)", "Torque (Nm)", "Torque over one electrical period", 620, 330)
    c.line(x, r["machine_torque_Nm"], label="machine")
    if r["phases"] > 1 and r["phase_torque_Nm"] is not None:
        c.line(x, r["phase_torque_Nm"], label="one phase")
    if r["cogging_torque_Nm"] is not None:
        c.line(x, r["cogging_torque_Nm"], label="cogging (no load)")
    charts.append(c)
    c = svgplot.Chart((0, 360), _range(r["flux_linkage_Wb"], r["no_load_flux_linkage_Wb"]),
                      "Electrical angle (deg)", "Flux linkage (Wb)", "Flux linked by the phase coil", 620, 330)
    c.line(x, r["flux_linkage_Wb"], label="loaded")
    if r["no_load_flux_linkage_Wb"] is not None:
        c.line(x, r["no_load_flux_linkage_Wb"], label="no load")
    charts.append(c)
    c = svgplot.Chart((0, 360), _range(r["terminal_voltage_V"], r["induced_voltage_V"]),
                      "Electrical angle (deg)", "Voltage (V)", f"Phase voltage at {r['speed_rpm']:g} rpm", 620, 330)
    c.line(x, r["terminal_voltage_V"], label="terminal")
    if r["induced_voltage_V"] is not None:
        c.line(x, r["induced_voltage_V"], label="induced (no load)")
    charts.append(c)
    if r["profile"] is not None and section(r):
        theta, _, b = r["profile"]
        c = svgplot.Chart((0.0, 360.0), _range(b[0]), "Angle around the gap (deg)", "Radial flux density (T)",
                          f"Air-gap flux density ({r['profile_source']})", 620, 330)
        c.line(theta, b[0], label="middle of the gap")
        charts.append(c)
    elif r["profile"] is not None:
        theta, z, b = r["profile"]
        rows = [int(np.argmin(np.abs(z - s * r["leg_z_mm"]))) for s in (1, -1)]
        c = svgplot.Chart((float(theta[0]), float(theta[-1])), _range(b[rows[0]], b[rows[1]]),
                          "Angle around the gap (deg), one pole pair", "Radial flux density (T)",
                          f"Air-gap flux density ({r['profile_source']})", 620, 330)
        c.line(theta, b[rows[0]], label="under leg 1")
        c.line(theta, b[rows[1]], label="under leg 2")
        charts.append(c)
    svgplot.save(path, charts, columns=2)


def section(r):
    """True for an export of a 2D cross-section (all phases in one solution)."""
    return r.get("model") == "section2d"


def _range(*series):
    values = np.concatenate([np.asarray(s, dtype=float) for s in series if s is not None])
    low, high = float(values.min()), float(values.max())
    pad = 0.08 * (high - low) or 1e-6
    return (min(low - pad, 0.0) if low >= 0 else low - pad, high + pad)


def write_summary(path, spec, r, columns_h, rows_h):
    tm, iron, heat = r["torque"], r["iron"], r["thermal"]
    core = spec["materials"]["stator_core"]
    linear = core["saturation_T"] is None and core["bh_curve"] is None
    out = ["# Field export for ParaView", "",
           "![Waveforms](waveforms.svg)", "",
           "## Key numbers", "",
           "| Quantity | Value |", "|---|---|",
           f"| Operating point | {r['speed_rpm']:g} rpm, {r['ampere_turns_peak']:.0f} ampere-turns peak "
           f"({r['ampere_turns_peak'] / r['turns']:.2f} A peak with {r['turns']} turns) |",
           f"| Winding | {r.get('winding_text', '')} |",
           f"| Mean torque | {tm['mean']:.4f} Nm |",
           f"| Torque ripple (peak to peak / mean) | {tm['ripple']:.2f} |",
           f"| Torque minimum, maximum | {float(np.min(r['machine_torque_Nm'])):.4f} Nm, {float(np.max(r['machine_torque_Nm'])):.4f} Nm |"]
    if r["cogging_torque_Nm"] is not None:
        cog = r["cogging_torque_Nm"]
        out += [f"| Cogging torque, peak to peak | {float(cog.max() - cog.min()):.4f} Nm |",
                f"| Induced voltage, peak | {float(np.max(np.abs(r['induced_voltage_V']))):.2f} V |"]
    out += [f"| Terminal voltage, peak | {float(np.max(np.abs(r['terminal_voltage_V']))):.2f} V |",
            f"| Flux linkage, peak | {float(np.max(np.abs(r['flux_linkage_Wb']))):.5f} Wb |",
            f"| Phase resistance at {heat['winding_C']:.0f} C | {onshape.resistance_text(r['resistance_ohm'])} |",
            f"| Stator iron loss per phase | {iron['iron_loss_W']:.3f} W |",
            f"| Rotor eddy-current loss per phase (iron, housing, magnets) | {iron.get('rotor_loss_W', 0.0):.3f} W |",
            f"| Copper loss per phase | {heat['copper_loss_W']:.3f} W |",
            f"| Winding, magnet temperature | {heat['winding_C']:.1f} C, {heat['magnet_C']:.1f} C |", "",
            "## Checks", "",
            "| Check | Value | Meaning |", "|---|---|---|",
            f"| Core flux density on 95 % of the volume, peak over the cycle | {iron['core_b_p95_T']:.2f} T | "
            f"highest local value {iron['core_b_max_T']:.2f} T |"]
    if not linear:
        out.append(f"| Share of the stator core above 80 % of saturation | {100 * max(r['saturated_core_share']):.1f} % "
                   f"at the worst step | colour by `saturation` to see where |")
    out += [f"| Lowest flux density along the magnetisation in any magnet element | {r['magnet_min_T']:.2f} T | "
            "demagnetisation risk if below the knee of the magnet grade at its temperature |",
            f"| Magnet volume below 0.3 T, below 0 T (all steps) | {100 * r['magnet_share_below_0p3T']:.1f} %, "
            f"{100 * r['magnet_share_below_0T']:.1f} % | the knee of N42 is roughly 0 to 0.3 T at 80 to 100 C; "
            "check the data sheet |", ""]
    top = sorted(rows_h[1:], key=lambda row: -row[1])[:5]
    out += ["## Largest torque harmonics", "",
            "Order 1 is the electrical frequency. Mean torque is order 0.", "",
            "| Order | Amplitude (Nm) | Share of mean |", "|---|---|---|"]
    out += [f"| {row[0]} | {row[1]:.4f} | {100 * row[1] / max(rows_h[0][1], 1e-12):.1f} % |" for row in top]
    out += _section_guide(r) if section(r) else _tfm_guide(r)
    with open(path, "w") as f:
        f.write("\n".join(out))


def _tfm_guide(r):
    """Files, data and ParaView steps of the export of a TFM sector."""
    return ["", "## Files", "",
            "| File | Content |", "|---|---|",
            f"| `machine.pvd` | solid parts, {r['steps']} steps over one electrical period"
            + (f", {r['sectors']} sectors" if r["sectors"] > 1 else ", one sector (one pole pair)") + " |",
            "| `air.pvd` | air regions, same steps |",
            "| `airgap.pvd` | cylinder in the middle of the air gap |",
            "| `core_loss.vtu` | stator core: `B_peak` and loss density |",
            "| `full_ring.vtu` | solid parts of the whole ring at the step of highest torque |",
            "| `waveforms.csv` | torque, current, flux and voltage per step |",
            "| `harmonics.csv` | harmonic amplitudes of torque, cogging torque, induced voltage, flux |",
            "| `airgap_profile.csv` | radial flux density around the gap under each leg |",
            "| `regions.csv` | meaning of the `region` and `material` numbers |", "",
            "The time value of a step is the electrical angle in degrees. Lengths are in millimetres, flux "
            "density in tesla, vector potential in Wb/m, magnetisation in A/m, current density in A/mm2.", "",
            "## Data on the field files", "",
            "| Name | On | Meaning |", "|---|---|---|",
            "| `B`, `B_magnitude` | points | flux density vector and magnitude |",
            "| `B_radial`, `B_tangential`, `B_axial` | points | cylindrical components |",
            "| `A` | points | vector potential |",
            "| `region` | cells | part number of step 0, see `regions.csv`. Magnets that cross the sector "
            "boundary are numbered differently in other steps; use `material` for selections over time |",
            "| `material` | cells | 1 air, 2 copper, 3 magnet, 4 stator core, 5 rotor iron, 6 rotor housing |",
            "| `side` | cells | 0 stator, 1 rotor |",
            "| `B_cell` | cells | flux density of the element |",
            "| `mu_r` | cells | relative permeability at the working point |",
            "| `saturation` | cells | polarisation / saturation polarisation, 0 to 1 (0 for linear materials) |",
            "| `magnetization` | cells | magnetisation vector of the magnets, zero elsewhere |",
            "| `B_along_magnetization` | cells | magnet working point, zero outside the magnets |",
            "| `current_density` | cells | coil current density vector, zero outside the coil |", "",
            "Every file of a step also carries the step values `rotor_angle_deg`, `electrical_angle_deg`, "
            "`phase_current_A`, `torque_Nm`, `machine_torque_Nm` and `flux_linkage_Wb` as field data.", "",
            "## In ParaView", "",
            "1. File > Open > `machine.pvd`, Apply. Colour by `B_magnitude`. Play steps through the rotor positions.",
            "2. Vector map: select `machine.pvd`, Filters > Glyph. Glyph Type Arrow, Orientation Array `B`, "
            "Scale Array `B`, Glyph Mode \"Every Nth Point\". Lower the scale factor until the arrows fit.",
            "3. Magnet pattern: Filters > Threshold on `material` from 3 to 3, then Glyph with Orientation Array "
            "`magnetization` (switch the glyph input to cell centres with Filters > Cell Centers first).",
            "4. Saturation: colour `machine.pvd` by `saturation` or `mu_r`.",
            "5. Demagnetisation: Threshold `material` 3 to 3, colour by `B_along_magnetization`.",
            "6. Air-gap field: open `airgap.pvd`, colour by `B_radial`.",
            "7. Field in the air: open `air.pvd`, Filters > Slice, or Stream Tracer on `B`.",
            "8. Loss hot spots: open `core_loss.vtu`, colour by `loss_density_W_per_kg`.",
            "9. Torque against rotor angle: open `waveforms.csv`, Apply, then Filters > Plot Data with "
            "`electrical_angle_deg` as the X array.",
            "10. More sectors without re-running: Filters > Transform with a rotation about Z of "
            f"{360.0 / r['pole_pairs']:.4f} degrees per copy, or run this command with `--sectors N`.", "",
            "`open_in_paraview.py` builds the five standard views as tabs (View > Python Shell > Run Script): "
            "full motor (`full_motor.vtu`), field per material, mesh, torque against electrical angle and, "
            "when the export was made with `--map`, the efficiency map (`efficiency_map.vtu`). "
            "Tested with ParaView 6.2.", "",
            "## Limits", "",
            "- One sector is one pole pair of one phase. Phases are treated as magnetically independent.",
            "- Magnetostatic solution at each rotor position: no eddy currents.",
            "- The flux density is the element field averaged to the mesh points inside each part. It jumps "
            "at material boundaries, as it should.",
            "- Loss density uses the loss coefficients of the specification, which are assumptions unless "
            "replaced by data-sheet values.", ""]

def _section_guide(r):
    """Files, data and ParaView steps of the export of a 2D cross-section."""
    return ["", "## Files", "",
            "| File | Content |", "|---|---|",
            f"| `machine.pvd` | solid parts of the whole cross-section, {r['steps']} steps over one electrical period, "
            f"extruded to the stack length ({r['stack_length_mm']:g} mm) |",
            "| `air.pvd` | air regions (air gap, between the magnets, shaft), same steps |",
            "| `airgap.pvd` | cylinder in the middle of the air gap, sampled every 0.5 degrees |",
            "| `core_loss.vtu` | stator core: `B_peak` and loss density |",
            "| `full_ring.vtu`, `full_motor.vtu` | the whole machine at the step of highest torque |",
            "| `waveforms.csv` | machine torque, current, flux and voltage of phase 1 per step |",
            "| `harmonics.csv` | harmonic amplitudes of torque, cogging torque, induced voltage, flux |",
            "| `airgap_profile.csv` | radial flux density around the middle of the gap |",
            "| `regions.csv` | meaning of the `region` and `material` numbers |", "",
            "The time value of a step is the electrical angle in degrees. Lengths are in millimetres, flux "
            "density in tesla, vector potential in Wb/m, magnetisation in A/m, current density in A/mm2. The "
            "solution is two-dimensional: the fields do not change along the stack (z), and end effects are "
            "not included.", "",
            "## Data on the field files", "",
            "| Name | On | Meaning |", "|---|---|---|",
            "| `B`, `B_magnitude` | points | flux density vector and magnitude (element values averaged at the points) |",
            "| `B_radial`, `B_tangential` | points | cylindrical components |",
            "| `A_z` | points | vector potential; its contour lines are the flux lines |",
            "| `region` | cells | part number, see `regions.csv` |",
            "| `material` | cells | 1 air, 2 copper, 3 magnet, 4 stator core, 5 rotor iron |",
            "| `side` | cells | 0 stator, 1 rotor |",
            "| `phase` | cells | phase of a coil side, 1 to %d; 0 elsewhere |" % r["phases"],
            "| `B_cell` | cells | flux density of the element |",
            "| `mu_r` | cells | relative permeability at the working point |",
            "| `saturation` | cells | polarisation / saturation polarisation, 0 to 1 (0 for linear materials) |",
            "| `magnetization` | cells | magnetisation vector of the magnets, zero elsewhere |",
            "| `B_along_magnetization` | cells | magnet working point, zero outside the magnets |",
            "| `current_density` | cells | current density along z in A/mm2, zero outside the coil sides |", "",
            "Every file of a step also carries the step values `rotor_angle_deg`, `electrical_angle_deg`, "
            "`phase_current_A` (phase 1), `torque_Nm`, `machine_torque_Nm` and `flux_linkage_Wb` (phase 1) as field data.", "",
            "## In ParaView", "",
            "1. File > Open > `machine.pvd`, Apply. Colour by `B_magnitude`. Play steps through the rotor positions.",
            "2. Flux lines: open `machine.pvd` and `air.pvd`, select both, Filters > Append Datasets, then "
            "Filters > Slice (Z normal), then Filters > Contour by `A_z` with about 30 values.",
            "3. Vector map: Filters > Glyph on `machine.pvd`, Orientation Array `B`, Scale Array `B`.",
            "4. Phases: colour `machine.pvd` by `phase`, or by `current_density` (Z) to see the current of each step.",
            "5. Saturation: colour by `saturation` or `mu_r`. Demagnetisation: Threshold `material` 3 to 3, "
            "colour by `B_along_magnetization`.",
            "6. Air-gap field: open `airgap.pvd`, colour by `B_radial`.",
            "7. Loss hot spots: open `core_loss.vtu`, colour by `loss_density_W_per_kg`.",
            "8. Torque against rotor angle: open `waveforms.csv`, Apply, then Filters > Plot Data with "
            "`electrical_angle_deg` as the X array.", "",
            "`open_in_paraview.py` builds the five standard views as tabs (View > Python Shell > Run Script): "
            "full motor, field per material with flux lines, mesh, torque against electrical angle and, when the "
            "export was made with `--map`, the efficiency map. Tested with ParaView 6.2.", "",
            "## Limits", "",
            "- Two-dimensional magnetostatic solution at each rotor position: no end effects, no eddy currents in "
            "the field (rotor eddy-current loss is estimated afterwards from the field).",
            "- The mesh is made again at every rotor position; `region` numbers are the same in every step.",
            "- Loss density uses the loss coefficients of the specification, which are assumptions unless "
            "replaced by data-sheet values.", ""]


def finish(outdir, mapdir=None):
    """Files for the five views: the whole motor, the efficiency map (with a map folder), the view scripts."""
    print("Full motor ->", paraviewfiles.full_motor(outdir), flush=True)
    if mapdir:
        for name in ("efficiency_map.csv", "envelope.csv"):
            if not os.path.isfile(os.path.join(mapdir, name)):
                sys.exit(f"{mapdir} has no {name}: run `emachine map` first.")
        paraviewfiles.efficiency_map(mapdir, outdir)
        for name in ("efficiency_map.csv", "envelope.csv"):
            shutil.copy(os.path.join(mapdir, name), os.path.join(outdir, name))
        print("Efficiency map ->", os.path.join(outdir, "efficiency_map.vtu"))
    else:
        print("No --map: the fifth view (efficiency map) is left out until --refresh --map <folder>.")
    print("Views ->", paraviewfiles.write_open_script(outdir, VIEWS_SCRIPT))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    picks.add_arguments(ap)
    ap.add_argument("--sectors", type=int, default=1, help="copies of the sector in the time series (default 1)")
    ap.add_argument("--turns", type=int, help="turns per phase coil (default: as chosen by the optimizer)")
    ap.add_argument("--skip-no-load", action="store_true", help="no second sweep without current")
    ap.add_argument("--skip-air", action="store_true", help="do not write the air regions")
    ap.add_argument("--keep-raw", action="store_true", help="keep the solver folders of every rotor position")
    ap.add_argument("--map", help="folder of emachine map: its efficiency map is added to the export")
    ap.add_argument("--refresh", action="store_true",
                    help="only rewrite full_motor.vtu, the map files and the view scripts of the export in --out")
    args = ap.parse_args(argv)
    if args.refresh:
        if not args.out or not os.path.isfile(os.path.join(args.out, "summary.json")):
            sys.exit("--refresh needs --out with an existing export (summary.json).")
        finish(args.out, args.map)
        return
    try:
        spec, values, parameters, outdir = picks.load(args, "paraview")
        kind = design_space.geometry(spec, values).kind
    except (picks.PickError, ValueError) as error:
        sys.exit(str(error))
    except NotImplementedError as error:              # a machine without a geometry yet
        sys.exit(f"No ParaView export: {error}")
    if kind not in EXPORTS:
        sys.exit(f"The ParaView export has no reader for the geometry {kind!r} of "
                 f"{spec['machine']['flux_path']}/{spec['machine']['principle']} yet.")
    began = time.time()
    turns = args.turns or picks.turns_of(parameters)
    try:
        if kind in ("rfm.section2d", "rafm.quasi3d"):
            if args.sectors > 1:
                print("--sectors is ignored: the cross-section is the whole machine.")
            r = section_export.export(spec, values, outdir, turns, not args.skip_no_load, args.skip_air, args.keep_raw)
        else:
            r = fieldexport.export(spec, values, outdir, turns, max(1, args.sectors), not args.skip_no_load,
                                   args.skip_air, args.keep_raw)
    except fieldexport.ExportError as error:
        sys.exit(str(error))

    columns, rows = waveform_table(r)
    write_csv(os.path.join(outdir, "waveforms.csv"), columns, rows)
    columns_h, rows_h = harmonic_table(r)
    write_csv(os.path.join(outdir, "harmonics.csv"), columns_h, rows_h)
    write_csv(os.path.join(outdir, "regions.csv"), ["region", "name", "material_id", "material", "side", "kind"],
              ([g[c] for c in ("region", "name", "material_id", "material", "side", "kind")] for g in r["regions"]))
    if r["profile"] is not None and section(r):
        theta, _, b = r["profile"]
        write_csv(os.path.join(outdir, "airgap_profile.csv"), ["theta_deg", "b_radial_T"], zip(theta.tolist(), b[0].tolist()))
    elif r["profile"] is not None:
        theta, z, b = r["profile"]
        index = [int(np.argmin(np.abs(z - s * r["leg_z_mm"]))) for s in (1, -1)]
        write_csv(os.path.join(outdir, "airgap_profile.csv"),
                  ["theta_deg", "b_radial_leg1_T", "b_radial_leg2_T", "b_radial_mean_over_length_T"],
                  zip(theta.tolist(), b[index[0]].tolist(), b[index[1]].tolist(), b.mean(axis=0).tolist()))
    draw(os.path.join(outdir, "waveforms.svg"), r)
    r["winding_text"] = describe.winding_text(spec, values)
    write_summary(os.path.join(outdir, "summary.md"), spec, r, columns_h, rows_h)
    keep = {k: v for k, v in r.items() if k not in ("profile", "regions")}
    with open(os.path.join(outdir, "summary.json"), "w") as f:
        json.dump(keep, f, indent=1, default=lambda v: v.tolist() if isinstance(v, np.ndarray) else float(v))
    finish(outdir, args.map)

    tm = r["torque"]
    print(f"Mean torque {tm['mean']:.4f} Nm, ripple {tm['ripple']:.2f}, iron loss {r['iron']['iron_loss_W']:.3f} W, "
          f"rotor loss {r['iron'].get('rotor_loss_W', 0.0):.3f} W per phase, "
          f"lowest magnet working point {r['magnet_min_T']:.2f} T")
    print(f"{r['steps']} steps, {r['elements']} elements {'in the section' if section(r) else 'per sector'}. Open {os.path.join(outdir, 'machine.pvd')} in ParaView; "
          f"see {os.path.join(outdir, 'summary.md')}   ({time.time() - began:.0f} s)")

