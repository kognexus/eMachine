"""
Radial machine sections (T59): rings from the bore outwards, each a stator or a rotor.

params = {
  "parts": [part, ...]            ordered from the inside out; neighbouring stator and rotor rings are
                                  separated by an air gap (part["r_in"] of the outer one minus
                                  part["r_out"] of the inner one)
  "bore_radius": r                hole inside the innermost ring (air)
  "rotor_angle_deg": angle        mechanical rotor angle; every rotor part is turned by it
}

Stator part: {"role": "stator", "type": "slotted", "r_in", "r_out", "facing": "in" | "out" (the side of
its teeth: "in" for a stator outside its rotor), "slots", "slot_depth" (from the gap surface to the
slot bottom), "tooth_width" (parallel-sided tooth body), "tip_height", "opening", "notches" (per tooth,
0 = none), "notch_width", "notch_depth", "offset_deg", "sides": [[slot, half, phase, sign, share], ...]}.
A salient-pole (SRM) stator is "slotted" with open slots (tip_height 0). Split teeth (vernier) are
notches whose width equals the slot opening (see notch_angles).

Rotor part: {"role": "rotor", "type": one of LAYOUTS, "r_in", "r_out", "facing", "poles" (2 p, or the
rotor poles of an SRM), "offset_deg", and the layout's own keys (see the builder functions)}.

Coil side k of stator s is the region coil_<s>_<slot>_<half>; half 0 is the clockwise half of the
slot. Magnet regions carry their magnetisation as a unit vector in the plane (absolute frame).
"""

import math

from . import shapes
from .shapes import annulus, local_rect, polygon, rotated, sector

BIG = 1.0e3


def gap_surface(part):
    """Radius of the air-gap surface of a part (for one-sided parts)."""
    return part["r_in"] if part["facing"] == "in" else part["r_out"]


def notch_angles(slots, notches, offset_deg=0.0):
    """Centres (degrees) of the notches of every tooth: the tooth face is divided into notches + 1
    equal modulators, so notches as wide as the slot opening give Q (notches + 1) equally spaced
    teeth (split-tooth vernier stator)."""
    if notches <= 0:
        return []
    pitch = 360.0 / slots
    tau = pitch / (notches + 1)
    out = []
    for k in range(slots):
        tooth = offset_deg + (k + 0.5) * pitch
        out += [tooth + (j - (notches - 1) / 2.0) * tau for j in range(notches)]
    return out


# ----------------------------------------------------------------------------- stators

def stator_faces(s_index, part):
    """Named faces of a slotted stator: coil halves, slot openings and notches (air), the core."""
    q = int(part["slots"])
    pitch = 360.0 / q
    rg, depth, tip = gap_surface(part), part["slot_depth"], part.get("tip_height", 0.0)
    w_t = part.get("tooth_width", 0.0)
    inward = part["facing"] == "in"               # teeth point inwards: slots lie outside the gap surface
    if inward:
        band = (rg + tip, rg + depth)
        tip_band = (rg, rg + tip + 1e-3)
    else:
        band = (rg - depth, rg - tip)
        tip_band = (rg - tip - 1e-3, rg)
    off = part.get("offset_deg", 0.0)
    named = []
    sides = {(int(s[0]), int(s[1])): s for s in part["sides"]}
    for k in range(q):
        centre = off + k * pitch
        for half in (0, 1):
            if part.get("slot_width"):                   # parallel-sided slot (T41) instead of parallel teeth
                w_s = part["slot_width"]
                y0, y1 = (-w_s / 2, 0.0) if half == 0 else (0.0, w_s / 2)
                faces = shapes.intersect(local_rect(0.0, BIG, y0, y1, centre), annulus(*band))
            else:
                start = centre - pitch / 2 if half == 0 else centre
                body = sector(band[0], band[1], start, pitch / 2)
                tooth_angle = centre - pitch / 2 if half == 0 else centre + pitch / 2
                faces = shapes.cut(body, [local_rect(0.0, BIG, -w_t / 2, w_t / 2, tooth_angle)])
            name = f"coil_{s_index}_{k}_{half}" if (k, half) in sides else "stator_air"
            named += [(name, f) for f in faces]
        opening = part.get("opening", 0.0)
        if tip > 0 and opening > 0:
            faces = shapes.intersect(local_rect(0.0, BIG, -opening / 2, opening / 2, centre), annulus(*tip_band))
            named += [("stator_air", f) for f in faces]
    n_notch, w_n, h_n = int(part.get("notches", 0)), part.get("notch_width", 0.0), part.get("notch_depth", 0.0)
    if n_notch and w_n > 0 and h_n > 0:
        band_n = (rg, rg + h_n) if inward else (rg - h_n, rg)
        for angle in notch_angles(q, n_notch, off):
            faces = shapes.intersect(local_rect(0.0, BIG, -w_n / 2, w_n / 2, angle), annulus(*band_n))
            named += [("stator_air", f) for f in faces]
    named.append(("stator_core", annulus(part["r_in"], part["r_out"])))
    regions = {}
    for (k, half), s in sides.items():
        regions[f"coil_{s_index}_{k}_{half}"] = {"kind": "coil", "side": "stator", "stator": s_index, "slot": k,
                                                 "half": half, "phase": int(s[2]), "sign": int(s[3]),
                                                 "share": float(s[4]) if len(s) > 4 else 1.0}
    return named, regions


