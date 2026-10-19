#!/usr/bin/env pvpython
"""
Five standard views of a machine design in ParaView: as tabs in the GUI, or as pictures. Works for
the export of a TFM sector and for the export of a 2D cross-section (radial flux machine, summary
key "model" = "section2d"): the section is shown from the top, with flux lines.

    In the GUI: run open_in_paraview.py of the export folder (View > Python Shell > Run Script);
                it calls this script with --interactive, one tab per view.
    Pictures:   pvpython paraview_views.py --export runs/user_tr48/paraview --map runs/user_tr48/map \\
                    --out runs/user_tr48/views
                pvpython --force-offscreen-rendering paraview_views.py ...     (no window)

Input: the folder written by emachine export (--export: summary.json, full_motor.vtu, machine.pvd,
waveforms.csv) and the folder with efficiency_map.vtu and efficiency_limits.vtu (--map: written by
emachine map, and copied into the export by emachine export --map). Older folders get these files with
    emachine export --refresh --out <export> --map <map folder>
Output (PNG, 1600 x 1200, unless --interactive):

    1_full_motor.png        the whole machine, all phases, one quarter cut away, coloured by material
    2_segment_field.png     the solid parts of the exported sector at the position of highest torque,
                            |B| with one colour map per material: blue stator core, orange copper,
                            purple magnets, green rotor iron or housing (a section: seen from the
                            top, with the flux lines)
    3_mesh.png              the Gmsh mesh of the sector: solid parts with element edges, the air cut
                            open at the axial mid-plane to show the tetrahedra (a section: the
                            triangles near the bore, from the top)
    4_torque_vs_angle.png   machine, phase and cogging torque over one electrical period
    5_efficiency_map.png    efficiency over speed and torque, drive limit (bus voltage and current)
                            and continuous limit (temperatures)

Tested with ParaView 6.2 (pictures and tabs, test T29-6); written to work back to 5.9. Every view is
built separately: if one fails in your ParaView version, the others are still built and the error
is printed.
"""

import argparse
import csv
import json
import math
import os
import sys
import traceback

EXPORT = ""     # export folder of emachine export, for Run Script in the GUI
MAP = ""        # map folder of emachine map
OUT = ""        # where the pictures go

#: material id (cell array "material") -> (label, solid colour, colour map preset for |B|)
MATERIALS = {
    4: ("Stator core", (0.55, 0.58, 0.62), ["Blues", "Cool to Warm"]),
    2: ("Copper coil", (0.85, 0.45, 0.18), ["Oranges", "Copper", "Inferno (matplotlib)"]),
    3: ("Magnets", (0.70, 0.16, 0.22), ["Purples", "Magma (matplotlib)"]),
    5: ("Rotor iron", (0.36, 0.37, 0.40), ["Greens", "Viridis (matplotlib)"]),
    6: ("Rotor housing", (0.80, 0.81, 0.83), ["Greens", "Viridis (matplotlib)"]),
}
STATOR_MATERIALS = (2, 4)
RESOLUTION = [1600, 1200]
INTERACTIVE = False     # set by --interactive: views go into tabs of the GUI, no pictures


# ----------------------------------------------------------------------------- inputs (no ParaView)

def read_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def check_inputs(export, mapdir):
    """Missing files, keys or columns the views need, as a list of messages (empty when complete)."""
    missing = []

    def need(path):
        if not os.path.isfile(path):
            missing.append(f"file {path}")
            return False
        return True

    if need(os.path.join(export, "summary.json")):
        with open(os.path.join(export, "summary.json")) as f:
            summary = json.load(f)
        for key in ("pole_pairs", "phases", "machine_torque_Nm", "phase_pitch_mm", "phase_turn_deg"):
            if key not in summary:
                missing.append(f"summary.json key {key}")
    for name in ("full_motor.vtu", "machine.pvd"):
        need(os.path.join(export, name))
    if need(os.path.join(export, "waveforms.csv")):
        columns = read_csv(os.path.join(export, "waveforms.csv"))[0].keys()
        for column in ("electrical_angle_deg", "machine_torque_Nm"):
            if column not in columns:
                missing.append(f"waveforms.csv column {column}")
    for name, arrays in (("efficiency_map.vtu", ("efficiency_percent", "within_drive_limits")),
                         ("efficiency_limits.vtu", ("curve",))):
        if need(os.path.join(mapdir, name)):
            present = vtu_arrays(os.path.join(mapdir, name))
            missing += [f"{name} array {a}" for a in arrays if a not in present]
    return missing


