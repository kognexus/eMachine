"""
2D meshes of the radial-axial ("raxial") machine with a toroidal winding (T55): the radial section and
the axial slices of the quasi-3D field model.

    python -m emachine.machines.rafm.section --params parts.json --part radial --out radial.msh
    python -m emachine.machines.rafm.section --params parts.json --part axial --slice 1 --out axial1.msh

radial  the cross-section at z = 0, the whole circle: outer rotor ring with the radial magnets, the
        air gap (split at its middle radius), the stator (radial teeth with tips, yoke ring, inner
        teeth), the outer sides of the toroidal coils in the radial slots and their inner (return)
        sides between the inner teeth; the bore is air. Outer boundary "outer" (A = 0).
axial   one slice at radius r_k, unrolled: x = r_k (theta - theta_0) over the whole circumference
        (periodic: boundaries "left" and "right"), y = z from the yoke's mid-plane (boundary
        "bottom", A = 0: by symmetry the flux there runs along the plane) to the outside of the rotor
        disc ("top", A = 0): half the yoke, the axial teeth with tips, the end sides of the coils,
        the axial gap (split), the axial magnets and the disc. theta_0 lies on a tooth, so no slot
        crosses the periodic boundary; magnets that cross it are split.

Lengths in mm. Slot k is centred at k * 360 / Q degrees; the toroidal coil in slot k has phase and
sign of the layout (machines/winding_layout.py toroidal): its outer side carries + sign along +z,
its end side on the +z face - sign along +r (out of the slice plane: x = theta, y = z, x cross y = r),
its inner side - sign. Magnet j is centred at rotor_offset + rotor_angle + j * 180 / p and shows a
north pole to the stator for even j.
"""

import argparse
import json
import math
import os
import sys

import gmsh

occ = gmsh.model.occ


def annulus(r0, r1):
    outer = occ.addDisk(0, 0, 0, r1, r1)
    if r0 <= 0:
        return outer
    inner = occ.addDisk(0, 0, 0, r0, r0)
    out, _ = occ.cut([(2, outer)], [(2, inner)])
    return out[0][1]


def ring_sector(r0, r1, start_deg, span_deg):
    a0, a1 = math.radians(start_deg), math.radians(start_deg + span_deg)
    pts = [occ.addPoint(r0 * math.cos(a0), r0 * math.sin(a0), 0), occ.addPoint(r1 * math.cos(a0), r1 * math.sin(a0), 0),
           occ.addPoint(r1 * math.cos(a1), r1 * math.sin(a1), 0), occ.addPoint(r0 * math.cos(a1), r0 * math.sin(a1), 0)]
    centre = occ.addPoint(0, 0, 0)
    curves = [occ.addLine(pts[0], pts[1]), occ.addCircleArc(pts[1], centre, pts[2]),
              occ.addLine(pts[2], pts[3]), occ.addCircleArc(pts[3], centre, pts[0])]
    face = occ.addPlaneSurface([occ.addCurveLoop(curves)])
    occ.remove([(0, centre)])
    return face


def slot_box(x0, x1, half_width, angle_deg, clip=None):
    """Rectangle x0..x1 (radial) by +-half_width in the frame of a slot, turned to angle_deg; clipped
    to the face `clip` (a copy of it) when given."""
    box = occ.addRectangle(x0, -half_width, 0, x1 - x0, 2 * half_width)
    occ.rotate([(2, box)], 0, 0, 0, 0, 0, 1, math.radians(angle_deg))
    if clip is None:
        return box
    out, _ = occ.intersect([(2, box)], occ.copy([(2, clip)]))
    return out[0][1] if out else None


def fragment_named(named):
    """Fragments the (name, face) list; earlier names win overlaps. Returns {name: [faces]}."""
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
        groups.setdefault(name, []).append(tag)
    return groups


