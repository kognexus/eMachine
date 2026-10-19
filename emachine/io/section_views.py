"""
The five standard views of a topology export (T75), with ParaView's own Python:

    GUI:       View > Python Shell > Run Script, open_in_paraview.py of the export folder (one tab per view)
    Pictures:  pvpython --force-offscreen-rendering section_views.py --export <export folder> --out <folder>
    Check:     python section_views.py --export <export folder> --check      (no ParaView needed)

    1 Full 3D material geometry   machine_3d.vtu: the section extruded to the stack length, quarter cut away
    2 Gmsh section mesh           first rated position: elements with their edges, coloured by material
    3 Elmer EM result             rated.pvd: |B| with flux lines (contours of A_z), animated over the rotor positions
    4 Torque and torque ripple    torque.csv: torque over the electrical angle, its mean, ripple in the title
    5 Back-EMF                    back_emf.csv: no-load EMF of phases A, B, C over one electrical period

The files are written by `python -m emachine.analysis.topology_export` (with `--refresh` for an older export).
Uses only paraview.simple and the standard library, so that it runs in ParaView's Python.
"""

import argparse
import csv
import json
import math
import os
import sys

RESOLUTION = [1600, 1200]
INTERACTIVE = False         # --interactive: views go into tabs of the GUI, no pictures

#: material code of the export (cell array "material") -> (label, colour)
MATERIALS = {
    1: ("Stator core", (0.60, 0.63, 0.67)),
    2: ("Rotor core", (0.33, 0.34, 0.37)),
    3: ("Magnet (towards the gap / counter-clockwise)", (0.80, 0.16, 0.20)),
    7: ("Magnet (away from the gap / clockwise)", (0.16, 0.36, 0.78)),
    4: ("Coil phase A", (0.93, 0.55, 0.13)),
    5: ("Coil phase B", (0.20, 0.62, 0.30)),
    6: ("Coil phase C", (0.55, 0.30, 0.65)),
}
PHASE_COLOURS = {"emf_a_V": (0.93, 0.55, 0.13), "emf_b_V": (0.20, 0.62, 0.30), "emf_c_V": (0.55, 0.30, 0.65)}


# ----------------------------------------------------------------------------- inputs (no ParaView)

def load_summary(export):
    with open(os.path.join(export, "summary.json")) as f:
        return json.load(f)


def csv_columns(path):
    with open(path) as f:
        return next(csv.reader(f))


def check_inputs(export):
    """List of problems with the files the views need (empty: all there)."""
    problems = []
    if not os.path.isfile(os.path.join(export, "summary.json")):
        return ["summary.json is missing: not a topology export"]
    summary = load_summary(export)
    needed = {"rated.pvd": None, "torque.csv": ["angle_el_deg", "torque_Nm", "mean_Nm"],
              "back_emf.csv": ["angle_el_deg", "emf_a_V", "emf_b_V", "emf_c_V"]}
    if summary.get("kind", "radial") == "radial":
        needed["machine_3d.vtu"] = None
    for name, columns in needed.items():
        path = os.path.join(export, name)
        if not os.path.isfile(path):
            problems.append(f"{name} is missing (run topology_export --refresh)")
        elif columns and not set(columns) <= set(csv_columns(path)):
            problems.append(f"{name} lacks the columns {sorted(set(columns) - set(csv_columns(path)))}")
    if os.path.isfile(os.path.join(export, "rated.pvd")):
        with open(os.path.join(export, "rated.pvd")) as f:
            text = f.read()
        for name in [part.split('"')[0] for part in text.split('file="')[1:]]:
            if not os.path.isfile(os.path.join(export, name)):
                problems.append(f"{name} (listed in rated.pvd) is missing")
    return problems


# ----------------------------------------------------------------------------- ParaView helpers

def in_tab(view, title):
    if not INTERACTIVE:
        return
    try:
        from paraview.simple import AssignViewToLayout, CreateLayout
        AssignViewToLayout(view=view, layout=CreateLayout(title), hint=0)
    except Exception as error:          # older ParaView: the view stays in the current layout
        print("No tab for", title, ":", error)


def new_render_view(title):
    from paraview.simple import CreateView
    view = CreateView("RenderView")
    in_tab(view, title)
    if not INTERACTIVE:
        view.ViewSize = RESOLUTION
    view.Background = [1.0, 1.0, 1.0]
    try:
        view.UseColorPaletteForBackground = 0
    except Exception:
        pass
    view.OrientationAxesVisibility = 0
    return view