def vtu_arrays(path):
    """Names of the data arrays in a VTU file written by tfm/vtkio.py.

    The arrays are stored inline, so their tags are spread over the whole file, which is searched
    through a memory map.
    """
    import mmap
    import re
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        return [m.group(1).decode("latin-1") for m in re.finditer(rb'<DataArray[^>]*?Name="([^"]*)"', data)]


def is_section(summary):
    """True for the export of a 2D cross-section: all phases in one solution, extruded along z."""
    return summary.get("model") == "section2d"


def csv_columns(path):
    with open(path, newline="") as f:
        return next(csv.reader(f))


def first_step_file(export):
    """First VTU file listed in machine.pvd."""
    with open(os.path.join(export, "machine.pvd")) as f:
        text = f.read()
    name = text.split('file="', 1)[1].split('"', 1)[0]
    return os.path.join(export, name)


# ----------------------------------------------------------------------------- ParaView helpers

def threshold(source, material):
    """Cells of one material (cell array 'material'), for ParaView 5.9 and later."""
    from paraview.simple import Threshold
    th = Threshold(Input=source)
    th.Scalars = ["CELLS", "material"]
    try:                                    # ParaView 5.10 and later
        th.LowerThreshold, th.UpperThreshold = material - 0.5, material + 0.5
        th.ThresholdMethod = "Between"
    except AttributeError:                  # ParaView 5.9
        th.ThresholdRange = [material - 0.5, material + 0.5]
    return th


def has_cells(source, time=None):
    """True when the output of a filter is not empty."""
    if time is None:
        source.UpdatePipeline()
    else:
        source.UpdatePipeline(time)
    return source.GetDataInformation().GetNumberOfCells() > 0


def material_parts(source, time=None):
    """(material id, threshold) of every material that has cells in `source`. The range of the
    'material' array is not enough: an outrunner has a housing (6) but no rotor iron (5)."""
    parts = []
    for material in sorted(MATERIALS):
        part = threshold(source, material)
        if has_cells(part, time):
            parts.append((material, part))
        else:
            from paraview.simple import Delete
            Delete(part)
    return parts


def solid_colour(display, rgb):
    """One colour, no colour map. ColorBy(display, None) fails in ParaView 6.2; an empty array name
    is what ParaView itself records for "Solid Color"."""
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


def apply_preset(lut, names):
    for name in names:
        try:
            if lut.ApplyPreset(name, True):
                return name
        except Exception:
            pass
    return None


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


def place_scalar_bar(bar, index):
    """Vertical bars side by side along the right edge, dark text on the white background."""
    bar.TitleColor = [0.1, 0.1, 0.1]
    bar.LabelColor = [0.1, 0.1, 0.1]
    try:
        bar.RangeLabelFormat = bar.LabelFormat = number_format(2)
        bar.AutomaticLabelFormat = 0
        bar.TitleFontSize = 14
        bar.LabelFontSize = 13
    except Exception:
        pass
    for location in ("Any Location", "AnyLocation"):
        try:
            bar.WindowLocation = location
            break
        except Exception:
            pass
    bar.Orientation = "Vertical"
    bar.Position = [0.62 + 0.095 * index, 0.10]
    bar.ScalarBarLength = 0.38


def in_tab(view, title):
    """Puts the view into a tab of its own (interactive mode)."""
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
    view.OrientationAxesVisibility = 1
    return view


