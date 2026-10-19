"""Surface magnets: one radially magnetised arc magnet per pole, on a soft-iron back."""

from ..shapes import ring_sector
from .frame import RotorType


class Surface(RotorType):
    code = "surface"

    def magnets(self, f, rp):
        return [0.0, 180.0], rp["magnet_arc_ratio"] * f.pitch, 0.0

    def seed(self, f, rp, z0, z1, span, width):
        return ring_sector(f.ra, f.rb, z0, z1, -span / 2, span)

    def core_name(self, outrunner):
        return "rotor_back_iron"
