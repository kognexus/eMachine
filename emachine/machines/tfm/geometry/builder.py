"""The geometry builder "tfm.sector3d": meshes the periodic sector of a TFM phase at a rotor angle."""

import copy
import json
import os
import sys

from emachine.core.interfaces import GeometryBuilder
from emachine.core.registry import register
from emachine.core.types import Mesh
from emachine.io.process import read_text, run


def make_mesh(params, angle, posdir):
    """Runs the sector mesher (sector.py) for the parameters and the rotor angle; returns the region description."""
    derived = copy.deepcopy(params)
    derived.pop("analysis", None)
    derived.setdefault("mesh", {})["rotor_angle_deg"] = angle
    with open(os.path.join(posdir, "mesh_parameters.json"), "w") as f:
        json.dump(derived, f, indent=2)
    run([sys.executable, "-m", "emachine.machines.tfm.geometry.sector", "--params", "mesh_parameters.json",
         "--out", "sector.msh"], posdir, os.path.join(posdir, "mesh.log"))
    with open(os.path.join(posdir, "sector.regions.json")) as f:
        return json.load(f)


@register("geometry", "tfm.sector3d")
class SectorBuilder(GeometryBuilder):
    def build(self, request, rotor_angle_deg, workdir):
        os.makedirs(workdir, exist_ok=True)
        meta = make_mesh(request.parameters, rotor_angle_deg, workdir)
        meta["warnings"] = [line.strip() for line in read_text(os.path.join(workdir, "mesh.log")).splitlines()
                            if "WARNING" in line]
        return Mesh(path=os.path.join(workdir, "sector.msh"), regions=meta["regions"], meta=meta)