def save(view, path):
    from paraview.simple import Render, SaveScreenshot
    Render(view)
    if INTERACTIVE:
        return
    SaveScreenshot(path, view, ImageResolution=RESOLUTION)
    print("  ->", path)


def oblique_camera(view, centre, distance, elevation=0.55, shift=0.0):
    """Camera looking down at `centre` from the front right. `shift` (share of `distance`) moves the
    picture to the left on the screen, to leave room for colour bars on the right."""
    position = [centre[0] + distance, centre[1] - 1.2 * distance, centre[2] + elevation * distance * 2]
    direction = [c - p for c, p in zip(centre, position)]
    right = [direction[1], -direction[0], 0.0]                  # direction x up (up = +Z)
    norm = math.hypot(right[0], right[1]) or 1.0
    move = [shift * distance * r / norm for r in right]
    view.CameraFocalPoint = [c + m for c, m in zip(centre, move)]
    view.CameraPosition = [p + m for p, m in zip(position, move)]
    view.CameraViewUp = [0.0, 0.0, 1.0]


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
    try:                                    # a light box behind the text, readable over the model
        display.ShowBorder = "Always"       # the box is drawn with the border (ParaView 5.10 and later)
        display.BorderColor = [1.0, 1.0, 1.0]
        display.BackgroundColor = [1.0, 1.0, 1.0, 0.85]
    except Exception:
        pass
    try:
        display.Justification = "Left"
    except Exception:
        pass


# ----------------------------------------------------------------------------- the five views

def view_full_motor(export, summary, out, cut=True):
    """1: every phase (full_motor.vtu), cut open by a quarter, solid colours per material."""
    from paraview.simple import Clip, Show, XMLUnstructuredGridReader
    motor_file = os.path.join(export, "full_motor.vtu")
    motor = XMLUnstructuredGridReader(FileName=[motor_file])
    view = new_render_view("1 Full motor")
    motor.UpdatePipeline()
    b = motor.GetDataInformation().GetBounds()
    radius = max(abs(b[0]), abs(b[1]), abs(b[2]), abs(b[3]))
    for material, shown in material_parts(motor):
        label, rgb, _ = MATERIALS[material]
        if cut:
            # Remove the quarter x > 0, y < 0, which faces the camera.
            shown = Clip(Input=shown)
            shown.ClipType = "Box"
            size = 1000.0
            shown.ClipType.Position = [0.0, -size, -size]
            shown.ClipType.Length = [size, size, 2 * size]
            try:
                shown.Invert = 0            # keep what lies outside the box
            except Exception:
                pass
        display = Show(shown, view)
        solid_colour(display, rgb)
    oblique_camera(view, (0.0, 0.0, (b[4] + b[5]) / 2), 2.4 * radius)
    if is_section(summary):
        text_label(view, "Full motor, %d phases (2D cross-section extruded to the stack length), quarter cut away\n"
                         "grey: stator core   orange: copper   red: magnets   dark grey: rotor iron"
                   % int(summary["phases"]))
    else:
        text_label(view, "Full motor, %d phases, quarter cut away\n"
                         "grey: stator core   orange: copper   red: magnets   light grey: rotor housing / iron"
                   % int(summary["phases"]))
    save(view, os.path.join(out, "1_full_motor.png"))


def step_of_highest_torque(summary):
    torque = summary["machine_torque_Nm"]
    return max(range(len(torque)), key=lambda k: torque[k])


def set_time(view, reader, step):
    from paraview.simple import GetAnimationScene
    times = list(reader.TimestepValues) if reader.TimestepValues else [0.0]
    time = times[min(step, len(times) - 1)]
    scene = GetAnimationScene()
    scene.UpdateAnimationUsingDataTimeSteps()
    scene.AnimationTime = time
    view.ViewTime = time
    return time