# ----------------------------------------------------------------------------- rotors

def _pole_centres(part, turn):
    n = int(part["poles"])
    return [turn + part.get("offset_deg", 0.0) + j * 360.0 / n for j in range(n)]


def _radial(angle_deg, sign=1.0):
    a = math.radians(angle_deg)
    return [sign * math.cos(a), sign * math.sin(a)]


def _magnet_band(part):
    """(r0, r1) of the magnet layer at the gap surface, and the iron band behind it."""
    h = part["magnet_thickness"]
    if part["facing"] == "out":
        return (part["r_out"] - h, part["r_out"]), (part["r_in"], part["r_out"] - h)
    return (part["r_in"], part["r_in"] + h), (part["r_in"] + h, part["r_out"])


def rotor_surface(part, turn, halbach=False):
    """Surface magnets: arc `magnet_arc` (share of the pole pitch), thickness `magnet_thickness`,
    `segments` per pole (parallel magnetised each; several approximate radial magnetisation), iron yoke
    behind (`yoke`: false for a non-magnetic hub). Halbach: the whole pole in `segments` pieces whose
    magnetisation turns with the angle (strong side towards the gap)."""
    poles = int(part["poles"])
    p = poles // 2
    band, back = _magnet_band(part)
    pitch = 360.0 / poles
    arc = (1.0 if halbach else part["magnet_arc"]) * pitch
    nseg = max(1, int(part.get("segments", 1)))
    outward = part["facing"] == "out"
    named, magnets = [], {}
    for j, centre in enumerate(_pole_centres(part, turn)):
        north = 1.0 if j % 2 == 0 else -1.0
        for s in range(nseg):
            a0 = centre - arc / 2 + s * arc / nseg
            mid = a0 + arc / (2 * nseg)
            name = f"magnet_{j}_{s}"
            named.append((name, sector(band[0], band[1], a0, arc / nseg)))
            if halbach:
                rel = math.radians(mid - turn - part.get("offset_deg", 0.0))
                theta = (1 - p) * rel if outward else (1 + p) * rel + math.pi
                theta += math.radians(turn + part.get("offset_deg", 0.0))
                m = [math.cos(theta), math.sin(theta)]
            else:
                m = _radial(mid if nseg > 1 else centre, north * (1.0 if outward else -1.0))
            magnets[name] = {"kind": "magnet", "side": "rotor", "magnetization": m, "pole": j}
    named.append(("rotor_air", annulus(*band)))
    if part.get("yoke", True):
        named.append(("rotor_core", annulus(*back)))
    else:
        named.append(("rotor_hub", annulus(*back)))
    return named, magnets


def rotor_consequent(part, turn):
    """Consequent poles: magnets (north, towards the gap) on every second pole, iron poles of arc
    `iron_arc` (share of the pole pitch) on the others, flush with the magnets."""
    pitch = 360.0 / int(part["poles"])
    band, back = _magnet_band(part)
    outward = part["facing"] == "out"
    named, magnets = [], {}
    for j, centre in enumerate(_pole_centres(part, turn)):
        if j % 2 == 0:
            arc = part["magnet_arc"] * pitch
            name = f"magnet_{j}_0"
            named.append((name, sector(band[0], band[1], centre - arc / 2, arc)))
            magnets[name] = {"kind": "magnet", "side": "rotor", "magnetization": _radial(centre, 1.0 if outward else -1.0),
                             "pole": j}
        else:
            arc = part["iron_arc"] * pitch
            named.append(("rotor_pole", sector(band[0], band[1], centre - arc / 2, arc)))
    named.append(("rotor_air", annulus(*band)))
    named.append(("rotor_core", annulus(*back)))
    return named, magnets