def new_chart(title):
    from paraview.simple import CreateView
    chart = CreateView("XYChartView")
    in_tab(chart, title)
    if not INTERACTIVE:
        chart.ViewSize = RESOLUTION
    return chart


def save(view, out, name):
    from paraview.simple import Render, SaveScreenshot
    Render(view)
    if INTERACTIVE:
        return
    path = os.path.join(out, name)
    SaveScreenshot(path, view, ImageResolution=RESOLUTION)
    print("  ->", path)


def threshold(source, material):
    from paraview.simple import Threshold
    th = Threshold(Input=source)
    th.Scalars = ["CELLS", "material"]
    try:                                    # ParaView 5.10 and later
        th.LowerThreshold, th.UpperThreshold = material - 0.5, material + 0.5
        th.ThresholdMethod = "Between"
    except AttributeError:                  # ParaView 5.9
        th.ThresholdRange = [material - 0.5, material + 0.5]
    return th


def material_parts(source):
    """(material code, threshold) of every solid material present (air left out)."""
    from paraview.simple import Delete
    parts = []
    for material in MATERIALS:
        part = threshold(source, material)
        part.UpdatePipeline()
        if part.GetDataInformation().GetNumberOfCells() > 0:
            parts.append((material, part))
        else:
            Delete(part)
    return parts


def solid_colour(display, rgb):
    """One colour, no colour map (ColorBy(display, None) fails in ParaView 6.2)."""
    try:
        display.ColorArrayName = ["POINTS", ""]
    except Exception:
        try:
            from paraview.simple import ColorBy
            ColorBy(display, None)
        except Exception:
            pass
    display.AmbientColor = list(rgb)
    display.DiffuseColor = list(rgb)


def number_format(digits):
    """Label format of a scalar bar: std::format from ParaView 6.1 on, printf before."""
    try:
        from paraview.simple import GetParaViewVersion
        version = GetParaViewVersion()
        if (version.major, version.minor) >= (6, 1):
            return "{:.%df}" % digits
    except Exception:
        pass
    return "%%.%df" % digits


def text_label(view, text, position="Upper Left Corner"):
    from paraview.simple import Show, Text
    label = Text(Text=text)
    display = Show(label, view)
    try:
        display.WindowLocation = position
    except Exception:
        display.WindowLocation = position.replace(" ", "")
    display.Color = [0.1, 0.1, 0.1]
    display.FontSize = 14
    try:
        display.Justification = "Left"
    except Exception:
        pass


COLOUR_NAMES = {1: "light grey", 2: "dark grey", 3: "red", 7: "blue", 4: "orange", 5: "green", 6: "purple"}


def legend(present):
    """One line naming the colour of each material shown, e.g. "Stator core: light grey"."""
    names = {3: "Magnet N", 7: "Magnet S"}
    return "   ".join("%s: %s" % (names.get(m, MATERIALS[m][0]), COLOUR_NAMES[m]) for m in MATERIALS if m in present)


def top_camera(view, radius):
    view.CameraParallelProjection = 1
    view.CameraFocalPoint = [0.0, 0.0, 0.0]
    view.CameraPosition = [0.0, 0.0, 20.0 * radius]
    view.CameraViewUp = [0.0, 1.0, 0.0]
    view.CameraParallelScale = 1.08 * radius


def bounds_radius(source):
    source.UpdatePipeline()
    b = source.GetDataInformation().GetBounds()
    return max(abs(b[0]), abs(b[1]), abs(b[2]), abs(b[3])), b


def title_of(summary):
    return "%s (%s)" % (summary.get("machine", "machine"), summary.get("pick", ""))


# ----------------------------------------------------------------------------- the five views