def view_segment_field(export, summary, out):
    """2: the exported sector at the position of highest torque, |B| with a colour map per material."""
    from paraview.simple import Calculator, GetColorTransferFunction, GetScalarBar, PVDReader, Show
    reader = PVDReader(FileName=os.path.join(export, "machine.pvd"))
    view = new_render_view("2 Field per material")
    step = step_of_highest_torque(summary)
    set_time(view, reader, step)
    bars = 0
    for material, part in material_parts(reader, view.ViewTime):
        label, rgb, presets = MATERIALS[material]
        name = "B_" + label.split()[0].lower() + "_T"       # own array name: own colour map
        field = Calculator(Input=part)
        field.ResultArrayName = name
        field.Function = "B_magnitude"
        try:
            field.AttributeType = "Point Data"
        except Exception:
            pass
        display = Show(field, view)
        display.ColorArrayName = ["POINTS", name]
        lut = GetColorTransferFunction(name)
        apply_preset(lut, presets)
        field.UpdatePipeline(view.ViewTime)
        array = field.PointData[name]
        high = array.GetRange()[1] if array is not None else 2.0
        lut.RescaleTransferFunction(0.0, max(high, 1e-6))
        display.LookupTable = lut
        bar = GetScalarBar(lut, view)
        bar.Title = "B %s (T)" % label
        bar.ComponentTitle = ""
        place_scalar_bar(bar, bars)
        display.SetScalarBarVisibility(view, True)
        bars += 1
    reader.UpdatePipeline(view.ViewTime)
    b = reader.GetDataInformation().GetBounds()
    centre = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2)
    extent = max(b[1] - b[0], b[3] - b[2], b[5] - b[4])
    torque = summary["machine_torque_Nm"][step]
    if is_section(summary):
        flux_lines(export, view, b[5])
        top_camera(view, (centre[0], centre[1]), 0.58 * extent, shift=0.24)
        text_label(view, "Cross-section, electrical angle %.1f deg, machine torque %.3f N m\n"
                         "Flux density magnitude in tesla, one colour map per material; black: flux lines"
                   % (summary["electrical_angle_deg"][step], torque))
    else:
        oblique_camera(view, centre, 1.35 * extent, shift=0.22)
        text_label(view, "Sector of %d pole pair(s), electrical angle %.1f deg, machine torque %.3f N m\n"
                         "Flux density magnitude in tesla, one colour map per material"
                   % (int(summary.get("sectors", 1)), summary["electrical_angle_deg"][step], torque))
    save(view, os.path.join(out, "2_segment_field.png"))


def top_camera(view, centre, half_height, shift=0.0):
    """Parallel projection looking down the z axis at `centre` (x, y); `half_height` is half the
    height shown. `shift` (share of the height) moves the picture to the left on the screen."""
    x, y = centre[0] + shift * 2 * half_height, centre[1]
    view.CameraParallelProjection = 1
    view.CameraFocalPoint = [x, y, 0.0]
    view.CameraPosition = [x, y, 20.0 * half_height]
    view.CameraViewUp = [0.0, 1.0, 0.0]
    view.CameraParallelScale = half_height


def flux_lines(export, view, top, levels=30):
    """Contour lines of the vector potential A_z (flux lines) on the top face of solid parts and air."""
    from paraview.simple import Contour, PVDReader, Show, Slice
    readers = [PVDReader(FileName=os.path.join(export, name + ".pvd")) for name in ("machine", "air")
               if os.path.isfile(os.path.join(export, name + ".pvd"))]
    low, high = None, None
    for reader in readers:
        reader.UpdatePipeline(view.ViewTime)
        a, b = reader.PointData["A_z"].GetRange()
        low, high = (a, b) if low is None else (min(low, a), max(high, b))
    step = (high - low) / (levels + 1)
    values = [low + step * (k + 1) for k in range(levels)]
    for reader in readers:
        face = Slice(Input=reader)
        face.SliceType = "Plane"
        face.SliceType.Origin = [0.0, 0.0, top - 1e-6 * max(abs(top), 1.0)]
        face.SliceType.Normal = [0.0, 0.0, 1.0]
        lines = Contour(Input=face)
        lines.ContourBy = ["POINTS", "A_z"]
        lines.Isosurfaces = values
        display = Show(lines, view)
        solid_colour(display, (0.05, 0.05, 0.05))
        display.LineWidth = 1.2