def v_bar_corners(part, side):
    """Corners of one bar of the interior V in the pole frame (x along the pole axis), and its outward
    normal: side +1 upper bar, -1 lower bar. Keys: v_depth (gap surface to the apex), v_angle_deg
    (180 = flat bar), magnet_length, magnet_thickness, post (iron between the two bars at the apex)."""
    rg = part["r_out"]
    half = math.radians(part["v_angle_deg"] / 2)
    u = (math.cos(half), side * math.sin(half))
    n = (math.sin(half), -side * math.cos(half))
    s0 = (rg - part["v_depth"], side * part.get("post", 0.0) / 2)
    length, t = part["magnet_length"], part["magnet_thickness"]
    corners = [s0, (s0[0] + length * u[0], s0[1] + length * u[1]),
               (s0[0] + length * u[0] + t * n[0], s0[1] + length * u[1] + t * n[1]), (s0[0] + t * n[0], s0[1] + t * n[1])]
    return corners, u, n


def v_pocket(part, side):
    """Air pocket at the outer end of a V bar (pole frame): along the bar until both its edges reach the
    bridge circle, at most one magnet thickness (+0.5 mm) long; None when the bar already reaches it."""
    corners, u, _ = v_bar_corners(part, side)
    limit = part["r_out"] - part["bridge"]
    ext = 0.0
    for c in (corners[1], corners[2]):
        cu = c[0] * u[0] + c[1] * u[1]
        disc = cu * cu - (c[0] ** 2 + c[1] ** 2) + limit ** 2
        if disc > 0:
            ext = max(ext, -cu + math.sqrt(disc))
    ext = min(ext + 0.2, part["magnet_thickness"] + 0.5)
    if ext <= 0.05:
        return None
    return [corners[1], (corners[1][0] + ext * u[0], corners[1][1] + ext * u[1]),
            (corners[2][0] + ext * u[0], corners[2][1] + ext * u[1]), corners[2]]


def rotor_interior_v(part, turn):
    """Interior magnets in a V per pole (inner rotor), with an air pocket from the outer end of each bar
    to the bridge `bridge` below the rotor surface."""
    named, magnets = [], {}
    rg = part["r_out"]
    for j, centre in enumerate(_pole_centres(part, turn)):
        north = 1.0 if j % 2 == 0 else -1.0
        for k, side in enumerate((1, -1)):
            corners, u, n = v_bar_corners(part, side)
            name = f"magnet_{j}_{k}"
            named.append((name, polygon(rotated(corners, centre))))
            a = math.radians(centre)
            mx, my = north * n[0], north * n[1]
            magnets[name] = {"kind": "magnet", "side": "rotor", "pole": j,
                             "magnetization": [math.cos(a) * mx - math.sin(a) * my, math.sin(a) * mx + math.cos(a) * my]}
            pocket = v_pocket(part, side)
            if pocket is None:
                continue
            faces = shapes.intersect(polygon(rotated(pocket, centre)), shapes.disk(rg - part["bridge"]))
            named += [("rotor_air", f) for f in faces]
    named.append(("rotor_core", annulus(part["r_in"], rg)))
    return named, magnets


def rotor_spoke(part, turn):
    """Spoke magnets between the poles (inner rotor), magnetised across: magnet from `spoke_inner`
    (radius) to the bridge `bridge` below the surface, width `spoke_width`, an air pocket of height
    `pocket` below it."""
    named, magnets = [], {}
    poles = int(part["poles"])
    rg, w = part["r_out"], part["spoke_width"]
    r0 = part["spoke_inner"]
    for j, centre in enumerate(_pole_centres(part, turn)):
        boundary = centre + 180.0 / poles
        name = f"magnet_{j}_0"
        named.append((name, local_rect(r0, rg - part["bridge"], -w / 2, w / 2, boundary)))
        sign = -1.0 if j % 2 == 0 else 1.0                       # towards the north pole j (even)
        a = math.radians(boundary)
        magnets[name] = {"kind": "magnet", "side": "rotor", "pole": j,
                         "magnetization": [-sign * math.sin(a), sign * math.cos(a)]}
        if part.get("pocket", 0.0) > 0:
            named.append(("rotor_air", local_rect(r0 - part["pocket"], r0, -w / 2, w / 2, boundary)))
    hub = part.get("hub_radius")
    if hub:                                       # non-magnetic hub below the magnets (T68): the poles do not touch
        named.append(("rotor_core", annulus(hub, rg)))
        named.append(("rotor_hub", annulus(part["r_in"], hub)))
    else:
        named.append(("rotor_core", annulus(part["r_in"], rg)))
    return named, magnets