def view_geometry_3d(export, summary, out):
    """1: the section extruded to the stack length, solid colours per material, a quarter cut away."""
    from paraview.simple import Clip, Show, XMLUnstructuredGridReader
    path = os.path.join(export, "machine_3d.vtu")
    if not os.path.isfile(path):
        print("  no machine_3d.vtu: view 1 left out (refresh the export with the stack length)")
        return
    reader = XMLUnstructuredGridReader(FileName=[path])
    view = new_render_view("1 Geometry 3D")
    radius, b = bounds_radius(reader)
    present = []
    for material, part in material_parts(reader):
        cut = Clip(Input=part)                       # remove the quarter x > 0, y < 0 that faces the camera
        cut.ClipType = "Box"
        size = 10.0 * radius
        cut.ClipType.Position = [0.0, -size, -size]
        cut.ClipType.Length = [size, size, 2 * size]
        try:
            cut.Invert = 0
        except Exception:
            pass
        solid_colour(Show(cut, view), MATERIALS[material][1])
        present.append(material)
    distance = 2.6 * radius
    view.CameraFocalPoint = [0.0, 0.0, 0.0]
    view.CameraPosition = [distance, -1.2 * distance, 1.1 * distance]
    view.CameraViewUp = [0.0, 0.0, 1.0]
    text_label(view, "%s: material geometry, stack %.1f mm (section extruded), quarter cut away\n%s"
               % (title_of(summary), b[5] - b[4], legend(present)))
    save(view, out, "1_geometry_3d.png")


def first_rated_file(export):
    with open(os.path.join(export, "rated.pvd")) as f:
        return os.path.join(export, f.read().split('file="')[1].split('"')[0])


def view_section_mesh(export, summary, out):
    """2: the Gmsh mesh of the first rated position, element edges on, coloured by material."""
    from paraview.simple import Show, XMLUnstructuredGridReader
    reader = XMLUnstructuredGridReader(FileName=[first_rated_file(export)])
    view = new_render_view("2 Section mesh")
    radius, _ = bounds_radius(reader)
    present = []
    air = threshold(reader, 0)
    display = Show(air, view)
    display.SetRepresentationType("Surface With Edges")
    solid_colour(display, (0.97, 0.97, 0.97))
    display.EdgeColor = [0.55, 0.55, 0.55]
    for material, part in material_parts(reader):
        display = Show(part, view)
        display.SetRepresentationType("Surface With Edges")
        solid_colour(display, MATERIALS[material][1])
        display.EdgeColor = [0.1, 0.1, 0.1]
        present.append(material)
    top_camera(view, radius)
    reader.UpdatePipeline()
    cells = reader.GetDataInformation().GetNumberOfCells()
    text_label(view, "%s: Gmsh section mesh, %d triangles (zoom into the air gap for its layers)\n%s"
               % (title_of(summary), cells, legend(present)))
    save(view, out, "2_section_mesh.png")


def view_em_field(export, summary, out):
    """3: |B| of the rated sweep with flux lines; the time is the electrical angle (animate over it)."""
    from paraview.simple import (ColorBy, Contour, GetAnimationScene, GetColorTransferFunction, GetScalarBar,
                                 PVDReader, Show)
    reader = PVDReader(FileName=os.path.join(export, "rated.pvd"))
    view = new_render_view("3 EM field")
    radius, _ = bounds_radius(reader)
    display = Show(reader, view)
    ColorBy(display, ("CELLS", "B_mag"))
    lut = GetColorTransferFunction("B_mag")
    for preset in ("Turbo", "Jet", "Rainbow Uniform"):
        try:
            if lut.ApplyPreset(preset, True):
                break
        except Exception:
            pass
    lut.RescaleTransferFunction(0.0, 2.2)
    bar = GetScalarBar(lut, view)
    bar.Title = "|B| (T)"
    bar.ComponentTitle = ""
    bar.TitleColor = bar.LabelColor = [0.1, 0.1, 0.1]
    try:
        bar.RangeLabelFormat = bar.LabelFormat = number_format(2)
        bar.AutomaticLabelFormat = 0
    except Exception:
        pass
    display.SetScalarBarVisibility(view, True)
    lines = Contour(Input=reader)
    lines.ContourBy = ["POINTS", "A_z"]
    reader.UpdatePipeline()
    low, high = reader.PointData["A_z"].GetRange()
    levels = 24
    step = (high - low) / (levels + 1)
    lines.Isosurfaces = [low + step * (k + 1) for k in range(levels)]
    line_display = Show(lines, view)
    solid_colour(line_display, (0.05, 0.05, 0.05))
    line_display.LineWidth = 1.0
    try:
        GetAnimationScene().UpdateAnimationUsingDataTimeSteps()
    except Exception:
        pass
    top_camera(view, radius)
    text_label(view, "%s: Elmer magnetostatic solution at the rated current, flux density and flux lines\n"
                     "time = electrical angle in degrees: play the animation to turn the rotor" % title_of(summary))
    save(view, out, "3_em_field.png")


