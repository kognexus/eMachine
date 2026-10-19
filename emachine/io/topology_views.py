"""
Pictures of a topology export (T65), rendered with ParaView's own Python (headless):

    pvpython --force-offscreen-rendering emachine/io/topology_views.py --export DIR --out DIR [--title TEXT]

For the rated sweep (position of the highest torque), the peak-current solution and the no-load
solution: flux density magnitude with flux lines (contours of A_z) and the material layout. Radial
sections are seen from the top; axial slices (wrapped onto their cylinders) from an oblique angle.
Uses only paraview.simple and the standard library.
"""

import argparse
import json
import os

from paraview.simple import (CellDatatoPointData, ColorBy, Contour, CreateView, Delete, GetColorTransferFunction,  # noqa
                             GetScalarBar, GetSources, OpenDataFile, Render, SaveScreenshot, Show, Text, UpdatePipeline)


def render(path, out_png, title, kind, field="B_mag", vmax=2.2, lines=True, material=False, zoom=None, levels=22,
           window=None, discs=False):
    view = CreateView("RenderView")
    view.ViewSize = [1400, 1100] if kind == "radial" else [1600, 1000]
    view.Background = [1, 1, 1]
    try:
        view.UseColorPaletteForBackground = 0
    except AttributeError:
        pass
    view.OrientationAxesVisibility = 0
    src = OpenDataFile(path)
    UpdatePipeline()
    if discs:                                      # half cut away: the r-z section shows the discs and gaps
        from paraview.simple import Clip
        src = Clip(Input=src)
        src.ClipType = "Plane"
        src.ClipType.Normal = [0.0, 1.0, 0.0]
        src.ClipType.Origin = [0.0, 0.0, 0.0]
        lines = False
    if material:
        disp = Show(src, view)
        ColorBy(disp, ("CELLS", "material"))
        lut = GetColorTransferFunction("material")
        lut.InterpretValuesAsCategories = 1
        lut.Annotations = ["0", "air", "1", "stator iron", "2", "rotor iron", "3", "magnet +", "4", "coil A", "5", "coil B",
                           "6", "coil C", "7", "magnet -"]
        lut.IndexedColors = [1, 1, 1, 0.62, 0.62, 0.62, 0.38, 0.38, 0.38, 0.78, 0.16, 0.16, 0.83, 0.63, 0.09,
                             0.18, 0.49, 0.2, 0.08, 0.4, 0.75, 0.12, 0.53, 0.9]
    else:
        smooth = CellDatatoPointData(Input=src)
        disp = Show(smooth, view)
        ColorBy(disp, ("POINTS", field))
        lut = GetColorTransferFunction(field)
        lut.ApplyPreset("Turbo", True)
        lut.RescaleTransferFunction(0.0, vmax)
        bar = GetScalarBar(lut, view)
        bar.Title = "|B| (T)"
        bar.ComponentTitle = ""
        bar.RangeLabelFormat = "%-#6.2f"
        bar.TitleColor = [0, 0, 0]
        bar.LabelColor = [0, 0, 0]
        disp.SetScalarBarVisibility(view, True)
    if lines:
        cont = Contour(Input=src)
        cont.ContourBy = ["POINTS", "A_z"]
        rng = src.PointData["A_z"].GetRange()
        n = levels
        cont.Isosurfaces = [rng[0] + (rng[1] - rng[0]) * (k + 0.5) / n for k in range(n)]
        cd = Show(cont, view)
        ColorBy(cd, None) if False else None
        try:
            cd.ColorArrayName = ["POINTS", ""]
        except Exception:
            pass
        cd.AmbientColor = [0, 0, 0]
        cd.DiffuseColor = [0, 0, 0]
        cd.LineWidth = 0.8
    text = Text(Text=title)
    td = Show(text, view)
    td.FontSize = 18
    td.Color = [0, 0, 0]
    td.WindowLocation = "Upper Left Corner"
    view.ResetCamera()
    cam = view.GetActiveCamera()
    if discs:
        cam.SetFocalPoint(0, 0, 15)
        cam.SetPosition(-70, 160, 70)
        cam.SetViewUp(0, 0, 1)
        view.ResetCamera()
        cam.Zoom(1.3)
    elif window:                                     # unrolled slice: (x0, x1, z0, z1) in mm
        x0, x1, z0, z1 = window
        cam.SetFocalPoint((x0 + x1) / 2, (z0 + z1) / 2, 0)
        cam.SetPosition((x0 + x1) / 2, (z0 + z1) / 2, 400)
        cam.SetViewUp(0, 1, 0)
        view.CameraParallelProjection = 1
        view.CameraParallelScale = max((z1 - z0) / 2 * 1.15, (x1 - x0) / 2 / 1.6)
    elif kind == "radial":
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(0, 0, 400)
        cam.SetViewUp(0, 1, 0)
        view.ResetCamera()
        if zoom:                                   # a sector at the air gap: zoom = gap radius in mm
            cam.SetFocalPoint(0, zoom, 0)
            cam.SetPosition(0, zoom, 400)
            view.CameraParallelProjection = 1
            view.CameraParallelScale = 9.0
    else:
        cam.SetFocalPoint(0, 0, 15)
        cam.SetPosition(170, -170, 140)
        cam.SetViewUp(0, 0, 1)
        view.ResetCamera()
        cam.Zoom(1.25)
    Render(view)
    SaveScreenshot(out_png, view, ImageResolution=view.ViewSize)
    for proxy in list(GetSources().values()):
        Delete(proxy)
    Delete(view)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    args = ap.parse_args(argv)
    with open(os.path.join(args.export, "summary.json")) as f:
        summary = json.load(f)
    os.makedirs(args.out, exist_ok=True)
    kind = summary["kind"]
    files = summary["files"]
    title = args.title or f"{summary['machine']} ({summary['pick']})"
    made = []
    rated = files.get("rated") or []
    if rated:
        torque = summary.get("torque_waveform_Nm") or []
        k = max(range(len(torque)), key=lambda i: torque[i]) if len(torque) == len(rated) else 0
        path = os.path.join(args.export, rated[k])
        render(path, os.path.join(args.out, "rated_field.png"), f"{title}: rated point, |B| and flux lines", kind)
        render(path, os.path.join(args.out, "materials.png"), f"{title}: materials", kind, lines=False, material=True)
        made += ["rated_field.png", "materials.png"]
        if kind == "radial" and summary.get("gap_radius_mm"):
            render(path, os.path.join(args.out, "rated_field_zoom.png"), f"{title}: rated point, close-up at the air gap",
                   kind, zoom=summary["gap_radius_mm"], levels=40)
            made.append("rated_field_zoom.png")
    unrolled = files.get("rated_unrolled") or []
    if unrolled:
        torque = summary.get("torque_waveform_Nm") or []
        k = max(range(len(torque)), key=lambda i: torque[i]) if len(torque) == len(unrolled) else 0
        render(os.path.join(args.export, unrolled[k]), os.path.join(args.out, "rated_unrolled.png"),
               f"{title}: middle slice unrolled (x = r theta, z), rated point", "radial", window=(0.0, 60.0, 0.0, 30.0), levels=40)
        render(os.path.join(args.export, unrolled[k]), os.path.join(args.out, "materials_unrolled.png"),
               f"{title}: middle slice unrolled, materials", "radial", lines=False, material=True, window=(0.0, 60.0, 0.0, 30.0))
        made += ["rated_unrolled.png", "materials_unrolled.png"]
    discs = files.get("rated_discs") or []
    if discs:
        render(os.path.join(args.export, discs[0]), os.path.join(args.out, "rated_discs.png"),
               f"{title}: the slices as discs, half cut away, rated point |B|", "axial", discs=True)
        render(os.path.join(args.export, discs[0]), os.path.join(args.out, "materials_discs.png"),
               f"{title}: the slices as discs, half cut away, materials", "axial", material=True, discs=True)
        made += ["rated_discs.png", "materials_discs.png"]
    for key, label in (("peak", "peak current (42 A)"), ("aligned_peak", "phase A at the highest map current, aligned"),
                       ("no_load", "no load")):
        items = files.get(key) or []
        if items:
            render(os.path.join(args.export, items[0]), os.path.join(args.out, f"{key}_field.png"),
                   f"{title}: {label}, |B| and flux lines", kind, vmax=2.4)
            made.append(f"{key}_field.png")
            if kind == "radial" and summary.get("gap_radius_mm") and key == "peak":
                render(os.path.join(args.export, items[0]), os.path.join(args.out, "peak_field_zoom.png"),
                       f"{title}: {label}, close-up at the air gap", kind, vmax=2.4, zoom=summary["gap_radius_mm"], levels=40)
                made.append("peak_field_zoom.png")
    print("views:", ", ".join(made))


if __name__ == "__main__":
    main()
