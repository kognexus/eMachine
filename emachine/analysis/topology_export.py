"""
ParaView export of a verified design of the multi-topology study (T65).

    python -m emachine.analysis.topology_export --run <study folder>/runs/<key> --pick optimal --out DIR

From the field files the verification kept (`verify/<pick>_work/pos*/<part>/fields_rated_*.npz`):
one .vtu per rotor position of the rated sweep and a .pvd time series (time = electrical degrees), and
one solution at the peak current (solved here). Radial sections are written in the plane z = 0
(millimetres); axial slices are wrapped onto their cylinders (x = r cos theta, y = r sin theta, z),
all slices of a position in one file.

Cell data: B (T, vector), B_mag (T), material (0 air, 1 stator core, 2 rotor core, 3 magnet, 4/5/6 coil of
phase A/B/C, 7 magnet magnetised the other way: 3 = towards the gap or counter-clockwise), region; point data:
A_z (Wb/m, the flux lines are its contours). Axial machines also as discs (`discs_*.vtu`, T67): every slice
extruded over its radial band (wedge cells).
"""

import argparse
import glob
import json
import math
import os

import numpy as np

from emachine.io.vtk import TRIANGLE, WEDGE, write_pvd, write_vtu
from emachine.solvers.elmer.section2d import triangle_fields

MATERIAL = {"air": 0, "stator_core": 1, "rotor_core": 2, "magnet": 3}


def material_code(name, region):
    kind = region.get("kind")
    if kind == "coil":
        return 4 + int(region["phase"]) % 3
    if kind == "magnet":
        return 3
    if kind == "core":
        return 1 if region.get("side") == "stator" else 2
    return 0


def part_arrays(fields_path, meta, planar=False):
    """Points (mm, 3D), triangles, cell and point data of one part solution (planar: an axial slice unrolled,
    x = r theta, y = z)."""
    f = np.load(fields_path)
    pts, tri, pot, body = f["points"], f["tri"].astype(int), f["potential"], f["body"].astype(int)
    names = [str(n) for n in f["names"]]
    area, centre, b, _ = triangle_fields(pts, tri, pot)
    regions = meta["regions"]
    mat = np.array([material_code(names[i - 1], regions.get(names[i - 1], {})) for i in body])
    geo0 = meta["geometry"]
    for k, i in enumerate(body):                  # magnets magnetised the other way: code 7 (T68)
        region = regions.get(names[i - 1], {})
        if region.get("kind") == "magnet" and region.get("magnetization") is not None:
            mx, my = region["magnetization"]
            if geo0["kind"] == "radial":
                cx, cy = centre[k]
                r = math.hypot(cx, cy) or 1.0
                radial, tangential = (mx * cx + my * cy) / r, (-mx * cy + my * cx) / r
                lead = radial if abs(radial) > 0.3 else tangential
            else:
                lead = my if abs(my) > 0.3 else mx
            if lead < 0:
                mat[k] = 7
    region_id = body.copy()
    geo = meta["geometry"]
    p_mm = pts * 1000.0
    if geo["kind"] == "radial" or planar:
        xyz = np.column_stack([p_mm, np.zeros(len(p_mm))])
        b3 = np.column_stack([b, np.zeros(len(b))])
    else:
        r = geo["radius"]
        theta = p_mm[:, 0] / r
        xyz = np.column_stack([r * np.cos(theta), r * np.sin(theta), p_mm[:, 1]])
        th_c = centre[:, 0] * 1000.0 / r
        b3 = np.column_stack([-np.sin(th_c) * b[:, 0], np.cos(th_c) * b[:, 0], b[:, 1]])
    cell = {"B": b3, "B_mag": np.linalg.norm(b, axis=1), "material": mat.astype(float), "region": region_id.astype(float)}
    return xyz, tri, cell, {"A_z": pot}


