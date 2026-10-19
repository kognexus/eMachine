"""
Elmer magnetostatics of a 3D periodic sector with a sliding surface in the air gap (A-V
formulation, Whitney elements). The geometry comes as a Gmsh mesh with a region description (the
"tfm.sector3d" geometry builder); the coil current is applied as an equivalent magnetisation.

For every rotor position: the mesh is converted for Elmer (millimetres -> metres) and the rotor and
stator meshes are joined node for node across the sliding surface; a case is written from the
region description and the settings; the problem is solved; torque, field energy and the flux
linked by the coil are read and scaled from the sector to the whole ring.
"""

import math
import os
import re
import shutil
import time

import numpy as np

from emachine.core.interfaces import FieldSolver
from emachine.core.registry import register
from emachine.core.types import FieldSample
from emachine.io.process import StageError, read_text, run

from . import ELMER_HOME
from .fields import ROTOR_LOSS_KINDS, coil_flux, save_core_field
from .materials import MU0, material_block, material_curve, material_of
from .results import read_fields, read_names, read_scalars

ANALYSIS_DEFAULTS = {
    "magnet_remanence_T": 1.3,       # NdFeB N42 is about 1.3 T
    "magnet_mu_r": 1.05,
    "stator_core_mu_r": 500.0,       # linear; soft magnetic composite is roughly 300-700
    "rotor_iron_mu_r": 1000.0,       # back iron and pole pieces
    "rotor_housing_mu_r": 1.0,       # hub or housing behind a Halbach array (1 = non-magnetic)
    "stator_core_saturation_T": None,  # saturation polarisation; None = linear with stator_core_mu_r
    "stator_core_bh_curve": None,      # optional measured curve [[H in A/m, B in T], ...]; overrides the line above
    "rotor_iron_saturation_T": None,
    "rotor_iron_bh_curve": None,
    "nonlinear_tolerance": 1e-5,
    "nonlinear_max_iterations": 40,
    "coil_turns": 20,
    "coil_current_A": 0.0,           # current in each turn; 0 = no-load
    "positions": 8,                  # rotor positions over the sweep (command line of emachine solve)
    "sweep_start_deg": 0.0,
    "sweep_deg": None,               # mechanical angle covered; default = one electrical period
    "keep_fields": False,            # keep the .vtu field file of every position (large) for ParaView
    "linear_tolerance": 1e-8,
    "linear_max_iterations": 3000,
}


def convert_mesh(posdir, meta):
    """Gmsh -> Elmer. The two sliding surfaces carry the same nodes, so merging joins rotor and stator."""
    shutil.rmtree(os.path.join(posdir, "mesh"), ignore_errors=True)
    run([os.path.join(ELMER_HOME, "bin", "ElmerGrid"), "14", "2", "sector.msh", "-autoclean",
         "-scale", "0.001", "0.001", "0.001", "-merge", "1.0e-7", "-out", "mesh"],
        posdir, os.path.join(posdir, "convert.log"))
    with open(os.path.join(posdir, "mesh", "mesh.header")) as f:
        nodes = int(f.readline().split()[0])
    sector = meta["sector"]
    expected = meta["mesh"]["nodes"] - (sector["sliding_cells_theta"] + 1) * (sector["sliding_cells_z"] + 1)
    if nodes != expected:
        raise StageError(f"Sliding surfaces did not join cleanly: {nodes} nodes after merging, expected {expected}.")



