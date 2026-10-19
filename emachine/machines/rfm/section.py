"""
2D cross-section mesher of a radial flux surface PM machine (inner rotor), the whole 360 degrees.

    python -m emachine.machines.rfm.section --params section_parameters.json --out section.msh

The rotor parts are turned to the rotor angle before meshing, so every rotor position is one
conforming mesh (no sliding interface). Regions (physical groups): stator_core, coil_<slot>_<half>,
gap_stator and gap_rotor (the air gap, split at its middle radius), magnet_<j>, rotor_air,
rotor_core, shaft; the outer boundary of the stator is "outer". A <out>.regions.json next to the
mesh describes every region (kind, side, area; phase and sign of coil sides; magnetisation of
magnets) for the solver.

Lengths in millimetres; angles in degrees from the x axis, counter-clockwise. Slot k is centred at
k * 360 / slots; coil side half 0 lies on its clockwise side, half 1 on its counter-clockwise side.
Magnet j is centred at rotor_offset + rotor_angle + j * 180 / p and is a north pole (magnetised
outwards) for even j.
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
    """Ring sector r0..r1 between two angles (degrees), as a polygon-free OCC face."""
    a0, a1 = math.radians(start_deg), math.radians(start_deg + span_deg)
    pts = [occ.addPoint(r0 * math.cos(a0), r0 * math.sin(a0), 0), occ.addPoint(r1 * math.cos(a0), r1 * math.sin(a0), 0),
           occ.addPoint(r1 * math.cos(a1), r1 * math.sin(a1), 0), occ.addPoint(r0 * math.cos(a1), r0 * math.sin(a1), 0)]
    centre = occ.addPoint(0, 0, 0)
    curves = [occ.addLine(pts[0], pts[1]), occ.addCircleArc(pts[1], centre, pts[2]),
              occ.addLine(pts[2], pts[3]), occ.addCircleArc(pts[3], centre, pts[0])]
    face = occ.addPlaneSurface([occ.addCurveLoop(curves)])
    occ.remove([(0, centre)])
    return face


def slot_half(r0, r1, width, angle_deg, half):
    """Half of a parallel-sided slot centred at angle, between the radii r0 (bore) and r1 (half 0:
    clockwise side). The slot opens onto the bore circle exactly."""
    y0, y1 = (-width / 2, 0.0) if half == 0 else (0.0, width / 2)
    box = occ.addRectangle(r0 - width, y0, 0, r1 - r0 + width, y1 - y0)
    out, _ = occ.intersect([(2, box)], [(2, annulus(r0, r1))])
    face = out[0][1]
    occ.rotate([(2, face)], 0, 0, 0, 0, 0, 1, math.radians(angle_deg))
    return face


def build(p):
    """Builds the faces; returns {region name: [face tags]} after fragmenting, and the region description."""
    q, pp = int(p["slots"]), int(p["pole_pairs"])
    ro, rs, depth, w = p["outer_radius"], p["bore_radius"], p["slot_depth"], p["slot_width"]
    gap, hm = p["air_gap"], p["magnet_thickness"]
    rr = rs - gap
    rm = rs - gap / 2
    shaft = p["shaft_radius"]
    turn = p.get("rotor_offset_deg", 0.0) + p.get("rotor_angle_deg", 0.0)

    named = []                                   # (name, face) in the order of priority
    for side in p["sides"]:
        slot, half = side[:2]
        named.append((f"coil_{slot}_{half}", slot_half(rs, rs + depth, w, slot * 360.0 / q, half)))
    stator = annulus(rs, ro)
    named.append(("gap_stator", annulus(rm, rs)))
    named.append(("gap_rotor", annulus(rr, rm)))
    pole_deg = 180.0 / pp
    span = p["magnet_arc_ratio"] * pole_deg
    for j in range(2 * pp):
        centre = turn + j * pole_deg
        named.append((f"magnet_{j}", ring_sector(rr - hm, rr, centre - span / 2, span)))
    named.append(("rotor_air", annulus(rr - hm, rr)))
    named.append(("rotor_core", annulus(shaft, rr - hm)))
    if shaft > 0:
        named.append(("shaft", occ.addDisk(0, 0, 0, shaft, shaft)))
    named.append(("stator_core", stator))

    tools = [(2, f) for _, f in named]
    _, frag_map = occ.fragment(tools[:1], tools[1:])
    occ.synchronize()
    owner = {}
    for (name, _), children in zip(named, frag_map):
        for dim, tag in children:
            if dim == 2 and tag not in owner:
                owner[tag] = name              # earlier entries win: coils and magnets cut out of cores and air
    groups = {}
    for tag, name in owner.items():
        groups.setdefault(name, []).append(tag)

    regions = {}
    for side in p["sides"]:
        slot, half, phase, sign = side[:4]
        # share: part of the coil side in this half of the slot (0.5 for a single-layer side that fills the slot)
        regions[f"coil_{slot}_{half}"] = {"kind": "coil", "side": "stator", "slot": slot, "half": half,
                                          "phase": phase, "sign": sign, "share": side[4] if len(side) > 4 else 1.0}
    for j in range(2 * pp):
        centre = turn + j * pole_deg
        regions[f"magnet_{j}"] = {"kind": "magnet", "side": "rotor", "centre_deg": centre,
                                  "direction": 1.0 if j % 2 == 0 else -1.0}
    regions.update({"gap_stator": {"kind": "air", "side": "stator", "gap": True},
                    "gap_rotor": {"kind": "air", "side": "rotor", "gap": True},
                    "rotor_air": {"kind": "air", "side": "rotor"}, "rotor_core": {"kind": "core", "side": "rotor"},
                    "shaft": {"kind": "air", "side": "rotor"}, "stator_core": {"kind": "core", "side": "stator"}})
    for name, tags in groups.items():
        regions[name]["area_mm2"] = sum(occ.getMass(2, t) for t in tags)
    regions = {k: v for k, v in regions.items() if k in groups}
    return groups, regions, {"r_rotor": rr, "r_stator": rs, "r_middle": rm, "outer_radius": ro}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", default="section.msh")
    args = ap.parse_args(argv)
    with open(args.params) as f:
        params = json.load(f)
    p, mesh = params["rfm"], params.get("mesh", {})
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.option.setNumber("General.Verbosity", 2)
    gmsh.model.add("section")
    groups, regions, radii = build(p)
    for name, tags in sorted(groups.items()):
        gmsh.model.setPhysicalName(2, gmsh.model.addPhysicalGroup(2, tags), name)
    outer = [tag for _, tag in gmsh.model.getBoundary([(2, t) for tags in groups.values() for t in tags],
                                                      combined=True, oriented=False)
             if _on_circle(tag, radii["outer_radius"])]
    gmsh.model.setPhysicalName(1, gmsh.model.addPhysicalGroup(1, outer), "outer")

    gap = radii["r_stator"] - radii["r_rotor"]
    gap_cell = mesh.get("gap_cell") or gap / 2.0
    size_max = mesh.get("size_max", 3.0)
    gap_curves = [tag for _, tag in gmsh.model.getBoundary([(2, t) for t in groups["gap_rotor"] + groups["gap_stator"]],
                                                           combined=False, oriented=False)]
    dist = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist, "CurvesList", sorted({abs(c) for c in gap_curves}))
    gmsh.model.mesh.field.setNumber(dist, "Sampling", 400)
    thr = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thr, "InField", dist)
    gmsh.model.mesh.field.setNumber(thr, "SizeMin", gap_cell)
    gmsh.model.mesh.field.setNumber(thr, "SizeMax", size_max)
    gmsh.model.mesh.field.setNumber(thr, "DistMin", gap)
    gmsh.model.mesh.field.setNumber(thr, "DistMax", 10 * gap + 3.0)
    gmsh.model.mesh.field.setAsBackgroundMesh(thr)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeMax", size_max)
    gmsh.model.mesh.generate(2)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.SaveAll", 0)
    gmsh.write(args.out)
    node_tags, _, _ = gmsh.model.mesh.getNodes()
    _, tri_tags, _ = gmsh.model.mesh.getElements(2)
    meta = {"units": "mm", "regions": regions, "radii": radii, "parameters": params,
            "mesh": {"nodes": len(node_tags), "elements": sum(len(t) for t in tri_tags)},
            "sector": {"periodicity": 1}, "rotor_angle_deg": p.get("rotor_angle_deg", 0.0),
            "stack_length_mm": p["stack_length"],
            "rotor_eddy_width_mm": [p["rotor_core_thickness"], p["rotor_core_thickness"], p["magnet_width"]]}
    with open(os.path.splitext(args.out)[0] + ".regions.json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"Mesh: {len(node_tags)} nodes, {meta['mesh']['elements']} triangles -> {args.out}")
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
