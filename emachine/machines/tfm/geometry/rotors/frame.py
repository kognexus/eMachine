"""The frame shared by all rotor types: radii, rows and pole pitch of the rotor ring."""

import math
import sys


class RotorType:
    """One kind of rotor. Subclasses describe their magnets; `build` may replace the whole ring."""

    code = ""
    custom_build = False         # True: the type builds the whole ring itself (build_ring)

    def magnet_height(self, rp):
        return rp["magnet_thickness"]

    def magnets(self, frame, rp):
        """(electrical angles of the magnets of one pole pair, angular span of one magnet, spoke width)."""
        raise NotImplementedError

    def seed(self, frame, rp, z0, z1, span, width):
        """The magnet solid of one row at angle 0."""
        raise NotImplementedError

    def row_extras(self, frame, rp, z0, z1, width, shift=0.0):
        """Further solids of one row (or skew slice), turned by `shift`: list of (dimension tag, name)."""
        return []

    def core_name(self, outrunner):
        raise NotImplementedError


class RotorFrame:
    def __init__(self, rp, kind):
        self.outrunner = rp["configuration"].lower() == "outrunner"
        self.poles = int(rp["poles"])
        if self.poles % 2:
            sys.exit("rotor.poles must be even.")
        self.pitch = 2 * math.pi / self.poles
        self.stack = rp["stack_length"]
        self.z_bottom = -self.stack / 2
        self.rows = int(rp["magnet_rows"])
        self.row_gap = rp["row_gap"] if self.rows > 1 else 0.0
        self.alternate = self.rows > 1 and rp["alternate_rows"]
        self.row_w = (self.stack - (self.rows - 1) * self.row_gap) / self.rows
        if self.row_w <= 0:
            sys.exit("The row gaps use up the whole stack length.")
        hm = kind.magnet_height(rp)
        if self.outrunner:
            self.ra = rp["inner_diameter"] / 2
            self.rb = self.ra + hm
            self.core_in, self.core_out = self.rb, rp["outer_diameter"] / 2
            self.gap_radius = self.ra
        else:
            self.rb = rp["outer_diameter"] / 2
            self.ra = self.rb - hm
            self.core_in, self.core_out = rp["shaft_diameter"] / 2, self.ra
            self.gap_radius = self.rb
        self.hm = hm
        if self.core_out <= self.core_in + 1e-6:
            sys.exit("The magnets leave no room for the rotor core: check the rotor diameters.")
