"""
TFM sector mesher for Elmer: parametric geometry, periodic sector and sliding air-gap interface.

Geometry source (pick one)
    --params examples/params/motor.json   Build the machine from parameters. The file mirrors the Onshape
                          dialogs of "TFM stator" and "TFM rotor" (see examples/params/motor.json).
    --demo                Same, with the default values of the two Onshape features.
    --step machine.step   Use a STEP export of the whole machine instead.

Output
    A Gmsh .msh file (format 2.2, readable by ElmerGrid) of one periodic sector, with
      - a rotor domain and a stator domain that share no mesh across the air gap;
      - two coincident "sliding" surfaces in the middle of the gap carrying the same
        structured node grid, ready for an Elmer mortar boundary;
      - matching meshes on the two cut planes, ready for periodic boundaries;
      - named physical groups for every material region and boundary.
    A .regions.json file next to it describing the sector and every region (material kind,
    magnetisation angles), for setting up the solver.

Conventions
    Machine axis = Z, stack centred on Z = 0, lengths in millimetres (scale by 0.001 for Elmer).
    The stator core at angle 0 faces a rotor north pole at rotor angle 0.

Supported by --params: U-core, U-core with I-bridge, claw-pole and toothed-ring (review paper,
Fig. 17) stators (inner or outer), and surface, Halbach, flux-concentrating and axial rotors
(inrunner or outrunner). C-, E- and Z-cores are built with --stator-only. Shafts and end caps
need the --step route.

Examples
    emachine mesh --demo --gui
    emachine mesh --params examples/params/motor.json --out motor.msh --gui
"""

import argparse
import copy
import json
import math
import os
import sys

import gmsh

from .parameters import DEFAULTS, merged
from .preview import show_window, write_preview
from .rotors import build_rotor, eddy_widths
from .shapes import occ, ring_sector, slug
from .stators import build_stator

# ----------------------------------------------------------------------------- STEP input

def import_step(path):
    """Returns ([(3, tag), ...], [name, ...]) for every solid in the STEP file."""
    gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
    gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
    shapes = occ.importShapes(path)
    occ.synchronize()
    parts = [dt for dt in shapes if dt[0] == 3]
    names = [slug(gmsh.model.getEntityName(3, tag)) for _, tag in parts]
    return parts, names


# ----------------------------------------------------------------------------- sector pipeline

def surface_point(tag):
    """A point on the underlying surface of face `tag` (parametric midpoint)."""
    lo, hi = gmsh.model.getParametrizationBounds(2, tag)
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    return gmsh.model.getValue(2, tag, mid)


