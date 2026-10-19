"""
Data files that make the whole machine and the efficiency map open directly in ParaView.

    full_motor.vtu         every phase of the machine, built from full_ring.vtu of a field export
    efficiency_map.vtu     the speed and torque grid of a map as a surface (x speed in 1000 rpm,
                           y torque in N m), every column of efficiency_map.csv as point data
    efficiency_limits.vtu  drive limit and continuous limit of the map as lines (cell array `curve`)

None of this needs ParaView: the files are written with numpy only.
"""

import csv
import json
import os
import shutil

import numpy as np

from . import vtk as vtkio

#: Materials of the stator, which turns with the phase; the rotor does not.
STATOR_MATERIALS = (2, 4)
#: Curves of efficiency_limits.vtu.
CURVES = {0: "drive limit (bus voltage, peak current)", 1: "continuous limit (temperatures)"}


def full_motor(export_dir):
    """
    Writes full_motor.vtu: the ring of one phase (full_ring.vtu) repeated for every phase. Phase k is
    moved k * phase_pitch_mm along +Z, and its stator parts are turned by k * phase_turn_deg about Z,
    as the phases of the real machine are. Adds the cell array `phase`. Returns the file path.

    A ring that already holds every phase (summary key `ring_has_all_phases`: the cross-section
    of a radial flux machine) is written once, with its own `phase` array.
    """
    with open(os.path.join(export_dir, "summary.json")) as f:
        summary = json.load(f)
    ring = vtkio.read_vtu(os.path.join(export_dir, "full_ring.vtu"))
    path = os.path.join(export_dir, "full_motor.vtu")
    if summary.get("ring_has_all_phases"):
        vtkio.write_vtu(path, ring["points"], ring["cells"], ring["cell_type"], ring["point_data"], ring["cell_data"])
        return path
    phases = int(summary["phases"])
    pitch, turn = float(summary["phase_pitch_mm"]), float(summary["phase_turn_deg"])
    points, cells = ring["points"], ring["cells"]
    material = ring["cell_data"]["material"]
    # A point belongs to the stator when a stator cell uses it; stator and rotor share no points.
    stator_point = np.zeros(len(points), dtype=bool)
    stator_point[np.unique(cells[np.isin(material, STATOR_MATERIALS)])] = True

    all_points, all_cells, point_data, cell_data = [], [], {}, {}
    for k in range(phases):
        moved = points.copy()
        moved[stator_point] = vtkio.rotate_z(points[stator_point], k * turn)
        moved[:, 2] += k * pitch
        all_points.append(moved)
        all_cells.append(cells + k * len(points))
        for name, array in ring["point_data"].items():
            array = np.asarray(array, dtype=float)
            if array.ndim == 2 and array.shape[1] == 3:
                array = array.copy()
                array[stator_point] = vtkio.rotate_z(array[stator_point], k * turn)
            point_data.setdefault(name, []).append(array)
        for name, array in ring["cell_data"].items():
            cell_data.setdefault(name, []).append(array)
        cell_data.setdefault("phase", []).append(np.full(len(cells), k + 1, dtype=np.int64))
    vtkio.write_vtu(path, np.vstack(all_points), np.vstack(all_cells), ring["cell_type"],
                    {n: np.concatenate(v) for n, v in point_data.items()},
                    {n: np.concatenate(v) for n, v in cell_data.items()})
    return path


