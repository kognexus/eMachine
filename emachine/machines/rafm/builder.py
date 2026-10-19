"""The geometry builder "rafm.quasi3d" (T55): the radial section and the axial slices of the raxial
machine at a rotor angle, each meshed by machines/rafm/section.py in a folder of its own."""

import copy
import json
import os
import sys

from emachine.core.interfaces import GeometryBuilder
from emachine.core.registry import register
from emachine.core.types import Mesh
from emachine.io.process import run


@register("geometry", "rafm.quasi3d")
class Quasi3DBuilder(GeometryBuilder):
    def build(self, request, rotor_angle_deg, workdir):
        os.makedirs(workdir, exist_ok=True)
        params = copy.deepcopy(request.parameters)
        params.pop("analysis", None)
        params["rafm"]["rotor_angle_deg"] = float(rotor_angle_deg)
        with open(os.path.join(workdir, "parts_parameters.json"), "w") as f:
            json.dump(params, f, indent=1)
        parts = [("radial", "radial", 0)] + [(f"axial{i}", "axial", i) for i in range(len(params["rafm"]["slices"]))]
        metas = []
        for name, part, index in parts:
            folder = os.path.join(workdir, name)
            os.makedirs(folder, exist_ok=True)
            run([sys.executable, "-m", "emachine.machines.rafm.section", "--params", os.path.join("..", "parts_parameters.json"),
                 "--part", part, "--slice", str(index), "--out", "section.msh"], folder, os.path.join(folder, "mesh.log"))
            with open(os.path.join(folder, "section.regions.json")) as f:
                meta = json.load(f)
            meta["folder"] = name
            metas.append(meta)
        meta = {"parts": metas, "parameters": params, "warnings": [],
                "mesh": {"elements": sum(m["mesh"]["elements"] for m in metas)}}
        return Mesh(path="", regions={}, meta=meta)