def write_case(analysis, meta, posdir, ampere_turns):
    """Writes case.sif for the coil ampere-turns of this position."""
    sector, regions = meta["sector"], meta["regions"]
    bodies, boundaries = read_names(posdir)
    missing = [name for name in regions if name not in bodies]
    if missing:
        raise StageError(f"Regions missing from the converted mesh: {missing}")
    order = sorted(regions, key=lambda name: bodies[name])
    if [bodies[name] for name in order] != list(range(1, len(order) + 1)):
        raise StageError("Body numbers from ElmerGrid are not consecutive.")

    coil_info = meta.get("coil") or {}
    if "area_mm2" in coil_info:
        coil_area = coil_info["area_mm2"] * 1e-6
    else:                                   # meshes written before the coil area was recorded (T35)
        stator = meta["parameters"]["stator"]
        coil_area = stator["coil_height"] * (stator["slot_width"] - 2 * stator["coil_clearance"]) * 1e-6
    current_density = ampere_turns / coil_area
    m0 = analysis["magnet_remanence_T"] / (MU0 * analysis["magnet_mu_r"])
    materials = {
        "air": 1.0,
        "copper": 1.0,
        "magnet": analysis["magnet_mu_r"],
        "stator core": analysis["stator_core_mu_r"],
        "rotor iron": analysis["rotor_iron_mu_r"],
        "rotor housing": analysis["rotor_housing_mu_r"],
    }
    material_ids = {name: i + 1 for i, name in enumerate(materials)}
    curves = {"stator core": material_curve(analysis, "stator_core"),
              "rotor iron": material_curve(analysis, "rotor_iron")}
    used = {material_of(name, regions[name]) for name in order}
    nonlinear = any(curves.get(name) for name in used)

    out = ["! Written by emachine (solvers/elmer/sector3d.py). Change the parameter file and re-run instead of editing this file.",
           'Check Keywords "Warn"\n',
           'Header\n  Mesh DB "." "mesh"\n  Results Directory "results"\nEnd\n',
           "Simulation\n  Max Output Level = 5\n  Coordinate System = Cartesian\n"
           "  Simulation Type = Steady State\n  Steady State Max Iterations = 1\nEnd\n",
           "Constants\n  Permeability of Vacuum = 1.25663706212e-6\nEnd\n"]
    w = out.append

    # The coil current is applied as an equivalent magnetisation M with curl M = J, which Elmer handles
    # robustly: axial M that ramps across the coil and is constant in the "coil shell" slab.
    coil_meta = meta.get("coil") or {}
    r0, r1 = coil_meta.get("r0_mm", 0.0) * 1e-3, coil_meta.get("r1_mm", 0.0) * 1e-3
    inward = coil_meta.get("shell") == "inward"
    shell_m = current_density * (r1 - r0) * (1 if inward else -1)
    loaded = abs(current_density) > 0
    shell_force = None

    forces, rotor_solids, coil_bodies, core_bodies = [], [], [], []
    rotor_loss_bodies = {"rotor iron": [], "rotor housing": [], "magnet": []}
    for index, name in enumerate(order, start=1):
        region = regions[name]
        lines = [f"Body {index}", f'  Name = "{name}"', f"  Target Bodies(1) = {bodies[name]}",
                 "  Equation = 1", f"  Material = {material_ids[material_of(name, region)]}"]
        if region["kind"] == "magnet":
            if region.get("axis") == "axial":           # ring magnet magnetised along the machine axis
                forces.append([f'  Name = "{name}"', f"  Magnetization 3 = Real {m0 * region['direction']:.8e}"])
            else:
                # Uniform magnetisation: direction = centre angle of the magnet + its angle from radial.
                phi = math.radians(region["centre_deg"] + region["beta_deg"])
                forces.append([f'  Name = "{name}"', f"  Magnetization 1 = Real {m0 * math.cos(phi):.8e}",
                               f"  Magnetization 2 = Real {m0 * math.sin(phi):.8e}"])
            lines.append(f"  Body Force = {len(forces)}")
        elif region["kind"] == "coil":
            coil_bodies.append(index)
            if loaded:
                edge = r1 if inward else r0  # M falls to zero at the coil face next to the air gap
                forces.append(['  Name = "coil current"',
                               "  Magnetization 3 = Variable Coordinate 1, Coordinate 2\n"
                               f'    Real MATC "{current_density:.8g}*({edge:.9g}-sqrt(tx(0)^2+tx(1)^2))"'])
                lines.append(f"  Body Force = {len(forces)}")
        elif region.get("coil_shell") and loaded:
            if shell_force is None:
                forces.append(['  Name = "coil current shell"', f"  Magnetization 3 = Real {shell_m:.8e}"])
                shell_force = len(forces)
            lines.append(f"  Body Force = {shell_force}")
        if region["side"] == "rotor" and region["kind"] != "air":
            rotor_solids.append(index)
        if region["side"] == "stator" and region["kind"] == "core":
            core_bodies.append(index)
        if region["side"] == "rotor" and material_of(name, region) in rotor_loss_bodies:
            rotor_loss_bodies[material_of(name, region)].append(index)
        w("\n".join(lines) + "\nEnd\n")

    for i, lines in enumerate(forces, start=1):
        w(f"Body Force {i}\n" + "\n".join(lines) + "\nEnd\n")
    for name, mu in materials.items():
        w(material_block(material_ids[name], name, mu, curves.get(name)))

    w('Equation 1\n  Name = "magnetostatics"\n  Active Solvers(2) = 1 2\nEnd\n')
    w('Solver 1\n  Equation = MGDynamics\n  Variable = AV\n'
      '  Procedure = "MagnetoDynamics" "WhitneyAVSolver"\n'
      "  Fix Input Current Density = Logical False\n"
      "  Edge Basis = Logical True\n  Apply Conforming BCs = Logical True\n  Optimize Bandwidth = False\n"
      + ("  Newton-Raphson Iteration = Logical True\n"
         f"  Nonlinear System Max Iterations = {int(analysis['nonlinear_max_iterations'])}\n"
         f"  Nonlinear System Convergence Tolerance = {analysis['nonlinear_tolerance']:g}\n" if nonlinear else "") +
      "  Linear System Solver = Iterative\n  Linear System Iterative Method = BiCGStabl\n"
      "  BiCGStabl Polynomial Degree = 4\n  Linear System Preconditioning = ILU0\n"
      f"  Linear System Max Iterations = {int(analysis['linear_max_iterations'])}\n"
      f"  Linear System Convergence Tolerance = {analysis['linear_tolerance']:g}\n"
      "  Linear System Residual Output = 100\n  Linear System Abort Not Converged = True\n"
      "  Steady State Convergence Tolerance = 1e-6\nEnd\n")
    w('Solver 2\n  Equation = MGDynamicsCalc\n  Procedure = "MagnetoDynamics" "MagnetoDynamicsCalcFields"\n'
      '  Potential Variable = String "AV"\n  Calculate Magnetic Flux Density = Logical True\n'
      "  Calculate Magnetic Vector Potential = Logical True\n  Calculate Nodal Forces = Logical True\n"
      "  Discontinuous Bodies = Logical True\n"
      "  Linear System Symmetric = True\n  Linear System Solver = Iterative\n"
      "  Linear System Iterative Method = CG\n  Linear System Preconditioning = None\n"
      "  Linear System Max Iterations = 5000\n  Linear System Convergence Tolerance = 1e-8\n"
      "  Linear System Residual Output = 0\n  Steady State Convergence Tolerance = 0\nEnd\n")
    w('Solver 3\n  Exec Solver = After All\n  Equation = SaveScalars\n'
      '  Procedure = "SaveData" "SaveScalars"\n  Filename = scalars.dat\n'
      "  Save Component Results = Logical True\nEnd\n")
    w('Solver 4\n  Exec Solver = After All\n  Equation = ResultOutput\n'
      '  Procedure = "ResultOutputSolve" "ResultOutputSolver"\n  Output File Name = fields\n'
      "  Vtu Format = Logical True\n  Ascii Output = Logical True\n  Save Geometry Ids = Logical True\n"
      "  Save Bulk Only = Logical True\n  Discontinuous Bodies = Logical True\nEnd\n")
    w('Component 1\n  Name = "rotor"\n'
      f"  Master Bodies({len(rotor_solids)}) = {' '.join(str(i) for i in rotor_solids)}\n"
      "  Calculate Magnetic Torque = Logical True\n  Torque Axis(3) = Real 0 0 1\n"
      "  Torque Origin(3) = Real 0 0 0\nEnd\n")

    def bc(number, name, lines):
        w(f'Boundary Condition {number}\n  Name = "{name}"\n  Target Boundaries(1) = {boundaries[name]}\n'
          + "".join(f"  {line}\n" for line in lines) + "End\n")

    bc(1, "outer_rotor", ["AV {e} = Real 0"])
    bc(2, "outer_stator", ["AV {e} = Real 0"])
    number = 3
    for side in ("rotor", "stator"):  # periodic cut planes: the meshes match, so the unknowns are identified
        bc(number, f"periodic_b_{side}", [])
        bc(number + 1, f"periodic_a_{side}", [f"Conforming BC = Integer {number}",
                                             "Radial Projector = Logical True", "Level Projector = Logical True"])
        number += 2

    with open(os.path.join(posdir, "case.sif"), "w") as f:
        f.write("\n".join(out))
    return {"coil_bodies": coil_bodies, "core_bodies": core_bodies, "rotor_loss_bodies": rotor_loss_bodies,
            "coil_area_m2": coil_area,
            "current_density": current_density, "ampere_turns": ampere_turns, "nonlinear": nonlinear}