def _columns(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    names = list(rows[0].keys())
    return {n: np.array([float(r[n]) if r[n] != "" else np.nan for r in rows]) for n in names}


def efficiency_map(map_dir, out_dir=None):
    """
    Writes efficiency_map.vtu and efficiency_limits.vtu from efficiency_map.csv and envelope.csv of
    a map folder (into `out_dir`, default the map folder). Returns the two file paths.

    The grid of efficiency_map.csv is regular, speed by speed with the torque running fastest. Point
    data: every column, efficiency also in percent, and the distance below the drive and the
    continuous limit in N m (`drive_margin_Nm`, `continuous_margin_Nm`: a clip at 0 cuts the map
    smoothly along the limit). Cell data: `within_drive_limits` and `continuous`, 1 when all four
    corners are. The limit lines end where the limit torque reaches zero.
    """
    out_dir = out_dir or map_dir
    grid = _columns(os.path.join(map_dir, "efficiency_map.csv"))
    env = _columns(os.path.join(map_dir, "envelope.csv"))
    speeds, torques = np.unique(grid["speed_rpm"]), np.unique(grid["torque_Nm"])
    ns, nt = len(speeds), len(torques)
    if ns * nt != len(grid["speed_rpm"]):
        raise ValueError(f"{map_dir}: efficiency_map.csv is not a regular grid of speed and torque.")
    order = np.lexsort((grid["torque_Nm"], grid["speed_rpm"]))       # speed major, torque fastest
    grid = {n: v[order] for n, v in grid.items()}
    points = np.column_stack([grid["speed_rpm"] / 1000.0, grid["torque_Nm"], np.zeros(ns * nt)])

    i, j = np.meshgrid(np.arange(ns - 1), np.arange(nt - 1), indexing="ij")
    corner = (i * nt + j).ravel()
    quads = np.column_stack([corner, corner + nt, corner + nt + 1, corner + 1])     # counter-clockwise
    point_data = {n: np.nan_to_num(v) for n, v in grid.items()}
    point_data["efficiency_percent"] = 100.0 * point_data["efficiency"]
    point_data["speed_krpm"] = grid["speed_rpm"] / 1000.0
    for name, column in (("drive_margin_Nm", "drive_torque_Nm"), ("continuous_margin_Nm", "continuous_torque_Nm")):
        limit = np.interp(grid["speed_rpm"], env["speed_rpm"], np.nan_to_num(env[column]))
        point_data[name] = limit - grid["torque_Nm"]
    cell_data = {n: np.all(point_data[n][quads] > 0.5, axis=1).astype(np.int64)
                 for n in ("within_drive_limits", "continuous")}
    inside = point_data["within_drive_limits"] > 0.5
    best = int(np.argmax(np.where(inside, point_data["efficiency"], -1.0)))
    field = {"best_efficiency": point_data["efficiency"][best], "best_speed_rpm": grid["speed_rpm"][best],
             "best_torque_Nm": grid["torque_Nm"][best], "speed_max_rpm": speeds[-1], "torque_max_Nm": torques[-1]}
    map_path = os.path.join(out_dir, "efficiency_map.vtu")
    vtkio.write_vtu(map_path, points, quads, vtkio.QUAD, point_data, cell_data, field)

    line_points, lines, curve = [], [], []
    for number, column in ((0, "drive_torque_Nm"), (1, "continuous_torque_Nm")):
        start = sum(len(p) for p in line_points)
        torque = np.nan_to_num(env[column])
        zero = np.flatnonzero(torque <= 0.0)
        count = int(zero[0]) + 1 if len(zero) and zero[0] > 0 else len(torque)     # up to the first zero
        line_points.append(np.column_stack([env["speed_rpm"][:count] / 1000.0, torque[:count],
                                            np.full(count, 0.001)]))
        lines.append(np.column_stack([np.arange(start, start + count - 1), np.arange(start + 1, start + count)]))
        curve.append(np.full(count - 1, number, dtype=np.int64))
    limits_path = os.path.join(out_dir, "efficiency_limits.vtu")
    vtkio.write_vtu(limits_path, np.vstack(line_points), np.vstack(lines), vtkio.LINE, None,
                    {"curve": np.concatenate(curve)})
    return map_path, limits_path


def write_open_script(export_dir, views_script):
    """
    Copies the view script next to the export and writes open_in_paraview.py, which builds the five
    views as tabs in the ParaView GUI (View > Python Shell > Run Script).
    """
    shutil.copy(views_script, os.path.join(export_dir, "paraview_views.py"))
    path = os.path.join(export_dir, "open_in_paraview.py")
    with open(path, "w") as f:
        f.write(OPEN_SCRIPT.replace("EXPORT_DIR", os.path.abspath(export_dir)))
    return path


OPEN_SCRIPT = '''"""
The five views of this export as tabs in the ParaView GUI: full motor, field per material, mesh,
torque against electrical angle, efficiency map.

    ParaView: View > Python Shell > Run Script, pick this file.
    or:       paraview --script=open_in_paraview.py

Uses paraview_views.py in the same folder. Pictures instead of tabs:
    pvpython paraview_views.py --export . --map .
"""
import os
import sys

try:
    here = os.path.dirname(os.path.abspath(__file__))
except NameError:                   # Run Script of some ParaView versions has no __file__
    here = r"EXPORT_DIR"
if here not in sys.path:
    sys.path.insert(0, here)
# The Python shell of the GUI keeps modules between runs: drop an older copy so that the file on
# disk is used every time.
sys.modules.pop("paraview_views", None)
import paraview_views as views

views.main(["--export", here, "--map", here, "--interactive"])
'''