def barrier_circles(part):
    """Centre distance and the (inner, outer) radii of the flux barriers around a q axis, for an inner
    rotor of surface radius r_out: circles centred on the q axis outside the rotor; the smallest touches
    the surface on the q axis, the largest meets it at right angles on the neighbouring d axes.
    `barriers` per pole, `insulation` = total barrier width / (rho_max - rho_min)."""
    rg = part["r_out"]
    beta = math.pi / int(part["poles"])
    rc = rg / math.cos(beta)
    rho_min, rho_max = rc - rg, rg * math.tan(beta)
    n = int(part["barriers"])
    pitch = (rho_max - rho_min) / n
    w = part["insulation"] * pitch
    return rc, [(rho_min + (k + 0.5) * pitch - w / 2, rho_min + (k + 0.5) * pitch + w / 2) for k in range(n)]


def rotor_flux_barrier(part, turn, with_magnets=False):
    """Flux barriers around every q axis (SynRM), ribs `rib` below the surface and above the inner
    ring `inner_ring`; with magnets (PMaSynRM): a magnet of width `pm_width` across the q axis in the
    middle of every barrier, magnetised along the q axis (`pm_remanence` overrides the remanence)."""
    named, magnets = [], {}
    rg, rib = part["r_out"], part["rib"]
    rc, rings = barrier_circles(part)
    inner = part["r_in"] + part.get("inner_ring", 1.0)
    poles = int(part["poles"])
    for j, d_axis in enumerate(_pole_centres(part, turn)):
        q_axis = d_axis + 180.0 / poles
        a = math.radians(q_axis)
        cx, cy = rc * math.cos(a), rc * math.sin(a)
        for k, (r0, r1) in enumerate(rings):
            if r0 <= 0:
                ring = shapes.disk(r1, cx, cy)
            else:
                ring = shapes.cut(shapes.disk(r1, cx, cy), [shapes.disk(r0, cx, cy)])[0]
            faces = shapes.intersect(ring, annulus(inner, rg - rib))
            if with_magnets and part.get("pm_width", 0.0) > 0:
                for f in faces:
                    named.append(("rotor_air", f))
                strip_ring = (shapes.disk(r1, cx, cy) if r0 <= 0 else
                              shapes.cut(shapes.disk(r1, cx, cy), [shapes.disk(r0, cx, cy)])[0])
                band = shapes.intersect(strip_ring, annulus(inner, rg - rib))
                pm_faces = []
                for f in band:
                    pm_faces += shapes.intersect(f, local_rect(0.0, BIG, -part["pm_width"] / 2, part["pm_width"] / 2, q_axis))
                for i, f in enumerate(pm_faces):
                    name = f"magnet_{j}_{k}_{i}"
                    named.insert(0, (name, f))
                    magnets[name] = {"kind": "magnet", "side": "rotor", "pole": j,
                                     "magnetization": _radial(q_axis, 1.0 if j % 2 == 0 else -1.0)}
                    if part.get("pm_remanence") is not None:
                        magnets[name]["remanence_T"] = part["pm_remanence"]
                        magnets[name]["mu_r"] = part.get("pm_mu_r", 1.1)
            else:
                named += [("rotor_air", f) for f in faces]
    named.append(("rotor_core", annulus(part["r_in"], rg)))
    return named, magnets


def rotor_salient(part, turn):
    """Salient iron poles (SRM): `poles` poles of arc `pole_arc_deg` and height `pole_height` on a yoke."""
    named = []
    h = part["pole_height"]
    outward = part["facing"] == "out"
    band = (part["r_out"] - h, part["r_out"]) if outward else (part["r_in"], part["r_in"] + h)
    back = (part["r_in"], part["r_out"] - h) if outward else (part["r_in"] + h, part["r_out"])
    arc = part["pole_arc_deg"]
    for centre in _pole_centres(part, turn):
        named.append(("rotor_pole", sector(band[0], band[1], centre - arc / 2, arc)))
    named.append(("rotor_air", annulus(*band)))
    named.append(("rotor_core", annulus(*back)))
    return named, {}


def rotor_through(part, turn):
    """A ring of magnets between two gaps (dual-stator machine), magnetised radially and alternating,
    arc `magnet_arc` of the pole pitch, on a non-magnetic carrier."""
    pitch = 360.0 / int(part["poles"])
    arc = part["magnet_arc"] * pitch
    named, magnets = [], {}
    for j, centre in enumerate(_pole_centres(part, turn)):
        name = f"magnet_{j}_0"
        named.append((name, sector(part["r_in"], part["r_out"], centre - arc / 2, arc)))
        magnets[name] = {"kind": "magnet", "side": "rotor", "pole": j, "magnetization": _radial(centre, 1.0 if j % 2 == 0 else -1.0)}
    named.append(("rotor_hub", annulus(part["r_in"], part["r_out"])))
    return named, magnets


