"""
Axial machine slices (T60): the machine cut by a cylinder at radius r and unrolled, x = r theta
(0 <= x < 2 pi r, periodic), y = z (axial). Each slice stands for the radial strip `depth` around r;
torque and flux of the machine are the sums over the slices (quasi-3D).

params = {
  "layers": [layer, ...]          from z = 0 upwards; neighbouring stator and rotor layers are separated
                                  by an air gap (z0 of the upper minus z1 of the lower)
  "slices": [{"radius": r, "depth": dr}, ...]
  "rotor_angle_deg": angle
}

Stator layer: {"role": "stator", "z0", "z1", "faces": "up" | "down" | "both" (sides with teeth and an
air gap), "slots", "slot_share" (slot width / slot pitch, constant angle), "slot_depth" (from each
face; "both": through the layer, a yokeless segmented stator), "tip_height", "opening_share",
"notches", "notch_share", "notch_depth", "core": true (false: coreless, the teeth and yoke are air),
"offset_deg", "sides": [[slot, half, phase, sign, share], ...]}.

Rotor layer: {"role": "rotor", "type": "surface" | "halbach" | "consequent" | "salient" | "through",
"z0", "z1", "faces": "up" | "down" | "both", "poles", "magnet_thickness", "magnet_arc" (share of the
pole pitch), "segments", "iron_arc", "pole_arc_deg", "pole_height", "yoke": true, "offset_deg", "polarity": 1 or -1 (-1 on the second rotor
of a yokeless dual-rotor machine, so the flux passes straight through the stator teeth)}.
"""

import math

from .shapes import occ

TOL = 1e-6


class Slice:
    """Drawing on one unrolled slice: x in mm along the circumference, wrapped at the width."""

    def __init__(self, radius, rotor_angle_deg):
        self.r = radius
        self.width = 2 * math.pi * radius
        self.turn = rotor_angle_deg

    def x_of(self, angle_deg):
        return (self.r * math.radians(angle_deg)) % self.width

    def rect(self, x0, y0, x1, y1):
        return occ.addRectangle(x0, y0, 0, x1 - x0, y1 - y0)

    def wrapped(self, centre_deg, arc_deg, y0, y1):
        """Rectangle of the angular width arc centred at the angle, between y0 and y1: one or two faces."""
        w = self.r * math.radians(arc_deg)
        if w >= self.width - TOL:
            return [self.rect(0.0, y0, self.width, y1)]
        x0 = (self.x_of(centre_deg) - w / 2) % self.width
        if self.width - x0 < 1e-4:
            x0 = 0.0
        x1 = x0 + w
        if x1 <= self.width + 1e-4:
            return [self.rect(x0, y0, min(x1, self.width), y1)]
        return [self.rect(x0, y0, self.width, y1), self.rect(0.0, y0, x1 - self.width, y1)]


def stator_layer(sl, s_index, layer):
    q = int(layer["slots"])
    pitch = 360.0 / q
    off = layer.get("offset_deg", 0.0)
    z0, z1 = layer["z0"], layer["z1"]
    depth, tip = layer["slot_depth"], layer.get("tip_height", 0.0)
    faces = layer["faces"]
    slot_arc = layer["slot_share"] * pitch
    sides = {(int(s[0]), int(s[1])): s for s in layer["sides"]}
    if faces == "both":
        body = (z0 + tip, z1 - tip)
        tips = [(z0, z0 + tip), (z1 - tip, z1)]
    elif faces == "up":
        body = (z1 - depth, z1 - tip)
        tips = [(z1 - tip, z1)]
    else:
        body = (z0 + tip, z0 + depth)
        tips = [(z0, z0 + tip)]
    named = []
    for k in range(q):
        centre = off + k * pitch
        for half in (0, 1):
            c = centre - slot_arc / 4 if half == 0 else centre + slot_arc / 4
            name = f"coil_{s_index}_{k}_{half}" if (k, half) in sides else "stator_air"
            named += [(name, f) for f in sl.wrapped(c, slot_arc / 2, *body)]
        if tip > 0:
            opening = layer.get("opening_share", layer["slot_share"]) * pitch
            for y0, y1 in tips:
                named += [("stator_air", f) for f in sl.wrapped(centre, opening, y0, y1)]
    n_notch = int(layer.get("notches", 0))
    if n_notch and layer.get("notch_depth", 0) > 0:
        tau = pitch / (n_notch + 1)
        h = layer["notch_depth"]
        bands = {"up": [(z1 - h, z1)], "down": [(z0, z0 + h)], "both": [(z0, z0 + h), (z1 - h, z1)]}[faces]
        for k in range(q):
            tooth = off + (k + 0.5) * pitch
            for j in range(n_notch):
                angle = tooth + (j - (n_notch - 1) / 2.0) * tau
                for y0, y1 in bands:
                    named += [("stator_air", f) for f in sl.wrapped(angle, layer["notch_share"] * pitch, y0, y1)]
    core = "stator_core" if layer.get("core", True) else "stator_air"
    named.append((core, sl.rect(0.0, z0, sl.width, z1)))
    regions = {f"coil_{s_index}_{k}_{half}": {"kind": "coil", "side": "stator", "stator": s_index, "slot": k, "half": half,
                                              "phase": int(s[2]), "sign": int(s[3]), "share": float(s[4]) if len(s) > 4 else 1.0}
               for (k, half), s in sides.items()}
    return named, regions


