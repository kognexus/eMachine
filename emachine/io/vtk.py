"""
Writing and reading VTK XML files for ParaView: unstructured grids (.vtu) and time series (.pvd).

Files are written as plain text in the same layout that Elmer writes, which ParaView reads.
"""

import os
import xml.etree.ElementTree as ET

import numpy as np

TETRA, QUAD, LINE, VERTEX, TRIANGLE, WEDGE = 10, 9, 3, 1, 5, 13
CELL_SIZE = {TETRA: 4, QUAD: 4, LINE: 2, VERTEX: 1, TRIANGLE: 3, WEDGE: 6}


def _text(array, fmt):
    flat = np.asarray(array).ravel()
    return " ".join(map(fmt.__mod__, flat)) if len(flat) else ""


def _data_array(name, array, extra=""):
    array = np.asarray(array)
    integer = np.issubdtype(array.dtype, np.integer)
    components = array.shape[1] if array.ndim == 2 else 1
    head = (f'<DataArray type="{"Int32" if integer else "Float64"}" Name="{name}" '
            f'NumberOfComponents="{components}" format="ascii"{extra}>')
    return f"        {head}\n{_text(array, '%d' if integer else '%.6g')}\n        </DataArray>"


def write_vtu(path, points, cells, cell_type=TETRA, point_data=None, cell_data=None, field_data=None):
    """
    Writes an unstructured grid of one cell type.

    points      (n, 3) coordinates
    cells       (m, k) point indices, k = 4 for tetrahedra and quadrilaterals, 6 for wedges (base
                triangle first, counter-clockwise seen from the top triangle), 3 for triangles,
                2 for lines, 1 for vertices
    point_data  {name: (n,) or (n, 3) array}
    cell_data   {name: (m,) or (m, 3) array}
    field_data  {name: number}; values for the whole file, such as the torque of this step
    """
    points = np.asarray(points, dtype=float)
    cells = np.asarray(cells, dtype=np.int64).reshape(-1, CELL_SIZE[cell_type])
    for group, count in ((point_data or {}, len(points)), (cell_data or {}, len(cells))):
        for name, array in group.items():
            if len(array) != count:
                raise ValueError(f"'{name}' has {len(array)} values for {count} entries.")
    out = ['<?xml version="1.0"?>',
           '<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">',
           "  <UnstructuredGrid>"]
    if field_data:
        out.append("    <FieldData>")
        for name, value in field_data.items():
            out.append(f'      <DataArray type="Float64" Name="{name}" NumberOfTuples="1" format="ascii">'
                       f"{float(value):.9g}</DataArray>")
        out.append("    </FieldData>")
    out.append(f'    <Piece NumberOfPoints="{len(points)}" NumberOfCells="{len(cells)}">')
    out.append("      <PointData>")
    out += [_data_array(name, array) for name, array in (point_data or {}).items()]
    out.append("      </PointData>")
    out.append("      <CellData>")
    out += [_data_array(name, array) for name, array in (cell_data or {}).items()]
    out.append("      </CellData>")
    out.append("      <Points>")
    out.append(f'        <DataArray type="Float64" NumberOfComponents="3" format="ascii">\n'
               f"{_text(points, '%.7g')}\n        </DataArray>")
    out.append("      </Points>")
    out.append("      <Cells>")
    size = CELL_SIZE[cell_type]
    out.append(f'        <DataArray type="Int32" Name="connectivity" format="ascii">\n{_text(cells, "%d")}\n'
               "        </DataArray>")
    out.append(f'        <DataArray type="Int32" Name="offsets" format="ascii">\n'
               f'{_text(size * np.arange(1, len(cells) + 1), "%d")}\n        </DataArray>')
    out.append(f'        <DataArray type="Int32" Name="types" format="ascii">\n'
               f'{_text(np.full(len(cells), cell_type), "%d")}\n        </DataArray>')
    out += ["      </Cells>", "    </Piece>", "  </UnstructuredGrid>", "</VTKFile>", ""]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(out))


