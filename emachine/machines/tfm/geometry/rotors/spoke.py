"""Flux-concentrating (spoke) rotor: tangentially magnetised spokes between iron pole pieces."""

import math
import sys

from ..shapes import occ, ring
from .frame import RotorType


class Spoke(RotorType):
    code = "flux_concentrating"

    def magnet_height(self, rp):
        return rp["fc_magnet_height"]

    def magnets(self, f, rp):
        wm = rp["fc_magnet_width"]
        if wm >= f.ra * math.sin(f.pitch / 2):
            sys.exit("The spoke magnets are too wide for this pole count.")
        return [90.0, 270.0], f.pitch, wm

    def seed(self, f, rp, z0, z1, span, width):
        block = occ.addBox(0.5 * f.ra, -width / 2, z0, f.rb + f.hm - 0.5 * f.ra, width, f.row_w)
        out, _ = occ.intersect([(3, block)], [(3, ring(f.ra, f.rb, z0, z1))])
        return out[0][1]

    def row_extras(self, f, rp, z0, z1, width, shift=0.0):
        """Iron pole pieces between the spokes."""
        slots = []
        for j in range(f.poles):
            s = occ.addBox(0.8 * f.ra, -width / 2, z0 - 1, f.rb + f.hm - 0.8 * f.ra, width, z1 - z0 + 2)
            occ.rotate([(3, s)], 0, 0, 0, 0, 0, 1, (j + 0.5) * f.pitch + shift)
            slots.append((3, s))
        out, _ = occ.cut([(3, ring(f.ra, f.rb, z0, z1))], slots)
        return [(dt, "rotor_pole_piece") for dt in out if dt[0] == 3]

    def core_name(self, outrunner):
        return "rotor_housing_non_magnetic" if outrunner else "rotor_hub_non_magnetic"
