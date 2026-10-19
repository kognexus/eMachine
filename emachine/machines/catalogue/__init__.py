"""
Topology catalogue (T58 to T63): every machine of the multi-topology study as a class with its design
variables, geometry checks and the section (machines/section2d) of a design.

    from emachine.machines.catalogue import TOPOLOGIES, get
    topo = get("rfm_spm_in")
    variables = topo.variables(envelope)
    design = topo.design(envelope, values)     # dict for pipeline.drive.evaluate, or GeometryError

The envelope (dict) holds outer and bore diameter, active axial length, mesh fidelity; the variables
are shares and lengths chosen so that most random designs are drawable (docs/design_principles.md
gives the ranges and where they come from).
"""

from .base import GeometryError, Topology  # noqa: F401
from . import axial, hybrid, radial

TOPOLOGIES = {}
for _module in (radial, axial, hybrid):
    for _cls in _module.TOPOLOGIES:
        TOPOLOGIES[_cls.key] = _cls


def get(key):
    return TOPOLOGIES[key]()