def merge(parts):
    pts, tri, cells, points = [], [], {}, {}
    offset = 0
    for xyz, t, cell, point in parts:
        pts.append(xyz)
        tri.append(t + offset)
        offset += len(xyz)
        for k, v in cell.items():
            cells.setdefault(k, []).append(v)
        for k, v in point.items():
            points.setdefault(k, []).append(v)
    return (np.concatenate(pts), np.concatenate(tri), {k: np.concatenate(v) for k, v in cells.items()},
            {k: np.concatenate(v) for k, v in points.items()})


def position_folders(work):
    """{tag: [(part folder, fields file, meta)]} of the kept solutions."""
    out = {}
    for pos in sorted(glob.glob(os.path.join(work, "pos*"))):
        for part_dir in sorted(glob.glob(os.path.join(pos, "*"))):
            meta_path = os.path.join(part_dir, "section.regions.json")
            if not os.path.isfile(meta_path):
                continue
            with open(meta_path) as f:
                meta = json.load(f)
            for path in glob.glob(os.path.join(part_dir, "fields_*.npz")):
                tag = os.path.basename(path)[len("fields_"):-4]
                out.setdefault(tag, []).append((part_dir, path, meta))
    return out


def write_series(entries, out, name, pe):
    """One .vtu per tag (sorted), and the .pvd. entries: {tag: [(dir, path, meta)]}."""
    files = []
    for tag in sorted(entries):
        parts = [part_arrays(path, meta) for _, path, meta in sorted(entries[tag])]
        xyz, tri, cell, point = merge(parts)
        angle = entries[tag][0][2]["rotor_angle_deg"]
        path = os.path.join(out, f"{name}_{tag}.vtu")
        write_vtu(path, xyz, tri, TRIANGLE, point_data=point, cell_data=cell)
        files.append((angle * pe, path))
    if files:
        write_pvd(os.path.join(out, f"{name}.pvd"), files)
    return files


def write_discs(entries, out, name):
    """Axial machines as discs: every slice of a solution extruded over its radial band (wedge cells), the slices
    of one solution in one file. Returns the file names."""
    files = []
    for tag in sorted(entries):
        pts_all, cells_all, data = [], [], {"B": [], "B_mag": [], "material": []}
        a_all = []
        offset = 0
        for _, path, meta in sorted(entries[tag]):
            geo = meta["geometry"]
            xyz2, tri, cell, point = part_arrays(path, meta, planar=True)
            _, _, cell3, _ = part_arrays(path, meta)            # B in machine coordinates
            r, depth = geo["radius"], meta["stack_length_mm"]
            theta = xyz2[:, 0] / r
            n = len(xyz2)
            for rr in (r - depth / 2, r + depth / 2):
                pts_all.append(np.column_stack([rr * np.cos(theta), rr * np.sin(theta), xyz2[:, 1]]))
                a_all.append(point["A_z"])
            cells_all.append(np.column_stack([tri + offset, tri + offset + n]))
            offset += 2 * n
            for k in data:
                data[k].append(cell3[k])
        target = os.path.join(out, f"{name}_{tag}.vtu")
        write_vtu(target, np.concatenate(pts_all), np.concatenate(cells_all), WEDGE,
                  point_data={"A_z": np.concatenate(a_all)}, cell_data={k: np.concatenate(v) for k, v in data.items()})
        files.append(os.path.basename(target))
    return files


