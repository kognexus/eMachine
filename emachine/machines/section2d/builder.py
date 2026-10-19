"""The geometry builder "section2d" (T59, T60): the parts of a radial section or axial slices at a rotor
angle, each meshed in a folder of its own (in this process; Gmsh is not thread-safe, so positions of
one design are meshed one after the other and designs run in separate processes)."""

import copy
import os

from emachine.core.interfaces import GeometryBuilder
from emachine.core.registry import register
from emachine.core.types import Mesh

from .mesher import mesh_part


def parts_of(params):
    if params.get("kind", "radial") == "radial":
        return [("radial", {"kind": "radial"})]
    return [(f"slice{k}", {"kind": "axial", "slice": k}) for k in range(len(params["slices"]))]


@register("geometry", "section2d")
class SectionPartsBuilder(GeometryBuilder):
    def build(self, request, rotor_angle_deg, workdir):
        params = copy.deepcopy(request.parameters)
        params.pop("analysis", None)
        params["rotor_angle_deg"] = float(rotor_angle_deg)
        metas = []
        for folder, part in parts_of(params):
            path = os.path.join(workdir, folder)
            os.makedirs(path, exist_ok=True)
            meta = mesh_part(params, part, os.path.join(path, "section.msh"))
            meta["folder"] = folder
            metas.append(meta)
        meta = {"parts": metas, "parameters": params, "warnings": [],
                "mesh": {"elements": sum(m["mesh"]["elements"] for m in metas)}}
        return Mesh(path="", regions={}, meta=meta)