def line_chart(path, x, series, title, left, bottom, tab, picture, out, colours=None, labels=None, widths=None,
               x_range=None):
    from paraview.simple import CSVReader, Show
    table = CSVReader(FileName=[path])
    chart = new_chart(tab)
    display = Show(table, chart)
    display.UseIndexForXAxis = 0
    display.XArrayName = x
    display.SeriesVisibility = list(series)
    try:
        if labels:
            display.SeriesLabel = [v for s in series for v in (s, labels[s])]
        if colours:
            display.SeriesColor = [v for s in series for v in [s] + ["%g" % c for c in colours[s]]]
        if widths:
            display.SeriesLineThickness = [v for s in series for v in (s, str(widths[s]))]
    except Exception:
        pass
    chart.ChartTitle = title
    chart.LeftAxisTitle = left
    chart.BottomAxisTitle = bottom
    if x_range:
        try:
            chart.BottomAxisUseCustomRange = 1
            chart.BottomAxisRangeMinimum, chart.BottomAxisRangeMaximum = x_range
        except Exception:
            pass
    save(chart, out, picture)


def read_columns(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return {k: [float(r[k]) for r in rows] for k in rows[0]} if rows else {}


def view_torque(export, summary, out):
    """4: rated torque over the electrical angle with its mean; ripple = (max - min) / mean in the title."""
    path = os.path.join(export, "torque.csv")
    data = read_columns(path)
    torque = data["torque_Nm"]
    mean = data["mean_Nm"][0]
    ripple = 100.0 * (max(torque) - min(torque)) / mean if mean else float("nan")
    line_chart(path, "angle_el_deg", ["torque_Nm", "mean_Nm"],
                       "%s: torque at the rated current, mean %.3f N m, ripple %.1f %% (max %.3f, min %.3f N m)"
                       % (title_of(summary), mean, ripple, max(torque), min(torque)),
                       "Torque (N m)", "Electrical angle (deg)", "4 Torque and ripple", "4_torque.png", out,
                       colours={"torque_Nm": (0.1, 0.2, 0.6), "mean_Nm": (0.5, 0.5, 0.5)},
                       labels={"torque_Nm": "Torque", "mean_Nm": "Mean"},
                       widths={"torque_Nm": 3, "mean_Nm": 1})


def view_back_emf(export, summary, out):
    """5: no-load EMF of the three phases over one electrical period."""
    path = os.path.join(export, "back_emf.csv")
    data = read_columns(path)
    peak = max(abs(v) for k in PHASE_COLOURS for v in data[k])
    rms = math.sqrt(sum(v * v for v in data["emf_a_V"]) / len(data["emf_a_V"]))
    line_chart(path, "angle_el_deg", list(PHASE_COLOURS),
                       "%s: back-EMF at the rated speed (no load), phase peak %.2f V, rms %.2f V"
                       % (title_of(summary), peak, rms),
                       "Phase EMF (V)", "Electrical angle (deg)", "5 Back-EMF", "5_back_emf.png", out,
                       colours=PHASE_COLOURS, labels={"emf_a_V": "Phase A", "emf_b_V": "Phase B", "emf_c_V": "Phase C"},
                       widths={k: 3 for k in PHASE_COLOURS}, x_range=(0.0, 360.0))


VIEWS = (view_geometry_3d, view_section_mesh, view_em_field, view_torque, view_back_emf)


def main(argv=None):
    global INTERACTIVE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", required=True, help="folder written by emachine.analysis.topology_export")
    ap.add_argument("--out", default=None, help="folder for the pictures (default: <export>/views)")
    ap.add_argument("--interactive", action="store_true", help="build the views as tabs in the GUI, no pictures")
    ap.add_argument("--check", action="store_true", help="only check that the inputs are there (no ParaView)")
    args = ap.parse_args(argv)
    export = os.path.abspath(args.export)
    problems = check_inputs(export)
    if args.check or problems:
        for problem in problems:
            print("missing:", problem)
        if not problems:
            print("all inputs of the five views are there:", export)
        return 1 if problems else 0
    INTERACTIVE = args.interactive
    out = os.path.abspath(args.out or os.path.join(export, "views"))
    if not INTERACTIVE:
        os.makedirs(out, exist_ok=True)
    summary = load_summary(export)
    failed = []
    for view in VIEWS:
        try:
            view(export, summary, out)
        except Exception as error:                  # one failing view must not stop the others
            import traceback
            traceback.print_exc()
            failed.append("%s: %s" % (view.__name__, error))
    for message in failed:
        print("failed:", message)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
