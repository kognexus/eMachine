"""
Rotor-angle sweeps: a machine's geometry is meshed and solved at N rotor positions over half an
electrical period, in parallel.

Single-phase plans (TFM): one phase is solved, starting at the aligned position (a rotor north
pole facing a stator core). The coil carries i = -I_peak * sin(electrical angle), which is in phase
with the induced voltage and produces positive torque. The solution is in ampere-turns: one turn
carrying the ampere-turns.
"""

import concurrent.futures
import math
import os
import shutil
import time

import numpy as np

from emachine.core import registry
from emachine.core.types import Excitation, GeometryRequest
from emachine.physics.winding import current_shape, electrical_angles


#: field solver used for a geometry kind when none is named
DEFAULT_SOLVER = {"tfm.sector3d": "elmer3d", "rfm.section2d": "elmer2d", "rafm.quasi3d": "elmer_quasi3d"}


class AnalysisError(RuntimeError):
    """The field analysis of a design failed. The message says where the logs are."""


def sweep_angles(pole_pairs, n, shift=0.0):
    """Mechanical rotor angles in degrees: n positions over half an electrical period."""
    return (180.0 / pole_pairs) * (np.arange(n) + shift) / n


def drive_current(ampere_turns_peak, n, shift=0.0):
    """Ampere-turns at each position for sinusoidal drive."""
    return ampere_turns_peak * current_shape(n, shift)


def run_positions(task, angles, rundir, jobs=4, currents=None, report=None):
    """
    Runs task(angle, posdir, current) for every angle in parallel. Returns (results in the order of
    the angles, failures as [(angle, message)]). `report(angle, result_or_None, error_or_None)` is
    called as positions finish.
    """
    os.makedirs(rundir, exist_ok=True)
    rows, failed = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        jobs_map = {}
        for k, angle in enumerate(angles):
            current = None if currents is None else float(currents[k])
            job = pool.submit(task, float(angle), os.path.join(rundir, f"pos_{k:03d}"), current)
            jobs_map[job] = (k, angle)
        for job in concurrent.futures.as_completed(jobs_map):
            k, angle = jobs_map[job]
            try:
                rows[k] = job.result()
                if report:
                    report(angle, rows[k], None)
            except Exception as error:  # keep the other positions running
                failed.append((angle, str(error)))
                if report:
                    report(angle, None, error)
    return [rows[k] for k in sorted(rows)], failed


def solve_position(parameters, analysis, angle, posdir, current=None, core_field=False,
                   geometry="tfm.sector3d", solver="elmer3d"):
    """
    Geometry and field solution at one rotor angle. Returns a result row (dict): rotor angle, coil
    current, torque, field energy, flux linkage, saved field file, core volume, solver iterations,
    elements, seconds, periodicity, mesh warnings. `current` (per turn) overrides
    analysis["coil_current_A"]; with `core_field` the core and rotor fields are saved for the loss
    model.
    """
    os.makedirs(posdir, exist_ok=True)
    began = time.time()
    mesh = registry.create("geometry", geometry).build(GeometryRequest(geometry, parameters), angle, posdir)
    current = analysis["coil_current_A"] if current is None else current
    sample = registry.create("solver", solver, settings=analysis, core_field=core_field).solve(
        mesh, Excitation(rotor_angle_deg=angle, ampere_turns=(analysis["coil_turns"] * current,)), posdir)
    if not analysis["keep_fields"] and mesh.path and os.path.isfile(mesh.path):
        os.remove(mesh.path)
    extras = sample.extras
    return {
        "rotor_angle_deg": angle,
        "coil_current_A": current,
        "torque_Nm": sample.torque_Nm,
        "field_energy_J": extras["field_energy_J"],
        "flux_linkage_Wb": sample.flux_linkage_Wb[0],
        "core_field_file": sample.field_file,
        "core_volume_mm3": extras["core_volume_mm3"],
        "solver_iterations": extras["solver_iterations"],
        "nonlinear_iterations": extras["nonlinear_iterations"],
        "elements": extras["elements"],
        "seconds": round(time.time() - began, 1),
        "periodicity": extras["periodicity"],
        "warnings": mesh.meta.get("warnings", []),
    }


def run_rows(parameters, analysis, angles, rundir, jobs=4, currents=None, core_field=False, report=None,
             geometry="tfm.sector3d", solver="elmer3d"):
    """solve_position at every angle, in parallel. Returns (rows in the order of the angles, failures)."""
    def task(angle, posdir, current):
        return solve_position(parameters, analysis, angle, posdir, current, core_field, geometry, solver)
    return run_positions(task, angles, rundir, jobs, currents, report)


def field_analysis(geometry="tfm.sector3d", solver=None):
    """
    The field analysis of a geometry kind with a solver, as a function
    (parameters, positions, workdir, jobs, ampere_turns_peak=None, core_field=True, keep=False, shift=0.0)
    that returns the sweep of one phase as a dictionary (see `analyse`).
    """
    def analyse(parameters, positions, workdir, jobs=6, ampere_turns_peak=None, core_field=True, keep=False,
                shift=0.0):
        return sweep(parameters, positions, workdir, jobs, ampere_turns_peak, core_field, keep, shift,
                     geometry=geometry, solver=solver or DEFAULT_SOLVER.get(geometry, "elmer3d"))
    analyse.__name__ = "analyse"
    return analyse


