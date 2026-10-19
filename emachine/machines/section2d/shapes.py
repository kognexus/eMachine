"""Gmsh OpenCASCADE faces used by the section builders. Lengths in mm, angles in degrees."""

import math

import gmsh

occ = gmsh.model.occ


def disk(r, x=0.0, y=0.0):
    return occ.addDisk(x, y, 0, r, r)


def annulus(r0, r1):
    """Ring between the radii r0 < r1 (a disk when r0 <= 0)."""
    outer = disk(r1)
    if r0 <= 1e-9:
        return outer
    out, _ = occ.cut([(2, outer)], [(2, disk(r0))])
    return out[0][1]


def sector(r0, r1, start_deg, span_deg):
    """Ring sector r0..r1 between start and start + span (counter-clockwise)."""
    span_deg = min(span_deg, 359.999)
    a0, a1 = math.radians(start_deg), math.radians(start_deg + span_deg)
    centre = occ.addPoint(0, 0, 0)
    p1 = occ.addPoint(r1 * math.cos(a0), r1 * math.sin(a0), 0)
    p2 = occ.addPoint(r1 * math.cos(a1), r1 * math.sin(a1), 0)
    if r0 <= 1e-9:
        curves = [occ.addLine(centre, p1), occ.addCircleArc(p1, centre, p2), occ.addLine(p2, centre)]
    else:
        p3 = occ.addPoint(r0 * math.cos(a1), r0 * math.sin(a1), 0)
        p0 = occ.addPoint(r0 * math.cos(a0), r0 * math.sin(a0), 0)
        curves = [occ.addLine(p0, p1), occ.addCircleArc(p1, centre, p2), occ.addLine(p2, p3),
                  occ.addCircleArc(p3, centre, p0)]
    face = occ.addPlaneSurface([occ.addCurveLoop(curves)])
    if r0 > 1e-9:
        occ.remove([(0, centre)])
    return face


def polygon(points):
    """Closed polygon through the points [(x, y), ...]."""
    tags = [occ.addPoint(x, y, 0) for x, y in points]
    lines = [occ.addLine(tags[i], tags[(i + 1) % len(tags)]) for i in range(len(tags))]
    return occ.addPlaneSurface([occ.addCurveLoop(lines)])


def local_rect(x0, x1, y0, y1, angle_deg):
    """Rectangle x0..x1 (along the radius of angle) by y0..y1 (across), turned to the angle."""
    face = occ.addRectangle(x0, y0, 0, x1 - x0, y1 - y0)
    occ.rotate([(2, face)], 0, 0, 0, 0, 0, 1, math.radians(angle_deg))
    return face


def rotated(points, angle_deg):
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return [(c * x - s * y, s * x + c * y) for x, y in points]


def intersect(a, b):
    """Intersection of two faces (both consumed); None when empty."""
    out, _ = occ.intersect([(2, a)], [(2, b)])
    faces = [t for d, t in out if d == 2]
    return faces


def intersect_all(a, tools):
    out, _ = occ.intersect([(2, a)], [(2, t) for t in tools])
    return [t for d, t in out if d == 2]


def cut(a, tools):
    """a minus the tools (all consumed); list of faces."""
    out, _ = occ.cut([(2, a)], [(2, t) for t in tools])
    return [t for d, t in out if d == 2]