def rotor_layer(sl, layer, index):
    poles = int(layer["poles"])
    pitch = 360.0 / poles
    z0, z1 = layer["z0"], layer["z1"]
    kind = layer["type"]
    faces = layer["faces"]
    turn = sl.turn + layer.get("offset_deg", 0.0)
    named, regions = [], {}
    if kind == "through":
        bands = [(z0, z1)]
    else:
        h = layer.get("magnet_thickness", layer.get("pole_height", 0.0))
        bands = {"up": [(z1 - h, z1)], "down": [(z0, z0 + h)], "both": [(z0, z0 + h), (z1 - h, z1)]}[faces]
    for b, (y0, y1) in enumerate(bands):
        up = (y1 >= z1 - TOL) if kind != "through" else True     # this band faces a gap above it
        strong = 1.0 if up else -1.0
        for j in range(poles):
            centre = turn + j * pitch
            north = 1.0 if j % 2 == 0 else -1.0
            if kind == "salient":
                named += [("rotor_pole", f) for f in sl.wrapped(centre, layer["pole_arc_deg"], y0, y1)]
                continue
            if kind == "consequent" and j % 2 == 1:
                named += [("rotor_pole", f) for f in sl.wrapped(centre, layer["iron_arc"] * pitch, y0, y1)]
                continue
            nseg = max(1, int(layer.get("segments", 1)))
            arc = pitch if kind == "halbach" else layer["magnet_arc"] * pitch
            for s in range(nseg):
                mid = centre - arc / 2 + (s + 0.5) * arc / nseg
                name = f"magnet_{index}_{b}_{j}_{s}"
                if kind == "halbach":
                    phase = math.radians((mid - turn) * poles / 2)          # electrical angle from pole 0
                    m = [-math.sin(phase), strong * math.cos(phase)]
                elif kind == "through":
                    m = [0.0, north]
                else:
                    m = [0.0, strong * (north if kind != "consequent" else 1.0)]
                m = [c * layer.get("polarity", 1.0) for c in m]
                named += [(name, f) for f in sl.wrapped(mid, arc / nseg, y0, y1)]
                regions[name] = {"kind": "magnet", "side": "rotor", "magnetization": m, "pole": j}
        named.append(("rotor_air", sl.rect(0.0, y0, sl.width, y1)))
    if kind != "through":
        core = "rotor_core" if layer.get("yoke", True) else "rotor_hub"
        named.append((core, sl.rect(0.0, z0, sl.width, z1)))
    else:
        named.append(("rotor_hub", sl.rect(0.0, z0, sl.width, z1)))
    return named, regions


def gaps(params):
    layers = params["layers"]
    out = []
    for i in range(len(layers) - 1):
        a, b = layers[i], layers[i + 1]
        if {a["role"], b["role"]} != {"stator", "rotor"}:
            raise ValueError(f"Layers {i} and {i + 1} are both {a['role']}s.")
        out.append({"index": i, "y0": a["z1"], "y1": b["z0"], "rotor": "below" if a["role"] == "rotor" else "above"})
    return out


def build(params, k_slice):
    """Named faces (priority order) and regions of slice k."""
    s = params["slices"][k_slice]
    sl = Slice(s["radius"], params.get("rotor_angle_deg", 0.0))
    named, regions, rotor_items = [], {}, []
    s_count = 0
    for i, layer in enumerate(params["layers"]):
        if layer["role"] == "stator":
            faces, reg = stator_layer(sl, s_count, layer)
            s_count += 1
            named += faces
        else:
            faces, reg = rotor_layer(sl, layer, i)
            rotor_items += faces
        regions.update(reg)
    gap_faces = []
    for g in gaps(params):
        mid = (g["y0"] + g["y1"]) / 2
        gap_faces += [(f"gap_{g['index']}_a", sl.rect(0.0, g["y0"], sl.width, mid)),
                      (f"gap_{g['index']}_b", sl.rect(0.0, mid, sl.width, g["y1"]))]
        regions[f"gap_{g['index']}_a"] = {"kind": "air", "side": "rotor" if g["rotor"] == "below" else "stator", "gap": g["index"]}
        regions[f"gap_{g['index']}_b"] = {"kind": "air", "side": "rotor" if g["rotor"] == "above" else "stator", "gap": g["index"]}
    coils = [(n, f) for n, f in named if n.startswith("coil_")]
    magnets = [(n, f) for n, f in rotor_items if n.startswith("magnet_")]
    poles = [(n, f) for n, f in rotor_items if n == "rotor_pole"]
    stator_air = [(n, f) for n, f in named if n == "stator_air"]
    rotor_air = [(n, f) for n, f in rotor_items if n == "rotor_air"]
    stator_core = [(n, f) for n, f in named if n == "stator_core"]
    rotor_rest = [(n, f) for n, f in rotor_items if not n.startswith("magnet_") and n not in ("rotor_air", "rotor_pole")]
    order = coils + magnets + poles + stator_air + rotor_air + gap_faces + stator_core + rotor_rest
    regions.update({"stator_air": {"kind": "air", "side": "stator"}, "rotor_air": {"kind": "air", "side": "rotor"},
                    "stator_core": {"kind": "core", "side": "stator"}, "rotor_core": {"kind": "core", "side": "rotor"},
                    "rotor_hub": {"kind": "air", "side": "rotor", "hub": True}})
    top = params["layers"][-1]["z1"]
    bottom = params["layers"][0]["z0"]
    frame = {"radius": sl.r, "depth": s["depth"], "width": sl.width, "bottom": bottom, "top": top, "gaps": gaps(params)}
    return order, regions, frame
