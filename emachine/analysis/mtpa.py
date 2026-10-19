"""
Maximum torque per ampere: the current angle (from the induced voltage, core.types.OperatingPoint)
that gives the most torque at a given current amplitude. For a surface PM machine it is 0; machines
with reluctance torque (IPM, SynRM, PMaSynRM) advance the current.
"""

import math

GOLDEN = (math.sqrt(5) - 1) / 2


def best_current_angle(torque_at, low_deg=0.0, high_deg=90.0, tolerance_deg=0.1):
    """
    Golden-section search of the current angle in [low, high] that maximises `torque_at(angle_deg)`
    (a single maximum is assumed). Returns (angle in degrees, torque).
    """
    a, b = float(low_deg), float(high_deg)
    c, d = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
    fc, fd = torque_at(c), torque_at(d)
    while b - a > tolerance_deg:
        if fc >= fd:
            b, d, fd = d, c, fc
            c = b - GOLDEN * (b - a)
            fc = torque_at(c)
        else:
            a, c, fc = c, d, fd
            d = a + GOLDEN * (b - a)
            fd = torque_at(d)
    angle = (a + b) / 2
    return angle, torque_at(angle)