def view_mesh(export, out, summary=None):
    """3: the Gmsh mesh: solid parts with element edges, air cut at the mid-plane (whole cells)."""
    from paraview.simple import Clip, PVDReader, Show
    if summary and is_section(summary):
        return view_section_mesh(export, summary, out)
    reader = PVDReader(FileName=os.path.join(export, "machine.pvd"))
    view = new_render_view("3 Mesh")
    set_time(view, reader, 0)
    for material, part in material_parts(reader, view.ViewTime):
        label, rgb, _ = MATERIALS[material]
        display = Show(part, view)
        display.SetRepresentationType("Surface With Edges")
        solid_colour(display, rgb)
        display.EdgeColor = [0.1, 0.1, 0.1]
    air_file = os.path.join(export, "air.pvd")
    if os.path.isfile(air_file):
        air = PVDReader(FileName=air_file)
        cut = Clip(Input=air)
        cut.ClipType = "Plane"
        cut.ClipType.Origin = [0.0, 0.0, 0.0]
        cut.ClipType.Normal = [0.0, 0.0, 1.0]
        try:
            cut.Crinkleclip = 1             # whole tetrahedra, not cut ones
        except Exception:
            pass
        display = Show(cut, view)
        display.SetRepresentationType("Surface With Edges")
        solid_colour(display, (0.75, 0.85, 0.95))
        display.Opacity = 0.35
    reader.UpdatePipeline(view.ViewTime)
    b = reader.GetDataInformation().GetBounds()
    centre = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2)
    oblique_camera(view, centre, 1.3 * max(b[1] - b[0], b[3] - b[2], b[5] - b[4]))
    elements = reader.GetDataInformation().GetNumberOfCells()
    text_label(view, "Gmsh mesh of the sector: %d tetrahedra in the solid parts\n"
                     "light blue: air, cut at the axial mid-plane" % elements)
    save(view, os.path.join(out, "3_mesh.png"))


def view_section_mesh(export, summary, out):
    """3 for a section: the triangles near the bore, seen from the top (slot opening, gap, magnets)."""
    from paraview.simple import PVDReader, Show
    view = new_render_view("3 Mesh")
    readers = [(PVDReader(FileName=os.path.join(export, "machine.pvd")), None)]
    if os.path.isfile(os.path.join(export, "air.pvd")):
        readers.append((PVDReader(FileName=os.path.join(export, "air.pvd")), (0.75, 0.85, 0.95)))
    set_time(view, readers[0][0], 0)
    for reader, colour in readers:
        parts = material_parts(reader, view.ViewTime) if colour is None else [(None, reader)]
        for material, part in parts:
            display = Show(part, view)
            display.SetRepresentationType("Surface With Edges")
            solid_colour(display, colour or MATERIALS[material][1])
            display.EdgeColor = [0.1, 0.1, 0.1]
    radii = summary["radii_mm"]
    bore = radii["r_stator"]
    top_camera(view, (bore, 0.0), 0.45 * bore)
    text_label(view, "Mesh of the cross-section near the bore, at a slot opening: %d triangles in the whole section\n"
                     "light blue: air (gap, between the magnets); the mesh is made again at every rotor position"
               % int(summary.get("elements", 0)))
    save(view, os.path.join(out, "3_mesh.png"))


