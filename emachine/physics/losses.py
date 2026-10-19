"""
Loss model: iron loss in the stator core and eddy-current loss in the rotor iron, the rotor housing
and the magnets (copper loss: emachine.physics.winding).

Stator core (T31): the flux density of every element over one electrical period is split into
harmonics; each harmonic traces an ellipse with major axis Bmaj and axis ratio R = Bmin / Bmaj, and
loses R * P_r(Bmaj) + (1 - R)^2 * P_a(Bmaj) (Zhu & Ramsden 1998; Guo et al., IEEE TMAG 2014), with
the alternating loss P_a = k_h f B^alpha + k_e (f B)^2 + k_a (f B)^1.5 and, when the material has
rotational data, the rotational loss P_r = P_hr + k_er (f B)^2 + k_ar (f B)^1.5. Without rotational
data the loss is alternating on the major axis.

Rotor parts: the flux density in the rotor frame is averaged over cells of about 1.5 mm (the
meshes of the rotor positions differ, and element-to-element interpolation adds a noise floor that
the eddy-current formula, weighted by k^2, would turn into loss); the noise floor is estimated from the
upper half of the harmonics, and only harmonics above four times the floor count, less the floor. The eddy-current loss of harmonic k
in a part of thickness t is c pi^2 t^2 sigma (k f Bmaj_k)^2 / 6 per m3 (thin plate) times the
skin-effect factor F(t / delta_k) of a plate (Stoll), with delta_k from the incremental permeability
of the material at the steady flux density of the part. Hysteresis in the rotor is left out. This
follows the approach of Guo et al., IEEE TMAG 2014, for a solid mild-steel rotor yoke, with the
skin effect in place of their fitted correction factor.

The stator loss is a_h f + a_e f^2 + a_x f^1.5 in the electrical frequency f, and the rotor loss
is kept as a spectrum per part: one field solution gives the loss at every speed. Not included: mechanical loss, skin effect in thick rotor parts, inverter loss.
"""

import math

import numpy as np

from emachine.core.interfaces import LossModel

NOT_INCLUDED = ["mechanical loss", "skin effect in thick rotor parts", "inverter loss"]


#: above this many point pairs the nearest point is found through a grid of cells (large meshes, T56)
BRUTE_FORCE_PAIRS = 2.0e8