def rotate_z(p, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (c * p[0] - s * p[1], s * p[0] + c * p[1], p[2])


def split_domain(domain_tag, parts, names, marker=None, marker_suffix=""):
    """
    Keeps what lies inside the domain solid and makes everything conformal.
    Returns {group name: [volume tags]}, with the left-over volume as 'air'.
    If a marker solid is given, the mesh also follows its faces, and every piece inside
    it is put in a separate group whose name carries marker_suffix.
    """
    # One boolean per part: the name of every piece is then certain, also when parts touch.
    inside, inside_names = [], []
    for part, name in zip(parts, names):
        try:
            pieces, _ = occ.intersect(occ.copy([part]), [(3, domain_tag)], removeObject=True, removeTool=False)
        except Exception:
            pieces = []
        for dt in pieces:
            if dt[0] == 3:
                inside.append(dt)
                inside_names.append(name)

    if not inside and marker is None:
        occ.synchronize()
        return {"air": [domain_tag]}

    tools = inside + ([(3, marker)] if marker is not None else [])
    _, frag_map = occ.fragment([(3, domain_tag)], tools)
    occ.synchronize()
    marked = set()
    if marker is not None:
        marked = {tag for dim, tag in frag_map[-1] if dim == 3}
    owner = {}
    for i, children in enumerate(frag_map[1:1 + len(inside)]):
        for dim, tag in children:
            if dim != 3:
                continue
            if tag in owner and owner[tag] != inside_names[i]:
                print(f"  warning: parts '{owner[tag]}' and '{inside_names[i]}' overlap; "
                      f"the overlap is kept as '{owner[tag]}'.", file=sys.stderr)
                continue
            owner[tag] = inside_names[i]
    groups = {}
    for tag, name in owner.items():
        groups.setdefault(name + (marker_suffix if tag in marked else ""), []).append(tag)
    for dim, tag in frag_map[0]:
        if dim == 3 and tag not in owner:
            groups.setdefault("air" + (marker_suffix if tag in marked else ""), []).append(tag)
    return groups


def classify_boundary(volume_tags, geo, tol):
    """Sorts the outer faces of a domain by the underlying surface they lie on."""
    faces = gmsh.model.getBoundary([(3, t) for t in volume_tags], combined=True, oriented=False)
    found = {"sliding": [], "periodic_a": [], "periodic_b": [], "outer": []}
    # Each cut plane is a half plane: normal n, and direction d pointing away from the axis.
    da = (math.cos(geo["theta0"]), math.sin(geo["theta0"]))
    db = (math.cos(geo["theta1"]), math.sin(geo["theta1"]))
    na = (-da[1], da[0])
    nb = (-db[1], db[0])
    for _, tag in faces:
        kind = gmsh.model.getType(2, tag)
        x, y, z = surface_point(tag)
        r = math.hypot(x, y)
        if kind == "Cylinder" and abs(r - geo["r_slide"]) < tol:
            found["sliding"].append(tag)
        elif kind == "Plane" and abs(abs(z) - geo["z_max"]) < tol:
            found["outer"].append(tag)
        elif kind == "Plane" and abs(na[0] * x + na[1] * y) < tol and da[0] * x + da[1] * y > 0:
            found["periodic_a"].append(tag)
        elif kind == "Plane" and abs(nb[0] * x + nb[1] * y) < tol and db[0] * x + db[1] * y > 0:
            found["periodic_b"].append(tag)
        else:
            found["outer"].append(tag)
    return found


def link_periodic(faces_a, faces_b, opening, tol):
    """Makes each face on plane B a periodic copy of its image on plane A. Returns the pair count."""
    c, s = math.cos(opening), math.sin(opening)
    affine = [c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    centres_b = {tag: occ.getCenterOfMass(2, tag) for tag in faces_b}
    pairs = 0
    for fa in faces_a:
        target = rotate_z(occ.getCenterOfMass(2, fa), opening)
        best, best_d = None, tol
        for fb, cb in centres_b.items():
            d = math.dist(target, cb)
            if d < best_d:
                best, best_d = fb, d
        if best is None:
            print(f"  warning: no periodic partner for face {fa}", file=sys.stderr)
            continue
        del centres_b[best]
        gmsh.model.mesh.setPeriodic(2, [best], [fa], affine)
        pairs += 1
    return pairs


def structure_sliding(face, n_theta, n_z):
    """Structured n_theta x n_z grid on a sliding face. Returns False if the face is not a 4-sided patch."""
    curves = gmsh.model.getBoundary([(2, face)], combined=False, oriented=False)
    if len(curves) != 4:
        return False
    for _, tag in curves:
        kind = gmsh.model.getType(1, tag)
        gmsh.model.mesh.setTransfiniteCurve(abs(tag), (n_z if kind == "Line" else n_theta) + 1)
    gmsh.model.mesh.setTransfiniteSurface(face)
    return True


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--params", help="JSON parameter file (see examples/params/motor.json)")
    src.add_argument("--demo", action="store_true", help="built-in defaults of the Onshape features")
    src.add_argument("--step", help="STEP export of the whole machine")
    ap.add_argument("--out", default="tfm_sector.msh")
    ap.add_argument("--no-periodic", action="store_true", help="do not force matching meshes on the cut planes")
    ap.add_argument("--no-mesh", action="store_true", help="build and tag the geometry only")
    ap.add_argument("--stator-only", action="store_true",
                    help="with --params: build the stator ring only, print its volumes and write it to --out "
                         "as a STEP or BREP file. Works for all six core types.")
    ap.add_argument("--gui", action="store_true", help="open the Gmsh window showing the meshed parts")
    ap.add_argument("--preview", help="save a picture (SVG) of the meshed parts, without opening a window")
    ap.add_argument("--show-air", action="store_true", help="also draw the air regions in --gui and --preview")
    step = ap.add_argument_group("only with --step")
    step.add_argument("--pole-pairs", type=int, default=16, help="periodicity of the machine")
    step.add_argument("--rotor-radius", type=float, default=59.0, help="rotor surface at the air gap, mm")
    step.add_argument("--stator-radius", type=float, default=60.0, help="stator surface at the air gap, mm")
    step.add_argument("--outrunner", action="store_true", help="rotor is outside the stator")
    args = ap.parse_args()

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.option.setNumber("General.Verbosity", 2)
    gmsh.model.add("tfm_sector")

    meta = {"units": "mm", "regions": {}}
    mp = copy.deepcopy(DEFAULTS["mesh"])
    if args.step:
        parts, names = import_step(args.step)
        if not parts:
            sys.exit("No solids found in the STEP file.")
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1)
        periodicity = args.pole_pairs
        outrunner = args.outrunner
        rotor_r, stator_r = args.rotor_radius, args.stator_radius
        r_parts_min = 0.5 * min(rotor_r, stator_r)
        r_parts_max = max(abs(xmin), abs(xmax), abs(ymin), abs(ymax))
        half_len = max(abs(zmin), abs(zmax))
        start_default = -math.pi / (2 * periodicity)
    else:
        user = {}
        if args.params:
            with open(args.params) as f:
                user = json.load(f)
        params = merged(DEFAULTS, user)
        mp = params["mesh"]
        s_parts, s_names, s_info = build_stator(params["stator"])
        if args.stator_only:
            occ.synchronize()
            for name in sorted(set(s_names)):
                tags = [dt[1] for dt, n in zip(s_parts, s_names) if n == name]
                print(f"  volume  {name:<20s} {len(tags):3d} solids  {sum(occ.getMass(3, t) for t in tags):12.1f} mm^3")
            if os.path.splitext(args.out)[1].lower() not in (".step", ".stp", ".brep"):
                sys.exit("--stator-only writes a .step or .brep file: set --out accordingly.")
            gmsh.write(args.out)
            print(f"Stator ring ({params['stator']['core_type']}) -> {args.out}")
            gmsh.finalize()
            return
        if not s_info["analysable"]:
            sys.exit(f"The '{params['stator']['core_type']}' core carries the rotor inside the stator or has two coils. "
                     "It can be built with --stator-only, but not meshed for analysis yet (ticket B02).")
        r_parts, r_names, r_info = build_rotor(params["rotor"], math.radians(mp["rotor_angle_deg"]))
        occ.synchronize()
        parts, names = s_parts + r_parts, s_names + r_names
        outrunner = r_info["outrunner"]
        if outrunner != bool(params["stator"]["inner_stator"]):
            sys.exit("An outrunner needs stator.inner_stator = true, and an inrunner needs it false.")
        rotor_r, stator_r = r_info["gap_radius"], s_info["gap_radius"]
        if (rotor_r - stator_r) * (1 if outrunner else -1) <= 0:
            sys.exit(f"No air gap: rotor surface radius {rotor_r:g}, stator surface radius {stator_r:g}.")
        periodicity = math.gcd(s_info["repeats"], r_info["pole_pairs"])
        r_parts_min = min(s_info["r_min"], r_info["r_min"])
        r_parts_max = max(s_info["r_max"], r_info["r_max"])
        half_len = max(s_info["half_width"], r_info["half_stack"])
        start_default = -s_info["pitch"] / 2
        meta["parameters"] = params
        meta["rotor_rows"] = r_info["rows"]
        meta["rotor_eddy_width_mm"] = [float(w) * 1000.0 for w in eddy_widths(params["rotor"])]
        meta["coil"] = s_info["coil"]
        meta["regions"].update(r_info["magnets"])

        # ---- design checks that matter for the analysis
        if s_info["pole_pairs"] != r_info["pole_pairs"]:
            print(f"  WARNING: the stator has {2 * s_info['pole_pairs']} poles but the rotor has "
                  f"{2 * r_info['pole_pairs']}. A transverse flux phase needs equal pole counts. "
                  f"The model only repeats {periodicity} times, so the sector is "
                  f"{360 / periodicity:g} deg.", file=sys.stderr)
        rows = r_info["rows"]
        staggered = s_info["core_type"] == "tr" and params["stator"]["ring_staggered_teeth"]
        if (s_info["core_type"] in ("u", "ui", "tr") and not staggered and len(rows) == 1
                and rows[0]["z1"] - rows[0]["z0"] > params["stator"]["slot_width"]):
            print("  WARNING: one magnet row spans both legs of the U-core, so both legs see the same "
                  "pole and the flux through the coil cancels. Use two rows with alternate polarity "
                  "and a gap equal to the slot width, or staggered teeth (toothed ring).", file=sys.stderr)
        if staggered and len(rows) == 2 and params["rotor"]["alternate_rows"]:
            print("  WARNING: staggered teeth with two rows of alternate polarity: both walls see the same "
                  "pole again and the flux through the coil cancels. Use one magnet row.", file=sys.stderr)
        arc = s_info["core_inner_arc"]
        if arc is not None and s_info["core_thickness"] > arc and s_info["core_type"] not in ("cp", "tr"):
            print(f"  WARNING: neighbouring stator cores overlap at their inner end "
                  f"(core thickness {s_info['core_thickness']:.2f} mm, room {arc:.2f} mm). "
                  "The overlap is merged into one core region.", file=sys.stderr)

    print(f"Input: {len(parts)} solids, part names: {sorted(set(names))}")

    gap = abs(rotor_r - stator_r)
    gap_cell = mp["gap_cell"] or max(gap, 0.2)
    opening = 2 * math.pi / periodicity
    start = math.radians(mp["sector_start_deg"]) if mp["sector_start_deg"] is not None else start_default
    geo = {
        "r_slide": 0.5 * (rotor_r + stator_r),
        "r_in": mp["inner_radius"] or 0.5 * r_parts_min,
        "r_out": r_parts_max + (mp["outer_margin"] or max(10.0, 0.25 * r_parts_max)),
        "z_max": half_len + (mp["axial_margin"] or max(10.0, half_len)),
        "theta0": start,
        "theta1": start + opening,
    }
    if not 0 < geo["r_in"] < geo["r_slide"] < geo["r_out"]:
        sys.exit("Radii are inconsistent: need 0 < inner radius < sliding radius < outer radius.")
    if opening > math.pi + 1e-9:
        sys.exit("The periodic sector is larger than 180 deg, which this script does not cut.")
    tol = 1e-4 * geo["r_out"]
    n_theta = max(8, math.ceil(geo["r_slide"] * opening / gap_cell))
    multiple = max(1, int(mp.get("sliding_theta_multiple") or 1))
    n_theta = multiple * max(1, round(n_theta / multiple))
    n_z = max(8, math.ceil(2 * geo["z_max"] / gap_cell))
    print("Sector: {:g} deg starting at {:.3f} deg; air gap {:.3f} mm, sliding radius {:.3f} mm; "
          "r {:.2f}..{:.2f} mm, |z| <= {:.2f} mm".format(
              math.degrees(opening), math.degrees(start), gap, geo["r_slide"],
              geo["r_in"], geo["r_out"], geo["z_max"]))

    # ---- two separate domains: nothing is shared across the sliding radius
    z0, z1 = -geo["z_max"], geo["z_max"]
    inner_dom = ring_sector(geo["r_in"], geo["r_slide"], z0, z1, start, opening)
    outer_dom = ring_sector(geo["r_slide"], geo["r_out"], z0, z1, start, opening)
    occ.synchronize()
    # The coil current is later applied as an equivalent magnetisation. That source also lives in the
    # slab between the coil and the model boundary on the side away from the air gap, so the mesh
    # must follow the faces of that slab ("coil shell").
    shell = [None, None]  # marker solid for the inner and outer domain
    coil = meta.get("coil")
    if coil:
        zc = coil["half_height_mm"]
        if coil["shell"] == "inward":
            shell[0] = ring_sector(geo["r_in"], coil["r0_mm"], -zc, zc, start, opening)
        else:
            shell[1] = ring_sector(coil["r1_mm"], geo["r_out"], -zc, zc, start, opening)
        occ.synchronize()
    inner_groups = split_domain(inner_dom, parts, names, shell[0], "_coilshell")
    outer_groups = split_domain(outer_dom, parts, names, shell[1], "_coilshell")
    occ.remove(parts, recursive=True)
    occ.synchronize()

    rotor_groups, stator_groups = (outer_groups, inner_groups) if outrunner else (inner_groups, outer_groups)
    sides = {"rotor": rotor_groups, "stator": stator_groups}
    crossing = [n for n in rotor_groups if n != "air" and n in stator_groups]
    if crossing:
        print(f"  warning: parts named {crossing} exist on both sides of the sliding radius.", file=sys.stderr)

    # ---- physical groups
    boundaries, labels = {}, {}
    for side, groups in sides.items():
        for name, tags in sorted(groups.items()):
            if not tags:
                continue
            label = name if name.startswith(side + "_") else f"{side}_{name}"
            pg = gmsh.model.addPhysicalGroup(3, tags)
            gmsh.model.setPhysicalName(3, pg, label)
            labels[(pg, label)] = tags
            volume = sum(occ.getMass(3, t) for t in tags)
            print(f"  volume  {label:<44s} {len(tags):3d} solids  {volume:12.1f} mm^3")
            base = name[:-len("_coilshell")] if name.endswith("_coilshell") else name
            region = dict(meta["regions"].pop(name, {}))
            if not region:
                region["kind"] = ("air" if base == "air" else "coil" if "coil" in base else
                                  "magnet" if ("magnet" in base and "non_magnetic" not in base) else "core")
            region.update({"side": side, "volume_mm3": volume, "coil_shell": base != name})
            meta["regions"][label] = region
        all_tags = [t for tags in groups.values() for t in tags]
        boundaries[side] = classify_boundary(all_tags, geo, tol)
        for kind, tags in boundaries[side].items():
            if not tags:
                continue
            label = f"{kind}_{side}"
            pg = gmsh.model.addPhysicalGroup(2, tags)
            gmsh.model.setPhysicalName(2, pg, label)
            print(f"  surface {label:<44s} {len(tags):3d} faces")
    meta["regions"] = {k: v for k, v in meta["regions"].items() if "side" in v}

    # ---- mesh constraints
    structured = True
    for side in sides:
        sliding = boundaries[side]["sliding"]
        if len(sliding) != 1 or not structure_sliding(sliding[0], n_theta, n_z):
            structured = False
            print(f"  warning: sliding surface of the {side} is not one 4-sided patch "
                  f"({len(sliding)} faces); it is meshed unstructured.", file=sys.stderr)
        if not args.no_periodic:
            n = link_periodic(boundaries[side]["periodic_a"], boundaries[side]["periodic_b"], opening, 10 * tol)
            print(f"  periodic pairs on the {side}: {n} "
                  f"(A {len(boundaries[side]['periodic_a'])}, B {len(boundaries[side]['periodic_b'])})")

    # Fine near the air gap, coarse far away.
    gap_faces = boundaries["rotor"]["sliding"] + boundaries["stator"]["sliding"]
    dist = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist, "SurfacesList", gap_faces)
    gmsh.model.mesh.field.setNumber(dist, "Sampling", 60)
    thr = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thr, "InField", dist)
    gmsh.model.mesh.field.setNumber(thr, "SizeMin", gap_cell)
    gmsh.model.mesh.field.setNumber(thr, "SizeMax", mp["size_max"])
    gmsh.model.mesh.field.setNumber(thr, "DistMin", 2 * gap_cell)
    gmsh.model.mesh.field.setNumber(thr, "DistMax", max(15.0, 40 * gap_cell))
    gmsh.model.mesh.field.setAsBackgroundMesh(thr)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeMax", mp["size_max"])

    meta["sector"] = {
        "periodicity": periodicity,
        "opening_deg": math.degrees(opening),
        "start_deg": math.degrees(start),
        "outrunner": bool(outrunner),
        "air_gap_mm": gap,
        "sliding_radius_mm": geo["r_slide"],
        "inner_radius_mm": geo["r_in"],
        "outer_radius_mm": geo["r_out"],
        "half_length_mm": geo["z_max"],
        "sliding_cells_theta": n_theta if structured else None,
        "sliding_cells_z": n_z if structured else None,
        "sliding_step_deg": math.degrees(opening) / n_theta if structured else None,
    }

    if not args.no_mesh:
        gmsh.model.mesh.generate(3)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.SaveAll", 0)
        gmsh.write(args.out)
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        _, tet_tags, _ = gmsh.model.mesh.getElements(3)
        meta["mesh"] = {"nodes": len(node_tags), "volume_elements": sum(len(t) for t in tet_tags)}
        print(f"Mesh: {len(node_tags)} nodes, {meta['mesh']['volume_elements']} volume elements -> {args.out}")
        if structured:
            print(f"  sliding surfaces: {n_theta} x {n_z} cells, "
                  f"{math.degrees(opening) / n_theta:.4f} deg per step")
        meta_file = os.path.splitext(args.out)[0] + ".regions.json"
        with open(meta_file, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"Region description -> {meta_file}")
        if args.preview:
            write_preview(labels, args.show_air, args.preview, start + opening / 2)
        if args.gui:
            show_window(labels, args.show_air)
    elif args.gui:
        gmsh.fltk.run()
    gmsh.finalize()


if __name__ == "__main__":
    main()
