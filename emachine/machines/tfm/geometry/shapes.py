"""Gmsh OpenCASCADE helpers shared by the stator and rotor builders of the TFM."""

import re

import gmsh

occ = gmsh.model.occ


def slug(name):
    """'Magnet N (radial out)' -> 'magnet_n_radial_out'."""
    name = name.split("/")[-1]
    name = re.sub(r"\s*[\(<]\d+[\)>]\s*$", "", name)  # trailing instance counters such as ' (3)'
    name = re.sub(r"-(?=\d)", " minus ", name)  # keep the sign: '-90 deg' and '90 deg' are different magnets
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return s or "part"


def ring(r0, r1, z0, z1):
    """Full ring r0..r1, z0..z1 around the Z axis. Returns a volume tag."""
    outer = occ.addCylinder(0, 0, z0, 0, 0, z1 - z0, r1)
    if r0 <= 0:
        return outer
    inner = occ.addCylinder(0, 0, z0 - 1, 0, 0, z1 - z0 + 2, r0)
    out, _ = occ.cut([(3, outer)], [(3, inner)])
    return out[0][1]


def ring_sector(r0, r1, z0, z1, start, opening):
    """Ring sector r0..r1, z0..z1 spanning the angles start..start+opening. Returns a volume tag."""
    outer = occ.addCylinder(0, 0, z0, 0, 0, z1 - z0, r1, angle=opening)
    tag = outer
    if r0 > 0:
        inner = occ.addCylinder(0, 0, z0 - 1, 0, 0, z1 - z0 + 2, r0)
        out, _ = occ.cut([(3, outer)], [(3, inner)])
        tag = out[0][1]
    occ.rotate([(3, tag)], 0, 0, 0, 0, 0, 1, start)
    return tag


def copies_at(seed, angles):
    """Rotated copies of the seed volume about Z; the seed itself is removed."""
    tags = []
    for angle in angles:
        c = occ.copy([(3, seed)])
        occ.rotate(c, 0, 0, 0, 0, 0, 1, angle)
        tags.append(c[0][1])
    occ.remove([(3, seed)], recursive=True)
    return tags