def read_vtu(path):
    """
    Reads a file written by `write_vtu` (plain text, one cell type). Returns a dictionary with
    points, cells, cell_type, point_data, cell_data, field_data. Raises ValueError when the counts
    in the header do not agree with the data.
    """
    root = ET.parse(path).getroot()
    if root.get("type") != "UnstructuredGrid":
        raise ValueError(f"{path}: not an unstructured grid.")
    piece = root.find(".//Piece")
    n_points, n_cells = int(piece.get("NumberOfPoints")), int(piece.get("NumberOfCells"))

    def numbers(node, dtype=float):
        return np.array((node.text or "").split(), dtype=dtype)

    def group(tag, count):
        data = {}
        for node in piece.find(tag):
            components = int(node.get("NumberOfComponents", "1"))
            values = numbers(node, np.int64 if node.get("type", "").startswith("Int") else float)
            if len(values) != count * components:
                raise ValueError(f"{path}: '{node.get('Name')}' has {len(values)} numbers, "
                                 f"expected {count} x {components}.")
            data[node.get("Name")] = values.reshape(count, components) if components > 1 else values
        return data

    points = numbers(piece.find("Points/DataArray"))
    if len(points) != 3 * n_points:
        raise ValueError(f"{path}: {len(points)} coordinates for {n_points} points.")
    arrays = {node.get("Name"): numbers(node, np.int64) for node in piece.find("Cells")}
    types, offsets, connectivity = arrays["types"], arrays["offsets"], arrays["connectivity"]
    if len(types) != n_cells or len(offsets) != n_cells:
        raise ValueError(f"{path}: cell arrays do not have {n_cells} entries.")
    cell_type = int(types[0]) if n_cells else TETRA
    if n_cells and (np.any(types != cell_type) or offsets[-1] != len(connectivity)):
        raise ValueError(f"{path}: mixed cell types or a wrong connectivity length.")
    cells = connectivity.reshape(n_cells, -1) if n_cells else connectivity.reshape(0, CELL_SIZE[cell_type])
    if n_cells and (cells.min() < 0 or cells.max() >= n_points):
        raise ValueError(f"{path}: a cell refers to a point that does not exist.")
    field = root.find(".//FieldData")
    return {"points": points.reshape(n_points, 3), "cells": cells, "cell_type": cell_type,
            "point_data": group("PointData", n_points), "cell_data": group("CellData", n_cells),
            "field_data": {n.get("Name"): float(n.text) for n in (field if field is not None else [])}}


def write_pvd(path, entries):
    """Time series: `entries` is a list of (time value, file path). Paths are stored relative to the .pvd file."""
    base = os.path.dirname(os.path.abspath(path))
    out = ['<?xml version="1.0"?>', '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">',
           "  <Collection>"]
    for time, file in entries:
        relative = os.path.relpath(os.path.abspath(file), base).replace(os.sep, "/")
        out.append(f'    <DataSet timestep="{float(time):.9g}" group="" part="0" file="{relative}"/>')
    out += ["  </Collection>", "</VTKFile>", ""]
    with open(path, "w") as f:
        f.write("\n".join(out))


def read_pvd(path):
    """List of (time value, absolute file path) of a .pvd file."""
    base = os.path.dirname(os.path.abspath(path))
    return [(float(node.get("timestep")), os.path.normpath(os.path.join(base, node.get("file"))))
            for node in ET.parse(path).getroot().iter("DataSet")]


def subset(points, cells, mask, point_data=None, cell_data=None):
    """The cells selected by `mask`, with only the points they use. Returns (points, cells, point_data, cell_data)."""
    cells = np.asarray(cells)[mask]
    used = np.unique(cells)
    index = np.full(len(points), -1, dtype=np.int64)
    index[used] = np.arange(len(used))
    return (np.asarray(points)[used], index[cells],
            {k: np.asarray(v)[used] for k, v in (point_data or {}).items()},
            {k: np.asarray(v)[mask] for k, v in (cell_data or {}).items()})


def rotate_z(vectors, angle_deg):
    c, s = np.cos(np.radians(angle_deg)), np.sin(np.radians(angle_deg))
    v = np.asarray(vectors, dtype=float)
    return np.column_stack([c * v[:, 0] - s * v[:, 1], s * v[:, 0] + c * v[:, 1], v[:, 2]])


def repeat_sector(points, cells, point_data, cell_data, copies, angle_deg):
    """
    A sector repeated `copies` times around the z axis, each copy turned by `angle_deg`.
    Arrays with three components are treated as vectors and turned with the geometry.
    """
    if copies <= 1:
        return points, cells, point_data, cell_data

    def turn(array, k):
        array = np.asarray(array)
        return rotate_z(array, k * angle_deg) if array.ndim == 2 and array.shape[1] == 3 else array

    n = len(points)
    return (np.vstack([rotate_z(points, k * angle_deg) for k in range(copies)]),
            np.vstack([np.asarray(cells) + k * n for k in range(copies)]),
            {name: np.concatenate([turn(a, k) for k in range(copies)]) for name, a in point_data.items()},
            {name: np.concatenate([turn(a, k) for k in range(copies)]) for name, a in cell_data.items()})
