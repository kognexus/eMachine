"""Materials of an Elmer case: linear or nonlinear B-H curves, and the material of each region."""

import math

from emachine.io.process import StageError

MU0 = 4e-7 * math.pi


def bh_table(mu_r, saturation_T, b_max=4.0, step=0.05):
    """
    B-H curve of a soft magnetic material from two numbers, as a list of (B in T, H in A/m).

    Model (Froehlich-Kennelly): polarisation J = Js * H / (H + a), B = mu0 * H + J, with
    a = Js / (mu0 * (mu_r - 1)). The initial relative permeability is mu_r, and J approaches the
    saturation polarisation Js at high field.
    """
    if mu_r <= 1 or saturation_T <= 0:
        raise ValueError("A B-H curve needs mu_r > 1 and a positive saturation.")
    a = saturation_T / (MU0 * (mu_r - 1.0))
    table = []
    for i in range(int(round(b_max / step)) + 1):
        b = i * step
        c = MU0 * a + saturation_T - b
        table.append((b, (-c + math.sqrt(c * c + 4 * MU0 * b * a)) / (2 * MU0)))
    return table


def material_curve(analysis, prefix):
    """(B, H) table of the material `prefix` ("stator_core" or "rotor_iron"), or None when it is linear."""
    measured = analysis.get(prefix + "_bh_curve")
    if measured:
        table = [(float(b), float(h)) for h, b in measured]
        if table[0] != (0.0, 0.0):
            table.insert(0, (0.0, 0.0))
        for (b0, h0), (b1, h1) in zip(table, table[1:]):
            if b1 <= b0 or h1 <= h0:
                raise StageError(f"'{prefix}_bh_curve' must rise strictly in both H and B.")
        return table
    saturation = analysis.get(prefix + "_saturation_T")
    return bh_table(analysis[prefix + "_mu_r"], saturation) if saturation else None


def material_block(number, name, mu_r, curve=None):
    """Elmer Material section: linear with mu_r, or nonlinear with a (B, H) table."""
    lines = [f"Material {number}", f'  Name = "{name}"']
    if curve:
        lines.append('  H-B Curve = Variable "dummy"\n    Real Cubic Monotone')
        lines += [f"      {b:.5f} {h:.7e}" for b, h in curve]
        lines.append("    End")
    else:
        lines.append(f"  Relative Permeability = {mu_r:g}")
    lines += ["  Relative Permittivity = 1", "  Electric Conductivity = 0", "End", ""]
    return "\n".join(lines)


def material_of(name, region):
    name = name.replace("_coilshell", "")
    kind = region["kind"]
    if kind in ("air", "magnet"):
        return kind
    if kind == "coil":
        return "copper"
    if region["side"] == "stator":
        return "stator core"
    if "non_magnetic" in name:
        return "air"
    return "rotor iron" if ("back_iron" in name or "pole_piece" in name) else "rotor housing"

