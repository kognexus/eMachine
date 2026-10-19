"""What every radial flux machine shares: the slotted stator around the rotor, the winding layout."""

from ..base import SlottedMachine


class RadialFlux(SlottedMachine):
    """Slotted stator, rotor in the bore; dimensions of SlottedMachine. Subclasses: one per principle."""

    flux_path = "rfm"

    def layout(self, spec, values):
        """The winding of the design (winding_layout.Layout); ValueError when it is not balanced."""
        return self.winding_layout(spec, values)
