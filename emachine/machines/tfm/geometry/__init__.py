"""
Geometry of the TFM sector model: stator types (stators/), rotor types (rotors/), shared shapes,
parameter defaults, and the sector mesher (sector.py) with its command line (emachine mesh).
"""

from .parameters import DEFAULTS, merged  # noqa: F401
from .rotors import build_rotor  # noqa: F401
from .shapes import copies_at, occ, ring, ring_sector, slug  # noqa: F401
from .stators import build_stator, valley_cutter, valley_profile  # noqa: F401