LAYOUTS = {
    "surface": rotor_surface,
    "halbach": lambda part, turn: rotor_surface(part, turn, halbach=True),
    "consequent": rotor_consequent,
    "interior_v": rotor_interior_v,
    "spoke": rotor_spoke,
    "flux_barrier": rotor_flux_barrier,
    "flux_barrier_pm": lambda part, turn: rotor_flux_barrier(part, turn, with_magnets=True),
    "salient": rotor_salient,
    "through": rotor_through,
}


# ----------------------------------------------------------------------------- the section

def gaps(params):
    """Air gaps between neighbouring parts: index, radii, and which side carries the rotor."""
    parts = params["parts"]
    out = []
    for i in range(len(parts) - 1):
        a, b = parts[i], parts[i + 1]
        if a["role"] == b["role"] == "stator" and abs(b["r_in"] - a["r_out"]) < 1e-9:
            continue        # two stator rings back to back: one double-sided stator (dual-rotor machine), no gap
        if {a["role"], b["role"]} != {"stator", "rotor"}:
            raise ValueError(f"Parts {i} and {i + 1} are both {a['role']}s.")
        out.append({"index": i, "r1": a["r_out"], "r2": b["r_in"], "rotor": "inner" if a["role"] == "rotor" else "outer"})
    return out


def build(params):
    """Named faces in the order of priority (earlier wins where they overlap), and the region
    description of the named regions."""
    turn = params.get("rotor_angle_deg", 0.0)
    named, regions = [], {}
    stator_count = rotor_count = 0
    rotor_items = []
    for part in params["parts"]:
        if part["role"] == "stator":
            faces, reg = stator_faces(stator_count, part)
            stator_count += 1
            named += faces
            regions.update(reg)
        else:
            faces, reg = LAYOUTS[part["type"]](part, turn)
            if rotor_count:
                # A second rotor (dual-rotor machine): its magnets get names of their own, the first keeps its names.
                tag = f"magnet_r{rotor_count}_"
                faces = [(tag + n[len("magnet_"):] if n.startswith("magnet_") else n, f) for n, f in faces]
                reg = {(tag + n[len("magnet_"):] if n.startswith("magnet_") else n): v for n, v in reg.items()}
            rotor_count += 1
            rotor_items += faces
            regions.update(reg)
    magnets = [(n, f) for n, f in rotor_items if n.startswith("magnet_")]
    poles = [(n, f) for n, f in rotor_items if n == "rotor_pole"]          # iron poles win over the air band
    others = [(n, f) for n, f in rotor_items if not n.startswith("magnet_") and n != "rotor_pole"]
    gap_faces = []
    for g in gaps(params):
        mid = (g["r1"] + g["r2"]) / 2
        gap_faces += [(f"gap_{g['index']}_a", annulus(g["r1"], mid)), (f"gap_{g['index']}_b", annulus(mid, g["r2"]))]
        regions[f"gap_{g['index']}_a"] = {"kind": "air", "side": "rotor" if g["rotor"] == "inner" else "stator",
                                          "gap": g["index"]}
        regions[f"gap_{g['index']}_b"] = {"kind": "air", "side": "rotor" if g["rotor"] == "outer" else "stator",
                                          "gap": g["index"]}
    # coils and magnets first, then the air of slots, pockets and barriers, the gaps, the iron
    coils = [(n, f) for n, f in named if n.startswith("coil_")]
    stator_air = [(n, f) for n, f in named if n == "stator_air"]
    stator_core = [(n, f) for n, f in named if n == "stator_core"]
    rotor_air = [(n, f) for n, f in others if n == "rotor_air"]
    rotor_rest = [(n, f) for n, f in others if n != "rotor_air"]
    order = coils + magnets + poles + stator_air + rotor_air + gap_faces + stator_core + rotor_rest
    bore = params.get("bore_radius", 0.0)
    if bore > 0:
        order.append(("bore", shapes.disk(bore)))
    regions.update({"stator_air": {"kind": "air", "side": "stator"}, "rotor_air": {"kind": "air", "side": "rotor"},
                    "stator_core": {"kind": "core", "side": "stator"}, "rotor_core": {"kind": "core", "side": "rotor"},
                    "rotor_hub": {"kind": "air", "side": "rotor", "hub": True}, "bore": {"kind": "air", "side": "rotor"}})
    outer = params["parts"][-1]["r_out"]
    return order, regions, {"outer_radius": outer, "gaps": gaps(params)}
