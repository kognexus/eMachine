"""Reading Elmer output: body numbers of the regions, field files (.vtu), saved scalars."""

import os
import re
import xml.etree.ElementTree as ET

import numpy as np

from emachine.io.process import read_text


def read_names(posdir):
    """Body and boundary numbers that ElmerGrid assigned to the named regions."""
    bodies, boundaries, target = {}, {}, None
    with open(os.path.join(posdir, "mesh", "mesh.names")) as f:
        for line in f:
            low = line.lower()
            if line.startswith("!"):
                target = bodies if "bodies" in low else boundaries if "boundar" in low else target
                continue
            m = re.match(r"\s*\$\s*(\S+)\s*=\s*(\d+)", line)
            if m and target is not None:
                target[m.group(1)] = int(m.group(2))
    return bodies, boundaries


def read_vtu(path):
    """Minimal reader for Elmer's ASCII .vtu files: points, tetrahedra, body ids and point fields."""
    root = ET.parse(path).getroot()
    piece = root.find(".//Piece")

    def array(node):
        return np.array(node.text.split(), dtype=float)

    points = array(piece.find("Points/DataArray")).reshape(-1, 3)
    cells = {a.get("Name"): array(a) for a in piece.find("Cells")}
    types = cells["types"].astype(int)
    offsets = cells["offsets"].astype(int)
    conn = cells["connectivity"].astype(int)
    tets = np.array([conn[offsets[i] - 4:offsets[i]] for i in np.where(types == 10)[0]])
    cell_data = {a.get("Name").lower(): array(a) for a in piece.find("CellData")}
    point_data = {}
    for a in piece.find("PointData"):
        comps = int(a.get("NumberOfComponents", "1"))
        point_data[a.get("Name").lower()] = array(a).reshape(-1, comps) if comps > 1 else array(a)
    body = cell_data["geometryids"].astype(int)[types == 10]
    return points, tets, body, point_data


def read_fields(posdir):
    """Points, tetrahedra, body ids and point fields of the solution of one position, or None."""
    files = sorted(f for f in os.listdir(os.path.join(posdir, "results")) if f.endswith(".vtu"))
    if not files:
        return None
    return read_vtu(os.path.join(posdir, "results", files[-1]))


def tet_volumes(p):
    return np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6


def flux_density_name(fields):
    """
    Name of the flux density field to use. Elmer writes two: the element field ("... e"), which is
    the curl of the solution and jumps at material boundaries as it should, and a nodal field
    smoothed over neighbouring elements. The smoothed field loses about a fifth of the flux in
    thin iron parts (ticket B05), so the element field is used whenever it is present.
    """
    names = [n for n in fields if "flux density" in n and fields[n].ndim == 2]
    return next((n for n in names if n.endswith(" e")), names[0] if names else None)



def read_scalars(posdir):
    """{name: value} of results/scalars.dat (SaveScalars)."""
    names = [re.sub(r"^\s*\d+:\s*", "", line).strip()
             for line in read_text(os.path.join(posdir, "results", "scalars.dat.names")).splitlines()
             if re.match(r"\s*\d+:", line)]
    values = [float(v) for v in read_text(os.path.join(posdir, "results", "scalars.dat")).split()]
    return dict(zip(names, values))