def view_hybrid_field(export, summary, out):
    """6 (hybrid machines): the radial section (machine.pvd) and the axial slices on both discs
    (axial.pvd) at the position of highest torque, |B| in one colour map, a quarter cut away."""
    from paraview.simple import Clip, GetColorTransferFunction, GetScalarBar, PVDReader, Show
    view = new_render_view("6 Radial section and axial slices")
    step = step_of_highest_torque(summary)
    lut = GetColorTransferFunction("B_magnitude")
    apply_preset(lut, ("Inferno (matplotlib)", "Viridis (matplotlib)"))
    lut.RescaleTransferFunction(0.0, 2.0)
    bounds = None
    for name in ("machine", "axial"):
        reader = PVDReader(FileName=os.path.join(export, name + ".pvd"))
        set_time(view, reader, step)
        shown = Clip(Input=reader)
        shown.ClipType = "Box"
        size = 1000.0
        shown.ClipType.Position = [0.0, -size, -size]
        shown.ClipType.Length = [size, size, 2 * size]
        try:
            shown.Invert = 0
        except Exception:
            pass
        display = Show(shown, view)
        display.ColorArrayName = ["POINTS", "B_magnitude"]
        display.LookupTable = lut
        reader.UpdatePipeline(view.ViewTime)
        b = reader.GetDataInformation().GetBounds()
        bounds = b if bounds is None else [min(bounds[0], b[0]), max(bounds[1], b[1]), min(bounds[2], b[2]),
                                           max(bounds[3], b[3]), min(bounds[4], b[4]), max(bounds[5], b[5])]
    bar = GetScalarBar(lut, view)
    bar.Title = "|B| (T)"
    bar.ComponentTitle = ""
    place_scalar_bar(bar, 2)
    display.SetScalarBarVisibility(view, True)
    radius = max(abs(v) for v in bounds[:4])
    oblique_camera(view, (0.0, 0.0, 0.0), 2.2 * radius, elevation=0.45, shift=0.15)
    shares = summary.get("torque_shares_Nm") or {}
    text = ", ".join("%s %.1f N m" % (k, v) for k, v in shares.items())
    text_label(view, "Quasi-3D model at electrical angle %.1f deg, machine torque %.1f N m\n"
                     "radial section (extruded over the radial teeth) and axial slices on both discs, |B| in T\n"
                     "mean torque per part: %s" % (summary["electrical_angle_deg"][step],
                                                     summary["machine_torque_Nm"][step], text))
    save(view, os.path.join(out, "6_radial_and_axial_field.png"))


def view_torque(export, summary, out):
    """4: torque over one electrical period."""
    from paraview.simple import CSVReader, CreateView, Render, SaveScreenshot, Show
    table = CSVReader(FileName=[os.path.join(export, "waveforms.csv")])
    chart = CreateView("XYChartView")
    in_tab(chart, "4 Torque vs angle")
    if not INTERACTIVE:
        chart.ViewSize = RESOLUTION
    display = Show(table, chart)
    display.UseIndexForXAxis = 0
    display.XArrayName = "electrical_angle_deg"
    present = csv_columns(os.path.join(export, "waveforms.csv"))
    series = [c for c in ("machine_torque_Nm", "phase_torque_Nm", "cogging_torque_Nm") if c in present]
    display.SeriesVisibility = series
    try:
        display.SeriesLabel = ["machine_torque_Nm", "Machine torque (%d phases)" % int(summary["phases"]), "phase_torque_Nm",
                               "Torque of one phase", "cogging_torque_Nm", "Cogging torque (no current)"]
        display.SeriesColor = ["machine_torque_Nm", "0.1", "0.2", "0.6", "phase_torque_Nm", "0.85", "0.45", "0.18",
                               "cogging_torque_Nm", "0.4", "0.4", "0.4"]
        display.SeriesLineThickness = ["machine_torque_Nm", "3", "phase_torque_Nm", "2", "cogging_torque_Nm", "2"]
    except Exception:
        pass
    torque = summary.get("torque", {})
    title = "Torque over one electrical period"
    if torque:
        title += ": mean %.3f N m, ripple %.1f %%" % (torque.get("mean", 0.0), 100 * torque.get("ripple", 0.0))
    chart.ChartTitle = title
    chart.LeftAxisTitle = "Torque (N m)"
    chart.BottomAxisTitle = "Electrical angle (deg)"
    try:
        chart.BottomAxisUseCustomRange = 1
        chart.BottomAxisRangeMinimum, chart.BottomAxisRangeMaximum = 0.0, 360.0
    except Exception:
        pass
    Render(chart)
    if not INTERACTIVE:
        path = os.path.join(out, "4_torque_vs_angle.png")
        SaveScreenshot(path, chart, ImageResolution=RESOLUTION)
        print("  ->", path)