def sweep(parameters, positions, workdir, jobs=6, ampere_turns_peak=None, core_field=True, keep=False, shift=0.0,
          geometry="tfm.sector3d", solver=None):
    """
    Runs the sweep of one phase (or of all phases: parameters["sweep"]["mode"] = "all_phases", then
    torque_Nm is the machine torque and flux_per_turn_Wb the flux of phase 0). Returns a dictionary with arrays of length `positions`:
    electrical_angle_rad, rotor_angle_deg, ampere_turns, torque_Nm (whole ring, one phase),
    flux_per_turn_Wb, and the list core_field_files. `shift` moves all positions by a fraction of
    a step: 0.5 gives the positions in between, so that two sweeps of n positions together are one
    sweep of 2 n positions.
    """
    from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS   # the settings of the field solvers
    solver = solver or DEFAULT_SOLVER.get(geometry, "elmer3d")
    began = time.time()
    analysis = dict(ANALYSIS_DEFAULTS)
    analysis.update(parameters.get("analysis", {}))
    analysis["coil_turns"] = 1
    analysis["keep_fields"] = bool(keep)
    peak = analysis["coil_current_A"] if ampere_turns_peak is None else ampere_turns_peak
    plan = parameters.get("sweep", {})
    p = int(plan.get("pole_pairs") or parameters["stator"]["pole_pairs"])
    all_phases = plan.get("mode") == "all_phases"
    phases = int(plan.get("phases", 1))
    angles = sweep_angles(p, positions, shift)
    currents = drive_current(peak, positions, shift)
    beta = math.radians(plan.get("current_angle_deg", 0.0))
    theta = electrical_angles(positions, shift)
    builder = registry.create("geometry", geometry)
    field_solver = registry.create("solver", solver, settings=analysis, core_field=core_field)
    request = GeometryRequest(geometry, parameters)

    def ampere_turns(angle):
        """Phase ampere-turns at a position: phase k lags phase 0 by k * 360 / m electrical degrees."""
        k_pos = int(np.argmin(np.abs(angles - angle)))
        if not all_phases:
            return (float(currents[k_pos]),)
        return tuple(-peak * math.sin(theta[k_pos] - 2 * math.pi * k / phases + beta) for k in range(phases))

    def task(angle, posdir, current):
        os.makedirs(posdir, exist_ok=True)
        mesh = builder.build(request, angle, posdir)
        sample = field_solver.solve(mesh, Excitation(rotor_angle_deg=angle, ampere_turns=ampere_turns(angle)), posdir)
        if not analysis["keep_fields"] and mesh.path and os.path.isfile(mesh.path):
            os.remove(mesh.path)
        return sample, mesh.meta.get("warnings", [])

    if os.path.isdir(workdir):
        shutil.rmtree(workdir)
    rows, failed = run_positions(task, angles, workdir, jobs, currents=currents)
    if failed:
        first = failed[0][1].splitlines()[0]
        raise AnalysisError(f"{len(failed)} of {positions} rotor positions failed in {workdir}: {first}")
    samples = [s for s, _ in rows]
    flux = [s.flux_linkage_Wb[0] for s in samples]
    if any(f is None for f in flux):
        raise AnalysisError(f"No coil flux could be read from the field files in {workdir}.")
    return {
        "electrical_angle_rad": electrical_angles(positions, shift),
        "rotor_angle_deg": angles,
        "ampere_turns": currents,
        "ampere_turns_peak": float(peak),
        "torque_Nm": np.array([s.torque_Nm for s in samples]),
        "flux_per_turn_Wb": np.array(flux),
        "flux_per_turn_phases_Wb": np.array([list(s.flux_linkage_Wb) for s in samples]),
        "core_field_files": [s.field_file for s in samples],
        "core_volume_mm3": samples[0].extras["core_volume_mm3"],
        "solver_iterations": [s.extras["solver_iterations"] for s in samples],
        "nonlinear_iterations": [s.extras["nonlinear_iterations"] for s in samples],
        "elements": samples[0].extras["elements"],
        "warnings": sorted({w for _, warnings in rows for w in warnings}),
        "seconds": time.time() - began,
    }


def analytic_stand_in(parameters, positions, rundir, jobs, shift=0.0):
    """
    Cheap replacement for the field analysis, for testing the workflow without Gmsh or Elmer: the
    solver "analytic" at every position of the sweep. It is a rough textbook estimate and must not
    be used for design decisions.
    """
    from emachine.solvers.analytic import AnalyticStandIn, parameters_mesh
    solver, mesh = registry.create("solver", "analytic"), parameters_mesh(parameters)
    ni = parameters["analysis"]["coil_current_A"]
    samples = [solver.solve(mesh, Excitation(rotor_angle_deg=0.0, electrical_angle_rad=math.pi * (k + shift) / positions,
                                             amplitude=ni))
               for k in range(positions)]
    return {
        "torque_Nm": np.array([s.torque_Nm for s in samples]),
        "flux_per_turn_Wb": np.array([s.flux_linkage_Wb[0] for s in samples]),
        "core_field_files": [],
        "elements": 0,
        "seconds": 0.0,
        "warnings": [AnalyticStandIn.WARNING],
    }
