"""
Meshes a section part (radial section or one axial slice) with Gmsh, in the calling process:

    meta = mesh_part(params, part, out)       part = {"kind": "radial"} or {"kind": "axial", "slice": k}

Writes <out> (Gmsh 2.2) and <out without .msh>.regions.json; returns the meta data the solver needs:
regions (kind, side, phase, sign, share, magnetisation, area), the air gaps, the boundaries and their
conditions, the depth (stack length or slice depth). Also usable as a command:

    python -m emachine.machines.section2d.mesher --params p.json --part radial|axial --slice k --out s.msh
"""

import argparse
import json
import math
import os
import sys

import gmsh

from . import axial, radial

occ = gmsh.model.occ


#: names used only for the priority of pieces, merged into a region after fragmenting
ALIASES = {"rotor_pole": "rotor_core"}


def fragment(named):
    """Fragments all faces; every piece goes to the earliest name that covers it. {name: [tags]}."""
    tools = [(2, f) for _, f in named]
    _, frag_map = occ.fragment(tools[:1], tools[1:])
    occ.synchronize()
    owner = {}
    for (name, _), children in zip(named, frag_map):
        for dim, tag in children:
            if dim == 2 and tag not in owner:
                owner[tag] = name
    groups = {}
    for tag, name in owner.items():
        groups.setdefault(ALIASES.get(name, name), []).append(tag)
    return groups


def _on_circle(tag, radius):
    lo, hi = gmsh.model.getParametrizationBounds(1, tag)
    for t in (lo[0], (lo[0] + hi[0]) / 2, hi[0]):
        x, y, _ = gmsh.model.getValue(1, tag, [t])
        if abs(math.hypot(x, y) - radius) > 1e-6 * max(radius, 1.0) + 1e-6:
            return False
    return True


def _boundary(groups):
    faces = [(2, t) for tags in groups.values() for t in tags]
    return [abs(tag) for _, tag in gmsh.model.getBoundary(faces, combined=True, oriented=False)]


def _size_field(gap_tags, size_gap, size_max, reach):
    curves = sorted({abs(t) for _, t in gmsh.model.getBoundary([(2, t) for t in gap_tags], combined=False, oriented=False)})
    dist = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist, "CurvesList", curves)
    gmsh.model.mesh.field.setNumber(dist, "Sampling", 600)
    thr = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thr, "InField", dist)
    gmsh.model.mesh.field.setNumber(thr, "SizeMin", size_gap)
    gmsh.model.mesh.field.setNumber(thr, "SizeMax", size_max)
    gmsh.model.mesh.field.setNumber(thr, "DistMin", size_gap)
    gmsh.model.mesh.field.setNumber(thr, "DistMax", reach)
    gmsh.model.mesh.field.setAsBackgroundMesh(thr)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeMax", size_max)


def mesh_part(params, part, out, verbose=False):
    mesh = params.get("mesh", {})
    gmsh.initialize(readConfigFiles=False)
    try:
        gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
        gmsh.option.setNumber("General.Verbosity", 2)
        gmsh.option.setNumber("Geometry.Tolerance", 1e-7)
        gmsh.model.add("section")
        if part["kind"] == "radial":
            named, regions, info = radial.build(params)
            groups = fragment(named)
            gap_tags = [t for name, tags in groups.items() if name.startswith("gap_") for t in tags]
            g_min = min(g["r2"] - g["r1"] for g in info["gaps"])
            outer = [t for t in _boundary(groups) if _on_circle(t, info["outer_radius"])]
            boundaries = {"outer": outer}
            conditions = {"outer": "zero"}
            depth = params["stack_length"]
            geometry = {"kind": "radial", "outer_radius": info["outer_radius"], "gaps": info["gaps"]}
            periodic = None
        else:
            k = int(part["slice"])
            named, regions, frame = axial.build(params, k)
            groups = fragment(named)
            gap_tags = [t for name, tags in groups.items() if name.startswith("gap_") for t in tags]
            g_min = min(g["y1"] - g["y0"] for g in frame["gaps"])
            W = frame["width"]
            edges = _boundary(groups)
            tol = 1e-6 * max(W, 1.0)

            def on(axis, value):
                found = []
                for tag in edges:
                    box = gmsh.model.getBoundingBox(1, tag)
                    lo, hi = (box[0], box[3]) if axis == "x" else (box[1], box[4])
                    if abs(lo - value) < tol and abs(hi - value) < tol:
                        found.append(tag)
                return found
            left = sorted(on("x", 0.0), key=lambda t: gmsh.model.getBoundingBox(1, t)[1])
            right = sorted(on("x", W), key=lambda t: gmsh.model.getBoundingBox(1, t)[1])
            if len(left) != len(right):
                raise RuntimeError(f"Periodic boundaries do not match: {len(left)} curves at x = 0, {len(right)} at x = W.")
            boundaries = {"bottom": on("y", frame["bottom"]), "top": on("y", frame["top"]), "left": left, "right": right}
            conditions = {"bottom": "zero", "top": "zero", "right": {"periodic": "left", "dx": W}}
            depth = frame["depth"]
            geometry = dict(frame, kind="axial", slice=k)
            periodic = (right, left, W)
        for name, tags in sorted(groups.items()):
            gmsh.model.setPhysicalName(2, gmsh.model.addPhysicalGroup(2, tags), name)
        for name, tags in boundaries.items():
            if tags:
                gmsh.model.setPhysicalName(1, gmsh.model.addPhysicalGroup(1, tags), name)
        if periodic:
            right, left, W = periodic
            gmsh.model.mesh.setPeriodic(1, right, left, [1, 0, 0, W, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
        size_gap = mesh.get("gap_cell") or g_min / 2.0
        size_max = mesh.get("size_max", 2.5)
        _size_field(gap_tags, size_gap, size_max, mesh.get("reach", 8.0))
        gmsh.model.mesh.generate(2)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.SaveAll", 0)
        gmsh.write(out)
        for name, tags in groups.items():
            if name in regions:
                regions[name]["area_mm2"] = sum(occ.getMass(2, t) for t in tags)
        regions = {k: v for k, v in regions.items() if k in groups}
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        _, tri_tags, _ = gmsh.model.mesh.getElements(2)
        meta = {"units": "mm", "part": part, "geometry": geometry, "regions": regions, "boundaries": conditions,
                "stack_length_mm": depth, "rotor_angle_deg": params.get("rotor_angle_deg", 0.0),
                "mesh": {"nodes": len(node_tags), "elements": sum(len(t) for t in tri_tags)}}
    finally:
        gmsh.finalize()
    with open(os.path.splitext(out)[0] + ".regions.json", "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", required=True)
    ap.add_argument("--part", choices=("radial", "axial"), default="radial")
    ap.add_argument("--slice", type=int, default=0)
    ap.add_argument("--out", default="section.msh")
    args = ap.parse_args(argv)
    with open(args.params) as f:
        params = json.load(f)
    meta = mesh_part(params, {"kind": args.part, "slice": args.slice}, args.out, verbose=True)
    print(f"Mesh: {meta['mesh']['nodes']} nodes, {meta['mesh']['elements']} triangles -> {args.out}")


if __name__ == "__main__":
    sys.exit(main())
