"""Halbach array: segments_per_pole magnets per pole, magnetisation turning along the array."""

from ..shapes import ring_sector
from .frame import RotorType


class Halbach(RotorType):
    code = "halbach"

    def magnets(self, f, rp):
        seg = int(rp["segments_per_pole"])
        return [k * 180.0 / seg for k in range(2 * seg)], f.pitch / seg, 0.0

    def seed(self, f, rp, z0, z1, span, width):
        return ring_sector(f.ra, f.rb, z0, z1, -span / 2, span)

    def core_name(self, outrunner):
        return "rotor_housing" if outrunner else "rotor_hub"