@register("solver", "elmer3d")
class ElmerSector3D(FieldSolver):
    """
    FieldSolver for a "tfm.sector3d" mesh. `settings` are the analysis settings (ANALYSIS_DEFAULTS):
    materials, coil turns (used for the reported flux linkage), tolerances, whether to keep the
    field files and whether to save the core fields for the loss model.
    """

    def __init__(self, settings=None, core_field=False):
        self.settings = dict(ANALYSIS_DEFAULTS, **(settings or {}))
        self.core_field = core_field

    def solve(self, mesh, excitation, workdir):
        settings = self.settings
        began = time.time()
        meta = mesh.meta
        convert_mesh(workdir, meta)
        coil = write_case(settings, meta, workdir, float(excitation.ampere_turns[0]))
        shutil.rmtree(os.path.join(workdir, "results"), ignore_errors=True)
        os.makedirs(os.path.join(workdir, "results"))
        run([os.path.join(ELMER_HOME, "bin", "ElmerSolver"), "case.sif"], workdir, os.path.join(workdir, "solve.log"))

        log = read_text(os.path.join(workdir, "solve.log"))
        iterations = re.findall(r"BiCGStabl:\s+(\d+)\s+(\S+)", log)
        newton = re.findall(r"ComputeChange: NS \(ITER=(\d+)\) \(NRM,RELC\): \(\s*\S+\s+(\S+)\s*\) :: mgdynamics\s*$",
                            log, flags=re.M)
        if coil["nonlinear"]:
            if not newton or float(newton[-1][1]) > settings["nonlinear_tolerance"]:
                change = newton[-1][1] if newton else "n/a"
                raise StageError(f"The nonlinear iteration did not converge (last relative change {change}), "
                                 f"see {os.path.join(workdir, 'solve.log')}")
        scalars = read_scalars(workdir)

        def scalar(key):
            return next((v for n, v in scalars.items() if key in n.lower()), float("nan"))

        periodicity = meta["sector"]["periodicity"]
        data = read_fields(workdir)
        widths = meta.get("rotor_eddy_width_mm")
        field_file = None
        if self.core_field and data:
            field_file = save_core_field(workdir, data, coil, periodicity, excitation.rotor_angle_deg,
                                         None if widths is None else np.asarray(widths) / 1000.0)
        sample = FieldSample(
            rotor_angle_deg=excitation.rotor_angle_deg,
            torque_Nm=scalar("magnetic torque") * periodicity,
            flux_linkage_Wb=(coil_flux(data, coil, periodicity, settings["coil_turns"]),),
            field_file=field_file,
            extras={
                "field_energy_J": scalar("electromagnetic field energy") * periodicity,
                "core_volume_mm3": sum(r["volume_mm3"] for r in meta["regions"].values()
                                       if r["side"] == "stator" and r["kind"] == "core") * periodicity,
                "solver_iterations": max(int(i[0]) for i in iterations) if iterations else -1,
                "nonlinear_iterations": int(newton[-1][0]) if (coil["nonlinear"] and newton) else 0,
                "elements": meta["mesh"]["volume_elements"],
                "periodicity": periodicity,
                "seconds": round(time.time() - began, 1),
            })
        if not settings["keep_fields"]:
            for f in os.listdir(os.path.join(workdir, "results")):
                if f.endswith(".vtu"):
                    os.remove(os.path.join(workdir, "results", f))
            shutil.rmtree(os.path.join(workdir, "mesh"), ignore_errors=True)
        return sample


__all__ = ["ANALYSIS_DEFAULTS", "ELMER_HOME", "ElmerSector3D", "convert_mesh", "write_case", "MU0",
           "ROTOR_LOSS_KINDS", "material_block", "material_curve", "material_of", "read_names"]
