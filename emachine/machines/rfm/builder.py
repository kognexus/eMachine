"""The geometry builder "rfm.section2d": meshes the 2D cross-section of a radial flux machine at a rotor angle."""

import copy
import json
import os
import sys

from emachine.core.interfaces import GeometryBuilder
from emachine.core.registry import register
from emachine.core.types import Mesh
from emachine.io.process import run


@register("geometry", "rfm.section2d")
class SectionBuilder(GeometryBuilder):
    def build(self, request, rotor_angle_deg, workdir):
        os.makedirs(workdir, exist_ok=True)
        params = copy.deepcopy(request.parameters)
        params.pop("analysis", None)
        params["rfm"]["rotor_angle_deg"] = float(rotor_angle_deg)
        with open(os.path.join(workdir, "section_parameters.json"), "w") as f:
            json.dump(params, f, indent=1)
        run([sys.executable, "-m", "emachine.machines.rfm.section", "--params", "section_parameters.json",
             "--out", "section.msh"], workdir, os.path.join(workdir, "mesh.log"))
        with open(os.path.join(workdir, "section.regions.json")) as f:
            meta = json.load(f)
        meta["warnings"] = []
        return Mesh(path=os.path.join(workdir, "section.msh"), regions=meta["regions"], meta=meta)