def nearest_by_grid(ref, pts):
    """Index of the nearest point of `pts` for every reference point, exactly: candidates from the
    3 x 3 x 3 cells around the reference's cell; references whose nearest candidate lies farther than
    one cell are searched by brute force."""
    lo = np.minimum(ref.min(axis=0), pts.min(axis=0))
    extent = np.maximum(ref.max(axis=0), pts.max(axis=0)) - lo
    dims = int(np.sum(extent > 1e-12 * max(float(extent.max()), 1e-300)))
    size = float(np.prod(extent[extent > 0])) / len(pts) if dims else 1.0
    h = 2.0 * size ** (1.0 / max(dims, 1)) if dims else 1.0       # about four points per cell
    cell = np.floor((pts - lo) / h).astype(np.int64)
    span = cell.max(axis=0) + 3
    key = ((cell[:, 0] + 1) * span[1] + cell[:, 1] + 1) * span[2] + cell[:, 2] + 1
    order = np.argsort(key, kind="stable")
    sorted_keys = key[order]
    rcell = np.floor((ref - lo) / h).astype(np.int64)
    best = np.full(len(ref), np.inf)
    nearest = np.zeros(len(ref), dtype=np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = rcell + np.array([dx, dy, dz])
                k = ((c[:, 0] + 1) * span[1] + c[:, 1] + 1) * span[2] + c[:, 2] + 1
                start = np.searchsorted(sorted_keys, k, side="left")
                stop = np.searchsorted(sorted_keys, k, side="right")
                count = stop - start
                for j in range(int(count.max()) if len(count) else 0):
                    use = np.nonzero(count > j)[0]
                    idx = order[start[use] + j]
                    d = np.einsum("ij,ij->i", pts[idx] - ref[use], pts[idx] - ref[use])
                    better = d < best[use]
                    best[use[better]] = d[better]
                    nearest[use[better]] = idx[better]
    far = np.nonzero(best > h * h)[0]                  # the true nearest may lie outside the 27 cells
    for start in range(0, len(far), 512):
        block = ref[far[start:start + 512]]
        nearest[far[start:start + 512]] = np.argmin(np.einsum("ij,ij->i", pts, pts)[None, :] - 2.0 * block @ pts.T, axis=1)
    return nearest


def resample_nearest(reference_points, points, values, chunk=512):
    """
    Values at the point of `points` nearest to each reference point.
    The stator mesh differs slightly between rotor positions, so fields are compared on the
    element centroids of one reference position.
    """
    ref = np.asarray(reference_points, dtype=np.float64)
    pts = np.asarray(points, dtype=np.float64)
    values = np.asarray(values)
    if len(ref) == len(pts) and np.array_equal(ref, pts):
        return values
    if len(ref) * len(pts) > BRUTE_FORCE_PAIRS:
        return values[nearest_by_grid(ref, pts)]
    nearest = np.empty(len(ref), dtype=np.int64)
    pts_sq = np.einsum("ij,ij->i", pts, pts)
    for start in range(0, len(ref), chunk):
        block = ref[start:start + chunk]
        distance = pts_sq[None, :] - 2.0 * block @ pts.T      # |p|^2 - 2 r.p ; |r|^2 does not change the argmin
        nearest[start:start + chunk] = np.argmin(distance, axis=1)
    return values[nearest]


def core_peak_field(core_field_files):
    """
    Peak flux density of every stator core element over the electrical cycle.
    Returns (volumes in m3 for the whole ring, peak flux density in T), on the elements of the first file.
    The positions cover half a period; the field reverses over the other half, so the peak of
    the magnitude over the samples is the peak over the cycle.
    """
    first = np.load(core_field_files[0])
    reference = first["centroid"]
    volume = first["volume"] * int(first["periodicity"])
    peak = np.linalg.norm(first["b"], axis=1)
    for path in core_field_files[1:]:
        data = np.load(path)
        magnitude = np.linalg.norm(data["b"], axis=1)
        peak = np.maximum(peak, resample_nearest(reference, data["centroid"], magnitude))
    return volume, peak


def iron_loss_density(material, frequency_Hz, b_peak):
    """Loss in W/kg: k_h f B^alpha + k_e f^2 B^2, plus k_a (f B)^1.5 (excess loss) when the material has k_anomalous."""
    b = np.asarray(b_peak, dtype=float)
    return (material["k_hysteresis"] * frequency_Hz * b ** material["alpha"]
            + material["k_eddy"] * frequency_Hz ** 2 * b ** 2
            + material.get("k_anomalous", 0.0) * (frequency_Hz * b) ** 1.5)


def iron_loss_from_field(spec, frequency_Hz, volume_m3, b_peak):
    """Iron loss in W of core elements with given volumes and peak flux densities."""
    material = spec["materials"]["stator_core"]
    mass = np.asarray(volume_m3, dtype=float) * material["density_kg_m3"]
    return float(np.sum(mass * iron_loss_density(material, frequency_Hz, b_peak)))


def _b_statistics(spec, volume, peak):
    order = np.argsort(peak)
    share = np.cumsum(volume[order]) / volume.sum()
    return {
        "core_b_max_T": float(peak.max()),
        "core_b_p95_T": float(peak[order][min(np.searchsorted(share, 0.95), len(peak) - 1)]),
        "core_b_mean_T": float(np.sum(volume * peak) / volume.sum()),
        "core_mass_kg": float(volume.sum() * spec["materials"]["stator_core"]["density_kg_m3"]),
    }


# ----------------------------------------------------------------------------- field over one period

def _load_sorted(core_field_files):
    data = [np.load(path) for path in core_field_files]
    angles = [float(d["angle_deg"]) if "angle_deg" in d.files else float(k) for k, d in enumerate(data)]
    order = np.argsort(angles)
    return [data[k] for k in order], np.asarray(angles)[order]


def _electrical_period_deg(data):
    """Mechanical degrees of one electrical period: given by the solver, or one sector (= one pole pair)."""
    if "electrical_period_deg" in data.files:
        return float(data["electrical_period_deg"])
    return 360.0 / int(data["periodicity"])


def _covers_half_period(angles, period):
    """True when the rotor positions cover half an electrical period (one pole pitch), False for a full one."""
    if len(angles) < 2:
        return True
    step = float(np.min(np.diff(angles)))
    return len(angles) * step < 0.75 * period


def stator_series(core_field_files):
    """
    Flux density of every stator core element over one electrical period, on the elements of the
    first file. Returns (volumes in m3 for the whole ring, B array (elements, samples, 3)). Positions
    over half a period are completed with the reversed field of the other half, B(t + T/2) = -B(t).
    """
    data, angles = _load_sorted(core_field_files)
    reference = data[0]["centroid"]
    volume = data[0]["volume"] * int(data[0]["periodicity"])
    b = np.stack([data[0]["b"]] + [resample_nearest(reference, d["centroid"], d["b"]) for d in data[1:]], axis=1)
    if _covers_half_period(angles, _electrical_period_deg(data[0])):
        b = np.concatenate([b, -b], axis=1)
    return volume, b


#: Size of the rotor-frame cells over which the rotor field is averaged, in m.
ROTOR_CELL_M = 1.5e-3


def rotor_series(core_field_files, cell_m=ROTOR_CELL_M):
    """
    Flux density of the rotor parts over one electrical period in the rotor frame, cylindrical
    components, averaged over cells (radius, angle, axial position; one kind of part per cell)
    that are present at every position. Returns (cell volumes in m3 for the whole ring, kind codes,
    B array (cells, samples, 3), eddy widths in m by kind) or None without rotor data.

    The angular cells divide one pole pitch into a whole number, so that over half a period the
    other half follows exactly from b(x, t + T/2) = -b(x - pole pitch, t) in the rotor frame.
    """
    data, angles = _load_sorted(core_field_files)
    if "rotor_b" not in data[0].files or len(data[0]["rotor_b"]) == 0:
        return None
    periodicity = int(data[0]["periodicity"])
    sector = 2 * math.pi / periodicity                 # extent of the model (wrapping)
    pitch = math.radians(_electrical_period_deg(data[0])) / 2        # one pole pitch
    ref = data[0]["rotor_centroid"]
    start = float(np.arctan2(ref[:, 1], ref[:, 0]).min()) - 1e-9
    radius = float(np.median(np.hypot(ref[:, 0], ref[:, 1])))
    per_pitch = max(1, int(round(radius * pitch / cell_m)))          # angular cells per pole pitch
    width = pitch / per_pitch
    cells_around = int(round(sector / width))

    def cells(d):
        c = d["rotor_centroid"]
        r, phi = np.hypot(c[:, 0], c[:, 1]), np.arctan2(c[:, 1], c[:, 0])
        j = np.floor(np.mod(phi - start, sector) / width).astype(np.int64) % cells_around
        keys = np.column_stack([d["rotor_kind"].astype(np.int64), np.floor(r / cell_m).astype(np.int64), j,
                                np.floor(c[:, 2] / cell_m).astype(np.int64)])
        unique, inverse = np.unique(keys, axis=0, return_inverse=True)
        inverse = inverse.ravel()
        v = d["rotor_volume"]
        volume = np.bincount(inverse, v, len(unique))
        b = np.column_stack([np.bincount(inverse, v * d["rotor_b"][:, i], len(unique)) for i in range(3)])
        return {tuple(k): (vol, bb) for k, vol, bb in zip(unique.tolist(), volume, b / volume[:, None])}

    per_position = [cells(d) for d in data]
    half = _covers_half_period(angles, _electrical_period_deg(data[0]))

    def partner(key):                       # the cell one pole pitch earlier in the rotor frame
        return (key[0], key[1], (key[2] - per_pitch) % cells_around, key[3])

    common = set(per_position[0])
    for cell in per_position[1:]:
        common &= set(cell)
    if half:
        common = {k for k in common if partner(k) in common}
    keys = sorted(common)
    series = [[cell[k][1] for k in keys] for cell in per_position]
    if half:
        series += [[-cell[partner(k)][1] for k in keys] for cell in per_position]
    volume = np.array([per_position[0][k][0] for k in keys]) * periodicity
    kinds = np.array([k[0] for k in keys], dtype=np.int64)
    widths = data[0]["rotor_eddy_width_m"] if "rotor_eddy_width_m" in data[0].files else None
    return volume, kinds, np.stack([np.array(s) for s in series], axis=1), widths


def harmonic_ellipses(b):
    """
    Major and minor axes of the ellipse of every harmonic k = 1 .. N/2 - 1 of B over one period.
    b: (elements, N samples, 3). Returns (bmaj, bmin), each (elements, harmonics), in T.
    """
    n = b.shape[1]
    spectrum = np.fft.rfft(b, axis=1) * (2.0 / n)                  # B = sum a_k cos + b_k sin
    a, c = spectrum.real[:, 1:n // 2, :], -spectrum.imag[:, 1:n // 2, :]
    aa, cc, ac = (a * a).sum(-1), (c * c).sum(-1), (a * c).sum(-1)
    mid, half = (aa + cc) / 2, np.sqrt(((aa - cc) / 2) ** 2 + ac ** 2)
    return np.sqrt(mid + half), np.sqrt(np.maximum(mid - half, 0.0))


def rotational_hysteresis_per_cycle(rotational, b):
    """Rotational hysteresis loss per cycle in J/kg under a circular flux density b (Zhu & Ramsden 1998)."""
    a1, a2, a3, bs = rotational["a1"], rotational["a2"], rotational["a3"], rotational["saturation_T"]
    s = 1.0 - np.asarray(b, dtype=float) / bs * math.sqrt(1.0 - 1.0 / (a2 ** 2 + a3 ** 2))
    s = np.clip(s, 1e-6, 1.0)
    u, v = 1.0 / s, 1.0 / (2.0 - s)
    return a1 * (u / ((a2 + u) ** 2 + a3 ** 2) - v / ((a2 + v) ** 2 + a3 ** 2))


def stator_element_coefficients(material, b):
    """
    Loss coefficients per kg of every element: loss in W/kg = h f + e f^2 + x f^1.5 at the
    electrical frequency f. b: (elements, samples over one period, 3).
    """
    bmaj, bmin = harmonic_ellipses(b)
    k = np.arange(1, bmaj.shape[1] + 1)[None, :]
    rotational = material.get("rotational")
    ratio = np.where(bmaj > 1e-12, bmin / np.maximum(bmaj, 1e-12), 0.0) if rotational else np.zeros_like(bmaj)
    alt = (1.0 - ratio) ** 2
    h = k * alt * material["k_hysteresis"] * bmaj ** material["alpha"]
    e = k ** 2 * bmaj ** 2 * alt * material["k_eddy"]
    x = k ** 1.5 * bmaj ** 1.5 * alt * material.get("k_anomalous", 0.0)
    if rotational:
        h = h + k * ratio * rotational_hysteresis_per_cycle(rotational, bmaj)
        e = e + k ** 2 * bmaj ** 2 * ratio * rotational["k_eddy"]
        x = x + k ** 1.5 * bmaj ** 1.5 * ratio * rotational.get("k_anomalous", 0.0)
    return h.sum(1), e.sum(1), x.sum(1)


def skin_factor(xi):
    """Eddy-current loss of a plate with skin effect over its low-frequency value, xi = thickness / skin depth."""
    xi = np.asarray(xi, dtype=float)
    out = np.ones_like(xi)
    mid = (xi > 1e-3) & (xi <= 30.0)
    x = xi[mid]
    out[mid] = 3.0 / x * (np.sinh(x) - np.sin(x)) / (np.cosh(x) - np.cos(x))
    out[xi > 30.0] = 3.0 / xi[xi > 30.0]
    return out


def incremental_mu_r(material, b):
    """Incremental relative permeability dB / (mu0 dH) of a material at flux density b (B-H model of the solver)."""
    b = float(b)
    curve = material.get("bh_curve")
    if curve:
        points = [(0.0, 0.0)] + [tuple(map(float, p)) for p in curve if tuple(p) != (0, 0)]
        h = np.array([p[0] for p in points])
        bb = np.array([p[1] for p in points])
        k = int(np.clip(np.searchsorted(bb, b), 1, len(bb) - 1))
        return max((bb[k] - bb[k - 1]) / (h[k] - h[k - 1]) / MU0, 1.0)
    mu_r, js = float(material.get("mu_r", 1.0)), material.get("saturation_T")
    if not js or mu_r <= 1.0:
        return max(mu_r, 1.0)
    a = js / (MU0 * (mu_r - 1.0))                     # Froehlich-Kennelly, as tfm_pipeline.bh_table
    j = min(b, 0.999 * js)
    hh = a * j / (js - j)
    return 1.0 + js * a / (hh + a) ** 2 / MU0


MU0 = 4e-7 * math.pi

#: rotor_kind code of tfm_pipeline.ROTOR_LOSS_KINDS -> material name in the specification
ROTOR_PARTS = {0: "rotor_iron", 1: "rotor_housing", 2: "magnet"}


def rotor_spectra(series):
    """
    Per rotor part: harmonic spectrum S_k = sum of cell volume * Bmaj_k^2 (m3 T2) after removing the
    noise floor, the eddy-current width and the mean steady flux density.
    """
    out = {}
    for code, name in ROTOR_PARTS.items():
        out[f"{name}_spectrum"], out[f"{name}_width_m"], out[f"{name}_b_dc_T"] = [], 0.0, 0.0
    if series is None:
        return out
    volume, kinds, b, widths = series
    bmaj, _ = harmonic_ellipses(b)
    power = bmaj ** 2
    count = power.shape[1]
    if count >= 6:
        # Keep a harmonic only where it stands clearly above the noise floor (power above four times
        # the floor, twice its amplitude); subtracting the floor alone leaves the harmonics where the
        # noise happens to be high, and the k^2 weighting makes those count.
        noise = np.median(power[:, count // 2:], axis=1, keepdims=True)
        power = np.where(power > 4.0 * noise, power - noise, 0.0)
    dc = np.linalg.norm(b.mean(axis=1), axis=1)
    for code, name in ROTOR_PARTS.items():
        sel = kinds == code
        if not np.any(sel):
            continue
        out[f"{name}_spectrum"] = (volume[sel, None] * power[sel]).sum(axis=0).tolist()
        out[f"{name}_width_m"] = float(widths[code]) if widths is not None else 0.0
        out[f"{name}_b_dc_T"] = float(np.sum(volume[sel] * dc[sel]) / np.sum(volume[sel]))
    return out


def rotor_loss(coefficients, frequency_Hz, materials):
    """
    Eddy-current loss in W of each rotor part of one phase at an electrical frequency (arrays
    allowed: spectra may carry leading axes that broadcast with the frequency).
    """
    f = np.asarray(frequency_Hz, dtype=float)
    out = {}
    for name in ROTOR_PARTS.values():
        spectrum = np.asarray(coefficients.get(f"{name}_spectrum", []), dtype=float)
        part = materials.get(name) or {}
        sigma = part.get("conductivity_S_m")
        if spectrum.size == 0 or not sigma:
            out[name] = np.zeros_like(f)
            continue
        width = part.get("eddy_width_mm")
        width = width / 1000.0 if width else coefficients.get(f"{name}_width_m", 0.0)
        if width <= 0:
            out[name] = np.zeros_like(f)
            continue
        mu = incremental_mu_r(part, coefficients.get(f"{name}_b_dc_T", 0.0))
        scale = part.get("eddy_correction", 1.0) * math.pi ** 2 * width ** 2 * sigma / 6.0
        total = 0.0
        for k in range(spectrum.shape[-1]):
            fk = (k + 1) * f
            with np.errstate(divide="ignore"):
                depth = np.sqrt(2.0 / (2 * math.pi * np.maximum(fk, 1e-12) * MU0 * mu * sigma))
            total = total + scale * spectrum[..., k] * fk ** 2 * skin_factor(width / depth)
        out[name] = total
    return out


def iron_loss_coefficients(spec, core_field_files):
    """
    Iron loss of one phase (the field of several phases is shared out) as a function of the electrical frequency f, from the field over the
    sweep: stator core a_h f + a_e f^2 + a_x f^1.5, and the eddy-current spectra of the rotor parts
    (see rotor_loss). The field does not depend on speed, so one field solution gives the loss at
    every speed.
    """
    material = spec["materials"]["stator_core"]
    volume, b = stator_series(core_field_files)
    share = 1.0 / phases_in_field(core_field_files[0])
    mass = volume * material["density_kg_m3"] * share
    h, e, x = stator_element_coefficients(material, b)
    peak = np.linalg.norm(b, axis=2).max(axis=1)
    rotor = rotor_series(core_field_files)
    if rotor is not None:
        rotor = (rotor[0] * share,) + tuple(rotor[1:])
    return {"a_h": float(np.sum(mass * h)), "a_e": float(np.sum(mass * e)), "a_x": float(np.sum(mass * x)),
            **rotor_spectra(rotor),
            **_b_statistics(spec, volume, peak)}


def phases_in_field(core_field_file):
    """Number of phases whose loss a field file holds: 1 for the sector of one TFM phase (default),
    all phases for the section of a whole radial flux machine (key `phases`)."""
    with np.load(core_field_file) as data:
        return int(data["phases"]) if "phases" in data.files else 1


#: scalar coefficients of the stator loss: interpolated smoothly between load levels
COEFFICIENTS = ("a_h", "a_e", "a_x")
#: rotor spectra: interpolated smoothly between load levels, harmonic by harmonic
SPECTRA = tuple(f"{name}_spectrum" for name in ROTOR_PARTS.values())


def loss_at(coefficients, frequency_Hz, materials):
    """(stator core loss, rotor loss) in W of one phase at an electrical frequency (arrays allowed)."""
    c = coefficients
    f = np.asarray(frequency_Hz, dtype=float)
    stator = c.get("a_h", 0.0) * f + c.get("a_e", 0.0) * f ** 2 + c.get("a_x", 0.0) * f ** 1.5
    rotor = sum(rotor_loss(c, f, materials).values())
    return stator, rotor


def stator_loss_density(material, frequency_Hz, core_field_files):
    """(volumes in m3, loss density in W/kg) of every stator core element at an electrical frequency."""
    volume, b = stator_series(core_field_files)
    h, e, x = stator_element_coefficients(material, b)
    f = float(frequency_Hz)
    return volume, h * f + e * f ** 2 + x * f ** 1.5


def iron_loss(spec, d, core_field_files):
    """Iron loss of one phase in W at the operating frequency: stator core and rotor, with statistics."""
    c = iron_loss_coefficients(spec, core_field_files)
    stator, rotor = loss_at(c, d["electrical_frequency_Hz"], spec["materials"])
    return {"iron_loss_W": float(stator), "rotor_loss_W": float(rotor),
            **{k: v for k, v in c.items() if k.startswith("core_")}}


class CoreAndRotorLoss(LossModel):
    """LossModel: stator core per harmonic ellipse and rotor eddy currents (this module)."""

    def coefficients(self, materials, field_files):
        return iron_loss_coefficients({"materials": materials}, field_files)

    def at(self, coefficients, frequency_Hz, materials):
        return loss_at(coefficients, frequency_Hz, materials)
