"""
Sketch of a meshed section as SVG (T59, T64): every triangle filled by the kind of its region, so a
topology can be looked at without ParaView. Radial sections are drawn as they are; axial slices as
unrolled strips (x along the circumference, z up), one under the other.

    svg = sketch(parts)       parts: list of (points (n, 2) in mm, triangles (m, 3), region name per
                              triangle, regions dict of the mesh meta, kind "radial" or "axial")
"""

import math

PHASE = ["#d4a017", "#2e7d32", "#1565c0"]
COLORS = {"stator_core": "#9e9e9e", "rotor_core": "#616161", "air": "#ffffff", "hub": "#e8e0d0", "gap": "#f4f8ff"}


def colour(name, region):
    kind = region.get("kind")
    if kind == "coil":
        base = PHASE[region["phase"] % 3]
        return base if region["sign"] > 0 else _lighter(base)
    if kind == "magnet":
        m = region.get("magnetization") or [region.get("direction", 1.0), 0.0]
        if region.get("remanence_T", 1.2) < 0.8:
            return "#8d6e63" if m[1] + m[0] >= 0 else "#bcaaa4"
        return "#c62828" if _outward(region) > 0 else "#1e88e5"
    if kind == "core":
        return COLORS["stator_core"] if region.get("side") == "stator" else COLORS["rotor_core"]
    if region.get("hub"):
        return COLORS["hub"]
    if region.get("gap") is not None:
        return COLORS["gap"]
    return COLORS["air"]


def _outward(region):
    m = region.get("magnetization")
    if m is None:
        return region.get("direction", 1.0)
    c = region.get("_centre")
    if c is None:
        return m[1]
    if region.get("_axial"):
        return m[1] if abs(m[1]) > abs(m[0]) else m[0]
    r = math.hypot(*c) or 1.0
    radial = (m[0] * c[0] + m[1] * c[1]) / r
    return radial if abs(radial) > 0.3 else (m[0] * -c[1] + m[1] * c[0]) / r


def _lighter(hex_colour, f=0.55):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(v + (255 - v) * f) for v in (r, g, b))


def sketch(parts, title="", width=720):
    blocks, y_off = [], 0.0
    radial = parts[0][4] == "radial"
    if radial:
        pts = parts[0][0]
        extent = max(abs(pts).max(), 1.0) * 1.03
        scale = width / (2 * extent)
        height = width
    else:
        w = max(p[0][:, 0].max() for p in parts)
        scale = width / w
        heights = [(p[0][:, 1].max() - p[0][:, 1].min()) for p in parts]
        height = sum(h * scale + 24 for h in heights)
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height + 30:.0f}' viewBox='0 0 {width} {height + 30:.0f}'>",
           "<rect width='100%' height='100%' fill='white'/>",
           f"<text x='8' y='18' font-family='Helvetica' font-size='14'>{title}</text>"]
    y_cursor = 30.0
    for points, tri, names, regions, kind in parts:
        for name, region in regions.items():
            sel = [i for i, n in enumerate(names) if n == name]
            if not sel:
                continue
            c = points[tri[sel]].reshape(-1, 2).mean(axis=0)
            region["_centre"] = (float(c[0]), float(c[1]))
            region["_axial"] = kind == "axial"
        paths = {}
        for t, n in zip(tri, names):
            region = regions.get(n, {"kind": "air"})
            col = colour(n, region)
            xy = points[t]
            if kind == "radial":
                coords = [(width / 2 + x * scale, 30 + width / 2 - y * scale) for x, y in xy]
            else:
                y0 = points[:, 1].min()
                h = (points[:, 1].max() - y0) * scale
                coords = [(x * scale, y_cursor + h - (y - y0) * scale) for x, y in xy]
            paths.setdefault(col, []).append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in coords) + "Z")
        for col, d in paths.items():
            out.append(f"<path d='{''.join(d)}' fill='{col}' stroke='{col}' stroke-width='0.3'/>")
        if kind != "radial":
            y_cursor += (points[:, 1].max() - points[:, 1].min()) * scale + 24
        for region in regions.values():
            region.pop("_centre", None)
            region.pop("_axial", None)
    out.append("</svg>")
    return "\n".join(out)


def read_msh(path):
    """Points (n, 2), triangles (m, 3) and the physical name of every triangle of a Gmsh 2.2 ASCII file."""
    import numpy as np
    with open(path) as f:
        lines = f.read().splitlines()
    i = lines.index("$PhysicalNames")
    n = int(lines[i + 1])
    names = {}
    for line in lines[i + 2:i + 2 + n]:
        dim, tag, name = line.split(maxsplit=2)
        names[int(tag)] = name.strip('"')
    i = lines.index("$Nodes")
    n = int(lines[i + 1])
    ids, xy = {}, []
    for k, line in enumerate(lines[i + 2:i + 2 + n]):
        v = line.split()
        ids[int(v[0])] = k
        xy.append((float(v[1]), float(v[2])))
    i = lines.index("$Elements")
    n = int(lines[i + 1])
    tri, phys = [], []
    for line in lines[i + 2:i + 2 + n]:
        v = list(map(int, line.split()))
        if v[1] == 2:
            ntags = v[2]
            tri.append([ids[x] for x in v[3 + ntags:6 + ntags]])
            phys.append(names.get(v[3], "?"))
    return np.array(xy), np.array(tri), phys
