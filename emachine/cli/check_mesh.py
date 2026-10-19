"""Checks a mesh from emachine mesh: sliding-surface match, periodic match, element quality."""
import math
import sys

import gmsh
import numpy as np

import json
import os


def main(argv=None):
    """Checks the mesh file argv[0] (default: the command-line argument)."""
    path = (argv or sys.argv[1:])[0]
    with open(os.path.splitext(path)[0] + ".regions.json") as f:
        sector = json.load(f)["sector"]
    opening = math.radians(sector["opening_deg"])
    print(f"Sector {sector['opening_deg']:g} deg, air gap {sector['air_gap_mm']:g} mm, sliding radius {sector['sliding_radius_mm']:g} mm")

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.open(path)

    groups = {gmsh.model.getPhysicalName(d, t): (d, t) for d, t in gmsh.model.getPhysicalGroups()}


    def nodes_of(name):
        d, t = groups[name]
        tags, coords = gmsh.model.mesh.getNodesForPhysicalGroup(d, t)
        return np.array(tags), np.array(coords).reshape(-1, 3)


    def match(a, b, tol=1e-6):
        """Largest distance from each point of a to its nearest point of b, and the number matched."""
        from collections import defaultdict
        grid = defaultdict(list)
        cell = 1e-3
        for i, p in enumerate(b):
            grid[tuple(np.round(p / cell).astype(int))].append(i)
        worst, hits = 0.0, 0
        for p in a:
            key = np.round(p / cell).astype(int)
            best = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for j in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                            d = np.linalg.norm(b[j] - p)
                            if best is None or d < best:
                                best = d
            if best is not None and best < tol:
                hits += 1
            worst = max(worst, best if best is not None else float("inf"))
        return worst, hits


    print("Physical groups:")
    for name, (d, t) in sorted(groups.items(), key=lambda kv: (kv[1][0], kv[0])):
        ents = gmsh.model.getEntitiesForPhysicalGroup(d, t)
        n = 0
        for e in ents:
            _, tags, _ = gmsh.model.mesh.getElements(d, e)
            n += sum(len(x) for x in tags)
        print(f"  dim {d}  {name:<32s} {n:8d} elements")

    rt, rc = nodes_of("sliding_rotor")
    st, sc = nodes_of("sliding_stator")
    worst, hits = match(rc, sc)
    shared = len(set(rt.tolist()) & set(st.tolist()))
    radius = np.hypot(rc[:, 0], rc[:, 1])
    print(f"\nSliding surfaces: rotor {len(rt)} nodes, stator {len(st)} nodes")
    print(f"  coincident positions: {hits} of {len(rt)} (largest mismatch {worst:.2e} mm)")
    print(f"  node ids shared between the two sides: {shared} (must be 0 for a sliding interface)")
    print(f"  radius {radius.min():.4f} .. {radius.max():.4f} mm")
    angles = np.unique(np.round(np.degrees(np.arctan2(rc[:, 1], rc[:, 0])), 6))
    levels = np.unique(np.round(rc[:, 2], 6))
    print(f"  grid: {len(angles)} angular lines, step {np.diff(angles).mean():.4f} deg; {len(levels)} axial levels, step {np.diff(levels).mean():.4f} mm")

    c, s = math.cos(opening), math.sin(opening)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    for side in ("rotor", "stator"):
        _, a = nodes_of(f"periodic_a_{side}")
        _, b = nodes_of(f"periodic_b_{side}")
        worst, hits = match(a @ rot.T, b)
        print(f"Periodic planes, {side}: A {len(a)} nodes, B {len(b)} nodes, matched after rotation {hits} (largest mismatch {worst:.2e} mm)")

    _, tets, _ = gmsh.model.mesh.getElements(3)
    all_tets = np.concatenate(tets)
    q = np.array(gmsh.model.mesh.getElementQualities(all_tets.tolist(), "minSICN"))
    print(f"\nTetrahedra: {len(q)}, quality (minSICN) min {q.min():.3f}, 1st percentile {np.percentile(q, 1):.3f}, median {np.median(q):.3f}")
    print(f"  below 0.1: {(q < 0.1).sum()}, below 0.2: {(q < 0.2).sum()}")
    gmsh.finalize()