def build_radial(p):
    q, pp = int(p["slots"]), int(p["pole_pairs"])
    R, rm_in, tm = p["outer_radius"], p["magnet_inner_radius"], p["magnet_thickness"]
    Rs, ryo, ryi, rb = p["stator_radius"], p["yoke_outer_radius"], p["yoke_inner_radius"], p["bore_radius"]
    w, b0, t, c, a = p["slot_width"], p["slot_opening"], p["tooth_tip_height"], p["coil_thickness"], p["coil_clearance"]
    cw = w - 2 * a
    turn = p.get("rotor_offset_deg", 0.0) + p.get("rotor_angle_deg", 0.0)
    gap = rm_in - Rs
    stator_ring = annulus(rb, Rs)
    named = []
    for coil in p["coils"]:
        k = coil["slot"]
        angle = k * 360.0 / q
        named.append((f"coil_{k}_out", slot_box(ryo + a, ryo + a + c, cw / 2, angle)))
        named.append((f"coil_{k}_in", slot_box(ryi - a - c, ryi - a, cw / 2, angle)))
    for k in range(q):
        angle = k * 360.0 / q
        for piece in (slot_box(ryo, Rs - t, w / 2, angle, stator_ring), slot_box(Rs - t - 1e-3, Rs + 1.0, b0 / 2, angle, stator_ring),
                      slot_box(rb - 1.0, ryi, w / 2, angle, stator_ring)):
            if piece is not None:
                named.append(("slot_air", piece))
    named.append(("gap_stator", annulus(Rs, Rs + gap / 2)))
    named.append(("gap_rotor", annulus(Rs + gap / 2, rm_in)))
    pole_deg = 180.0 / pp
    span = p["magnet_arc_el_deg"] / pp
    for j in range(2 * pp):
        centre = turn + j * pole_deg
        named.append((f"magnet_{j}", ring_sector(rm_in, rm_in + tm, centre - span / 2, span)))
    named.append(("rotor_air", annulus(rm_in, rm_in + tm)))
    named.append(("rotor_core", annulus(rm_in + tm, R)))
    if rb > 0:
        named.append(("bore", occ.addDisk(0, 0, 0, rb, rb)))
    named.append(("stator_core", stator_ring))
    groups = fragment_named(named)

    regions = {}
    for coil in p["coils"]:
        k = coil["slot"]
        for side, sign in (("out", coil["sign"]), ("in", -coil["sign"])):
            regions[f"coil_{k}_{side}"] = {"kind": "coil", "side": "stator", "slot": k, "phase": coil["phase"], "sign": sign}
    for j in range(2 * pp):
        # north to the stator: magnetised inwards (direction -1 of the radial unit vector)
        regions[f"magnet_{j}"] = {"kind": "magnet", "side": "rotor", "centre_deg": turn + j * pole_deg,
                                  "direction": -1.0 if j % 2 == 0 else 1.0}
    regions.update({"slot_air": {"kind": "air", "side": "stator"}, "bore": {"kind": "air", "side": "stator"},
                    "gap_stator": {"kind": "air", "side": "stator", "gap": True},
                    "gap_rotor": {"kind": "air", "side": "rotor", "gap": True},
                    "rotor_air": {"kind": "air", "side": "rotor"}, "rotor_core": {"kind": "core", "side": "rotor"},
                    "stator_core": {"kind": "core", "side": "stator"}})
    for name, tags in groups.items():
        regions[name]["area_mm2"] = sum(occ.getMass(2, tag) for tag in tags)
    regions = {k: v for k, v in regions.items() if k in groups}
    # Arkkio's torque on the rotor: r_rotor is the rotor side of the gap (outside), r_stator the stator side
    return groups, regions, {"r_rotor": rm_in, "r_stator": Rs, "r_middle": Rs + gap / 2, "outer_radius": R}


