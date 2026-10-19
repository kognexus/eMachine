"""Surface magnets on the rotor discs."""

from emachine.core.types import Variable

from ...base import RotorLayout


class Surface(RotorLayout):
    name = "surface"
    ticket = "B10"

    def variables(self, spec):
        return [Variable("magnet_thickness_mm", 1.0, 8.0, unit="mm"), Variable("magnet_arc_el_deg", 108.0, 180.0, unit="el. deg")]
