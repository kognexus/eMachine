"""Pictures of a meshed sector: an SVG preview without a window, or the Gmsh window."""

import math
import os

import gmsh

def part_colour(label):
    """Display colour for a region, chosen from its name."""
    if "air" in label:
        return (200, 225, 245)
    if "coil" in label:
        return (205, 110, 50)
    if "magnet_n" in label:
        return (200, 40, 40)
    if "magnet_s" in label:
        return (40, 150, 65)
    if "magnet" in label and "non_magnetic" not in label:
        return (60, 90, 205) if "minus" in label else (235, 190, 40)
    if "pole_piece" in label:
        return (120, 120, 126)
    if "rotor" in label:
        return (105, 110, 122)
    return (170, 170, 178)


def write_preview(labels, show_air, path, mid_angle):
    """
    Window-free picture (SVG) of the meshed parts: the outer skin of every region, drawn far to near.
    """
    import numpy as np

    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    xyz = np.zeros((int(node_tags.max()) + 1, 3))
    xyz[node_tags.astype(int)] = np.asarray(coords).reshape(-1, 3)

    # Camera: above the stack, to one side of the sector.
    az, el = mid_angle - math.radians(55), math.radians(32)
    cam = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    right = np.cross([0.0, 0.0, 1.0], cam)
    right /= np.linalg.norm(right)
    up = np.cross(cam, right)
    light = np.array([0.35, -0.25, 0.9])
    light /= np.linalg.norm(light)

    polys, legend = [], []
    for (_, label), tags in sorted(labels.items(), key=lambda kv: kv[0][1]):
        if label.endswith("_air") and not show_air:
            continue
        tets = []
        for t in tags:
            _, nodes = gmsh.model.mesh.getElementsByType(4, t)
            tets.append(np.asarray(nodes, dtype=np.int64).reshape(-1, 4))
        tets = np.vstack(tets)
        faces = np.vstack([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]], tets[:, [1, 2, 3]]])
        faces.sort(axis=1)
        uniq, counts = np.unique(faces, axis=0, return_counts=True)
        skin = uniq[counts == 1]
        pts = xyz[skin]
        normal = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-30)
        shade = 0.45 + 0.55 * np.abs(normal @ light)
        depth = pts.mean(axis=1) @ cam
        colour = np.array(part_colour(label))
        legend.append((label, colour))
        for i in range(len(skin)):
            polys.append((depth[i], pts[i] @ right, pts[i] @ up, colour * shade[i]))

    polys.sort(key=lambda q: q[0])
    xs = np.concatenate([q[1] for q in polys])
    ys = np.concatenate([q[2] for q in polys])
    width, pad = 1200.0, 30.0
    scale = (width - 2 * pad) / (xs.max() - xs.min())
    height = (ys.max() - ys.min()) * scale + 2 * pad + 22 * len(legend) + 10
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'viewBox="0 0 {width:.0f} {height:.0f}">', '<rect width="100%" height="100%" fill="white"/>']
    opacity = ' fill-opacity="0.35"' if show_air else ""
    for _, px, py, c in polys:
        pts = " ".join(f"{pad + (x - xs.min()) * scale:.1f},{pad + (ys.max() - y) * scale:.1f}" for x, y in zip(px, py))
        out.append(f'<polygon points="{pts}" fill="rgb({c[0]:.0f},{c[1]:.0f},{c[2]:.0f})"{opacity} '
                   f'stroke="black" stroke-opacity="0.25" stroke-width="0.3"/>')
    y0 = (ys.max() - ys.min()) * scale + 2 * pad
    for i, (label, c) in enumerate(legend):
        out.append(f'<rect x="{pad}" y="{y0 + 22 * i}" width="16" height="16" fill="rgb({c[0]},{c[1]},{c[2]})" stroke="black" stroke-width="0.5"/>')
        out.append(f'<text x="{pad + 24}" y="{y0 + 22 * i + 13}" font-family="Helvetica, Arial, sans-serif" font-size="14">{label}</text>')
    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))
    print(f"Preview -> {path} ({len(polys)} triangles)")


def show_window(labels, show_air):
    """
    Opens the Gmsh window on the meshed parts only, one colour per region. The air is left out
    unless asked for, because its mesh hides everything else.
    """
    keep = [key for key in labels if show_air or not key[1].endswith("_air")]
    gmsh.model.removePhysicalGroups()
    for key in keep:
        new = gmsh.model.addPhysicalGroup(3, labels[key])
        gmsh.model.setPhysicalName(3, new, key[1])
    opt = gmsh.option.setNumber
    opt("Mesh.SaveAll", 0)
    view_file = os.path.abspath(".tfm_view.msh")
    gmsh.write(view_file)
    gmsh.clear()
    gmsh.open(view_file)
    os.remove(view_file)
    opt("Mesh.ColorCarousel", 2)   # one colour per region
    opt("Mesh.VolumeFaces", 1)
    opt("Mesh.VolumeEdges", 1)
    opt("Mesh.SurfaceFaces", 0)
    opt("Mesh.SurfaceEdges", 0)
    opt("Mesh.Points", 0)
    opt("Mesh.Lines", 0)
    opt("Geometry.Points", 0)
    opt("Geometry.Curves", 0)
    opt("General.Trackball", 0)
    opt("General.RotationX", 300)
    opt("General.RotationY", 0)
    opt("General.RotationZ", 235)
    print("Regions shown: " + ", ".join(sorted(key[1] for key in keep)))
    gmsh.fltk.run()