def build_axial(p, k_slice):
    q, pp = int(p["slots"]), int(p["pole_pairs"])
    sl = p["slices"][k_slice]
    r = sl["radius"]
    W = 2 * math.pi * r
    theta0 = math.pi / q                                  # on a tooth: no slot crosses x = 0
    hy2, Lc2, L2 = p["yoke_length"] / 2, p["core_length"] / 2, p["axial_length"] / 2
    g, ta = p["air_gap"], p["axial_magnet_thickness"]
    w, b0, t, c, a = p["slot_width"], p["slot_opening"], p["tooth_tip_height"], p["coil_thickness"], p["coil_clearance"]
    cw = w - 2 * a
    turn = p.get("rotor_offset_deg", 0.0) + p.get("rotor_angle_deg", 0.0)

    def x_of(theta_rad):
        return r * ((theta_rad - theta0) % (2 * math.pi))

    def rect(x0, y0, x1, y1):
        return occ.addRectangle(x0, y0, 0, x1 - x0, y1 - y0)

    def wrapped(x0, y0, x1, y1):
        """Rectangle x0..x1 that may run over the periodic boundary: one or two faces."""
        x0 %= W
        x1 = x0 + (x1 - x0 if x1 > x0 else x1 - x0 + W)
        if x1 <= W + 1e-9:
            return [rect(x0, y0, min(x1, W), y1)]
        return [rect(x0, y0, W, y1), rect(0.0, y0, x1 - W, y1)]

    named = []
    for coil in p["coils"]:
        k = coil["slot"]
        xc = x_of(2 * math.pi * k / q)
        named.append((f"coil_{k}_end", rect(xc - cw / 2, hy2 + a, xc + cw / 2, hy2 + a + c)))
    for k in range(q):
        xc = x_of(2 * math.pi * k / q)
        named.append(("slot_air", rect(xc - w / 2, hy2, xc + w / 2, Lc2 - t)))
        named.append(("slot_air", rect(xc - b0 / 2, Lc2 - t - 1e-3, xc + b0 / 2, Lc2)))
    named.append(("gap_stator", rect(0.0, Lc2, W, Lc2 + g / 2)))
    named.append(("gap_rotor", rect(0.0, Lc2 + g / 2, W, Lc2 + g)))
    pole = math.pi / pp
    span = math.radians(p["axial_magnet_arc_el_deg"] / pp)
    magnets = []
    for j in range(2 * pp):
        centre = math.radians(turn) + j * pole
        xc = x_of(centre)
        for face in wrapped(xc - r * span / 2, Lc2 + g, xc + r * span / 2, Lc2 + g + ta):
            magnets.append((f"magnet_{j}", face))
    named += magnets
    named.append(("rotor_air", rect(0.0, Lc2 + g, W, Lc2 + g + ta)))
    named.append(("rotor_core", rect(0.0, Lc2 + g + ta, W, L2)))
    named.append(("stator_core", rect(0.0, 0.0, W, Lc2)))
    groups = fragment_named(named)

    regions = {}
    for coil in p["coils"]:
        regions[f"coil_{coil['slot']}_end"] = {"kind": "coil", "side": "stator", "slot": coil["slot"],
                                               "phase": coil["phase"], "sign": -coil["sign"]}
    for j in range(2 * pp):
        # north to the stator: magnetised towards -z (-y)
        regions[f"magnet_{j}"] = {"kind": "magnet", "side": "rotor", "centre_deg": turn + math.degrees(j * pole),
                                  "magnetization": [0.0, -1.0 if j % 2 == 0 else 1.0]}
    regions.update({"slot_air": {"kind": "air", "side": "stator"},
                    "gap_stator": {"kind": "air", "side": "stator", "gap": True},
                    "gap_rotor": {"kind": "air", "side": "rotor", "gap": True},
                    "rotor_air": {"kind": "air", "side": "rotor"}, "rotor_core": {"kind": "core", "side": "rotor"},
                    "stator_core": {"kind": "core", "side": "stator"}})
    for name, tags in groups.items():
        regions[name]["area_mm2"] = sum(occ.getMass(2, tag) for tag in tags)
    regions = {k: v for k, v in regions.items() if k in groups}
    frame = {"radius": r, "depth": sl["depth"], "width": W, "theta0_rad": theta0, "gap_y0": Lc2, "gap_y1": Lc2 + g,
             "top": L2}
    return groups, regions, frame


def _boundary_curves(groups):
    faces = [(2, t) for tags in groups.values() for t in tags]
    return [tag for _, tag in gmsh.model.getBoundary(faces, combined=True, oriented=False)]


def _curve_box(tag):
    return gmsh.model.getBoundingBox(1, tag)