def view_efficiency_map(mapdir, out):
    """5: efficiency over speed and torque (efficiency_map.vtu), with the drive and continuous limits."""
    from paraview.simple import (Clip, ColorBy, Contour, GetColorTransferFunction, GetScalarBar, Show, Threshold,
                                 XMLUnstructuredGridReader)
    grid = XMLUnstructuredGridReader(FileName=[os.path.join(mapdir, "efficiency_map.vtu")])
    grid.UpdatePipeline()
    b = grid.GetDataInformation().GetBounds()
    speed_max, torque_max = b[1] or 1.0, b[3] or 1.0       # speed in 1000 rpm, torque in N m
    scale = 0.7 * speed_max / torque_max        # torque is drawn stretched to a readable aspect ratio

    # Cut along the drive limit (torque margin 0), not along whole cells.
    inside = Clip(Input=grid)
    inside.ClipType = "Scalar"
    inside.Scalars = ["POINTS", "drive_margin_Nm"]
    inside.Value = 0.0
    inside.Invert = 0                       # keep margin >= 0
    inside.UpdatePipeline()
    best = inside.PointData["efficiency_percent"].GetRange()[1]

    view = new_render_view("5 Efficiency map")
    view.OrientationAxesVisibility = 0
    display = Show(inside, view)
    display.Scale = [1.0, scale, 1.0]
    ColorBy(display, ("POINTS", "efficiency_percent"))
    lut = GetColorTransferFunction("efficiency_percent")
    apply_preset(lut, ["Turbo", "Jet", "Rainbow Uniform"])
    lut.RescaleTransferFunction(max(0.0, best - 40.0), best)
    bar = GetScalarBar(lut, view)
    bar.Title = "Efficiency (%)"
    bar.ComponentTitle = ""
    place_scalar_bar(bar, 3)
    bar.Position = [0.93, 0.10]
    bar.RangeLabelFormat = bar.LabelFormat = number_format(0)
    display.SetScalarBarVisibility(view, True)
    try:
        display.DataAxesGrid.GridAxesVisibility = 1
        grid_axes = display.DataAxesGrid
        grid_axes.IgnoreDisplayTransformScale = 1      # labels in N m, not in stretched units
        grid_axes.AxesToLabel = 1 | 2                  # speed below, torque on the left only
        step = 0.1 if torque_max <= 1.5 else (0.2 if torque_max <= 3 else 0.5 * math.ceil(torque_max / 6))
        # Custom label positions are in the stretched display coordinates; the text shows N m.
        grid_axes.YAxisUseCustomLabels = 1
        grid_axes.YAxisLabels = [k * step * scale for k in range(int(torque_max / step + 1e-9) + 1)]
        grid_axes.YAxisNotation = "Fixed"
        grid_axes.YAxisPrecision = 1 if step >= 0.1 else 2
        display.DataAxesGrid.XTitle = "Speed (1000 rpm)"
        display.DataAxesGrid.YTitle = "Torque (N m)"
        display.DataAxesGrid.GridColor = [0.3, 0.3, 0.3]
        display.DataAxesGrid.XTitleColor = display.DataAxesGrid.YTitleColor = [0.1, 0.1, 0.1]
        display.DataAxesGrid.XLabelColor = display.DataAxesGrid.YLabelColor = [0.1, 0.1, 0.1]
    except Exception:
        pass

    levels = [round(best - d, 1) for d in (30, 20, 10, 5, 2) if best - d > 0]
    lines = Contour(Input=inside)
    lines.ContourBy = ["POINTS", "efficiency_percent"]
    lines.Isosurfaces = levels
    line_display = Show(lines, view)
    line_display.Scale = [1.0, scale, 1.0]
    solid_colour(line_display, (0.1, 0.1, 0.1))
    line_display.LineWidth = 1.5

    limits = XMLUnstructuredGridReader(FileName=[os.path.join(mapdir, "efficiency_limits.vtu")])
    for curve, rgb in ((0, (0.0, 0.0, 0.0)), (1, (0.85, 0.1, 0.1))):
        th = Threshold(Input=limits)
        th.Scalars = ["CELLS", "curve"]
        try:
            th.LowerThreshold, th.UpperThreshold = curve - 0.5, curve + 0.5
            th.ThresholdMethod = "Between"
        except AttributeError:
            th.ThresholdRange = [curve - 0.5, curve + 0.5]
        curve_display = Show(th, view)
        curve_display.Scale = [1.0, scale, 1.0]
        solid_colour(curve_display, rgb)
        curve_display.LineWidth = 3.0

    view.CameraParallelProjection = 1
    view.CameraPosition = [speed_max / 2, 0.5 * scale * torque_max, 10 * speed_max]
    view.CameraFocalPoint = [speed_max / 2, 0.5 * scale * torque_max, 0.0]
    view.CameraViewUp = [0.0, 1.0, 0.0]
    view.CameraParallelScale = 0.65 * scale * torque_max
    text_label(view, "Torque, speed and efficiency. Black line: drive limit (bus voltage, peak current); "
                     "red line: continuous limit (temperatures).\nContours at %s; best %.1f %%"
               % (", ".join("%.0f %%" % v for v in levels), best))
    save(view, os.path.join(out, "5_efficiency_map.png"))


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", default=EXPORT, help="folder written by emachine export")
    ap.add_argument("--map", default=MAP, help="folder written by emachine map")
    ap.add_argument("--out", default=OUT, help="folder for the pictures (default: <export>/views)")
    ap.add_argument("--no-cut", action="store_true", help="show the full motor without the quarter cut away")
    ap.add_argument("--check", action="store_true", help="only check that every input exists")
    ap.add_argument("--interactive", action="store_true", help="build the views as tabs in the GUI, no pictures")
    args = ap.parse_args(argv)
    global INTERACTIVE
    INTERACTIVE = args.interactive
    if not args.export or not args.map:
        sys.exit("Give --export and --map (or fill in EXPORT and MAP at the top of the script).")
    missing = check_inputs(args.export, args.map)
    if missing:
        sys.exit("Missing inputs:\n  " + "\n  ".join(missing))
    if args.check:
        print("All inputs present.")
        return 0
    out = args.out or os.path.join(args.export, "views")
    if not INTERACTIVE:
        os.makedirs(out, exist_ok=True)
    with open(os.path.join(args.export, "summary.json")) as f:
        summary = json.load(f)

    failures = 0
    for name, build in (("1 full motor", lambda: view_full_motor(args.export, summary, out, not args.no_cut)),
                        ("2 segment field", lambda: view_segment_field(args.export, summary, out)),
                        ("3 mesh", lambda: view_mesh(args.export, out, summary)),
                        ("4 torque vs angle", lambda: view_torque(args.export, summary, out)),
                        ("5 efficiency map", lambda: view_efficiency_map(args.map, out))) + (
            (("6 radial and axial field", lambda: view_hybrid_field(args.export, summary, out)),)
            if summary.get("hybrid") else ()):
        print("View", name)
        try:
            build()
        except Exception:
            failures += 1
            traceback.print_exc()
            print("View", name, "failed; the others go on.")
    if INTERACTIVE:
        print("Views in tabs", "(%d failed)" % failures if failures else "")
    else:
        print("Pictures in", out, "(%d failed)" % failures if failures else "")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