def write_unrolled(entries, out, name):
    """The middle slice of an axial machine, unrolled flat (one file per tag)."""
    files = []
    for tag in sorted(entries):
        parts = sorted(entries[tag])
        _, path, meta = parts[len(parts) // 2]
        xyz, tri, cell, point = part_arrays(path, meta, planar=True)
        target = os.path.join(out, f"{name}_{tag}.vtu")
        write_vtu(target, xyz, tri, TRIANGLE, point_data=point, cell_data=cell)
        files.append(os.path.basename(target))
    return files


def export(rundir, pick, out, cfg=None, peak=True, log=print):
    with open(os.path.join(rundir, "verify", f"{pick}.json")) as f:
        record = json.load(f)
    names = record.get("picks", [pick])
    work = os.path.join(rundir, "verify", f"{names[0]}_work")
    os.makedirs(out, exist_ok=True)
    entries = position_folders(work)
    pe = record["design"]["pe"]
    rated = {k: v for k, v in entries.items() if k.startswith("rated_")}
    noload = {k: v for k, v in entries.items() if k.startswith("noload_")}
    summary = {"machine": record["machine"], "pick": pick, "kind": "axial" if record["machine"].startswith("afm") else "radial",
               "torque_Nm": record.get("torque_Nm"), "peak_torque_Nm": record.get("peak_torque_Nm"),
               "ripple": record.get("ripple"), "efficiency": record.get("efficiency"), "files": {},
               "gap_radius_mm": (record.get("design") or {}).get("dims", {}).get("gap_radius_mm")
               or (record.get("design") or {}).get("dims", {}).get("ring_outer_mm")}
    summary["files"]["rated"] = [os.path.basename(p) for _, p in write_series(rated, out, "rated", pe)]
    summary["files"]["no_load"] = [os.path.basename(p) for _, p in write_series(noload, out, "noload", pe)]
    if summary["kind"] == "axial":
        summary["files"]["rated_unrolled"] = write_unrolled(rated, out, "unrolled")
        torque = record.get("torque_waveform_Nm") or []
        tags = sorted(rated)
        best = tags[int(np.argmax(torque))] if len(torque) == len(tags) and tags else (tags[0] if tags else None)
        if best:
            summary["files"]["rated_discs"] = write_discs({best: rated[best]}, out, "discs")
    if record["principle"] == "srm":                  # SRM: the flux map solutions (phase A alone)
        maps = {k: v for k, v in entries.items() if k.startswith("map_")}
        top = max((k for k in maps), default=None, key=lambda k: (int(k.split("_")[2]), -int(k.split("_")[1])))
        if top:
            summary["files"]["aligned_peak"] = [os.path.basename(p) for _, p in
                                                write_series({top: maps[top]}, out, "aligned", record["design"]["pe"])]
    if peak and cfg is not None and record["principle"] != "srm" and record.get("analysed") and \
            not record["machine"].startswith("rafm"):          # the raxial machine's quasi-3D files: T56 export
        summary["files"]["peak"] = [os.path.basename(p) for p in solve_peak(record, cfg, out)]
    torque = record.get("torque_waveform_Nm") or []
    summary["torque_waveform_Nm"] = torque
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    log(f"exported {record['machine']} {pick} -> {out}")
    return summary


def solve_peak(record, cfg, out):
    """The field at the peak current (rotor position 0, the peak current angle), kept and written."""
    from emachine.machines.catalogue import TOPOLOGIES
    from emachine.physics import drive as D
    from emachine.pipeline.drive import FieldRunner
    from .topology_study import envelope_for, fine_envelope, register_solvers, settings_for
    register_solvers()
    topo = TOPOLOGIES[record["machine"]]()
    design = topo.design(fine_envelope(envelope_for(cfg, record["machine"])), record["values"])
    settings = settings_for(cfg, topo, fine=True)
    work = os.path.join(out, "_peak_work")
    runner = FieldRunner(design["params"], settings["analysis"], work, keep=True)
    n_eff = record["winding"]["n_eff"]
    i_abc = D.phase_currents(n_eff * cfg["drive"]["peak_current_A"], 0.0, math.radians(record["gamma_peak_deg"]),
                             record["sequence"])
    runner.solve(0.0, i_abc, tag="peak")
    entries = position_folders(work)
    files = write_series({"peak": entries["peak"]}, out, "peak", design["pe"])
    return [p for _, p in files]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--pick", default="optimal")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = None
    if args.config:
        from .topology_study import load_config
        cfg = load_config(args.config)
    export(args.run, args.pick, args.out, cfg)


if __name__ == "__main__":
    main()