def mesh_and_write(groups, regions, out, size_gap, size_max, gap_curves_of, boundaries, extra_meta, periodic=None):
    for name, tags in sorted(groups.items()):
        gmsh.model.setPhysicalName(2, gmsh.model.addPhysicalGroup(2, tags), name)
    for name, tags in boundaries.items():
        if tags:
            gmsh.model.setPhysicalName(1, gmsh.model.addPhysicalGroup(1, tags), name)
    if periodic:
        right, left, width = periodic
        gmsh.model.mesh.setPeriodic(1, right, left, [1, 0, 0, width, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
    gap_curves = sorted({abs(c) for c in gap_curves_of})
    dist = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist, "CurvesList", gap_curves)
    gmsh.model.mesh.field.setNumber(dist, "Sampling", 2000)
    thr = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thr, "InField", dist)
    gmsh.model.mesh.field.setNumber(thr, "SizeMin", size_gap)
    gmsh.model.mesh.field.setNumber(thr, "SizeMax", size_max)
    gmsh.model.mesh.field.setNumber(thr, "DistMin", 2 * size_gap)
    gmsh.model.mesh.field.setNumber(thr, "DistMax", 15 * size_gap + 5.0)
    gmsh.model.mesh.field.setAsBackgroundMesh(thr)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeMax", size_max)
    gmsh.model.mesh.generate(2)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.SaveAll", 0)
    gmsh.write(out)
    node_tags, _, _ = gmsh.model.mesh.getNodes()
    _, tri_tags, _ = gmsh.model.mesh.getElements(2)
    meta = dict(extra_meta, regions=regions, mesh={"nodes": len(node_tags), "elements": sum(len(x) for x in tri_tags)})
    with open(os.path.splitext(out)[0] + ".regions.json", "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", required=True)
    ap.add_argument("--part", choices=("radial", "axial"), required=True)
    ap.add_argument("--slice", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    with open(args.params) as f:
        params = json.load(f)
    p, mesh = params["rafm"], params.get("mesh", {})
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.option.setNumber("General.Verbosity", 2)
    gmsh.model.add(args.part)
    size_gap = mesh.get("gap_cell") or p["air_gap"] / 2
    size_max = mesh.get("size_max", 6.0)
    if args.part == "radial":
        groups, regions, radii = build_radial(p)
        outer = [tag for tag in _boundary_curves(groups) if _on_circle(tag, radii["outer_radius"])]
        gap_curves = [tag for _, tag in gmsh.model.getBoundary([(2, t) for t in groups["gap_rotor"] + groups["gap_stator"]],
                                                               combined=False, oriented=False)]
        meta = mesh_and_write(groups, regions, args.out, size_gap, size_max, gap_curves, {"outer": outer},
                              {"part": "radial", "units": "mm", "radii": radii, "parameters": params,
                               "stack_length_mm": p["radial_tooth_length"], "boundaries": {"outer": "zero"}})
    else:
        groups, regions, frame = build_axial(p, args.slice)
        W, top = frame["width"], frame["top"]
        edges = _boundary_curves(groups)
        tol = 1e-6 * max(W, 1.0)

        def on(axis, value):
            out = []
            for tag in edges:
                box = _curve_box(tag)
                lo, hi = (box[0], box[3]) if axis == "x" else (box[1], box[4])
                if abs(lo - value) < tol and abs(hi - value) < tol:
                    out.append(tag)
            return out
        left, right = on("x", 0.0), on("x", W)
        left.sort(key=lambda tag: _curve_box(tag)[1])
        right.sort(key=lambda tag: _curve_box(tag)[1])
        if len(left) != len(right):
            raise SystemExit(f"Periodic boundaries do not match: {len(left)} curves at x = 0, {len(right)} at x = W.")
        gap_curves = [tag for _, tag in gmsh.model.getBoundary([(2, t) for t in groups["gap_rotor"] + groups["gap_stator"]],
                                                               combined=False, oriented=False)]
        meta = mesh_and_write(groups, regions, args.out, size_gap, size_max, gap_curves,
                              {"bottom": on("y", 0.0), "top": on("y", top), "left": left, "right": right},
                              {"part": "axial", "slice": args.slice, "units": "mm", "frame": frame, "parameters": params,
                               "stack_length_mm": frame["depth"],
                               "boundaries": {"bottom": "zero", "top": "zero", "right": {"periodic": "left", "dx": W}}},
                              periodic=(right, left, W))
    print(f"Mesh {args.part}: {meta['mesh']['nodes']} nodes, {meta['mesh']['elements']} triangles -> {args.out}")
    gmsh.finalize()


def _on_circle(tag, radius, tol=1e-6):
    lo, hi = gmsh.model.getParametrizationBounds(1, tag)
    for t in (lo[0], (lo[0] + hi[0]) / 2, hi[0]):
        x, y, _ = gmsh.model.getValue(1, tag, [t])
        if abs(math.hypot(x, y) - radius) > tol * max(radius, 1.0) + 1e-6:
            return False
    return True


if __name__ == "__main__":
    sys.exit(main())
