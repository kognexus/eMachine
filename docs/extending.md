# Extending emachine

Everything that varies between machines, solvers and optimizers is a plugin: a class that
implements one interface of `emachine/core/interfaces.py`, registers itself under a name, and is
listed in `emachine/plugins.py`. The pipeline, the analyses and the commands find it by name, so
nothing else changes. Write the tests first (`tests/unit/<package>/`), then the class.

Names of flux paths, principles, rotor layouts and windings: `docs/naming.md`.

## A new rotor layout of an existing machine

One module in `emachine/machines/<flux_path>/rotors/<layout>.py` with a `RotorLayout`, added to the
`ROTORS` of the principle class:

```python
# emachine/machines/rfm/rotors/inset.py
from emachine.core.types import Variable
from ...base import RotorLayout

class Inset(RotorLayout):
    name = "inset"
    ticket = "B13"            # the ticket that builds its geometry
    def variables(self, spec):
        return [Variable("magnet_thickness_mm", 1.0, 8.0), Variable("inset_ratio", 0.0, 1.0)]
    # checks(spec, values, d); geometry(machine, spec, values, fidelity) when it can be solved

# emachine/machines/rfm/pmsm.py
    ROTORS = (Surface, Interior, Inset)
```

`"machine": {"flux_path": "rfm", "principle": "pmsm", "rotor": "inset"}` then loads, and
`emachine list` shows the layout with its ticket.

## A new machine (flux path and principle)

1. Write a class implementing `Machine` in `emachine/machines/<flux_path>/<principle>.py`. For a
   slotted radial or axial machine, start from the flux path's base class (`rfm/base.py`
   `RadialFlux`, `afm/base.py` `AxialFlux`, both `SlottedMachine`s), which already provides the
   stator variables, dimensions, checks, winding, thermal network and an all-phase excitation;
   give it `principle`, its `ROTORS`, and `principle_variables` / `principle_checks` /
   `extra_options` for what all its layouts share:

   ```python
   from emachine.core.registry import register
   from .base import RadialFlux
   from .rotors.surface import Surface

   @register("machine", "rfm/vernier")
   class RadialFluxVernier(RadialFlux):
       principle = "vernier"
       ROTORS = (Surface,)
   ```

2. `derive(spec, values)` must contain `pole_pairs`, `electrical_frequency_Hz`,
   `ampere_turns_peak` and `ampere_turns_rms`; `thermal_network` must have the nodes `winding`,
   `core` and `rotor`. The pipeline relies on these.
3. `excitation(spec, values)` says how the phases are solved: `single_phase_shifted` (one phase,
   the others shifted; magnetically independent phases, as the TFM) or `all_phases`.
4. `geometry(spec, values, fidelity)` returns a `GeometryRequest(kind, parameters)` for a
   registered geometry builder. Until there is one, raise `NotSolvableYet` with the ticket: the
   machine can then already be specified, checked and listed.
5. List the module in `emachine/plugins.py`. `emachine list` shows it, and a spec with
   `"machine": {"flux_path": "rfm", "principle": "vernier"}` loads with its options.

## A new stator or rotor type of the TFM

One class in its own module, plus one line in the table:

- stator: `emachine/machines/tfm/geometry/stators/<name>.py`, a `StatorType` with `code`,
  `layout(frame, sp)` (coil window, trimming) and `build(frame, sp)` returning the core solids;
  add it to `STATORS` in `stators/__init__.py`. The `StatorFrame` gives the dimensions, the pole
  angles and the shape helpers (`radial`, `trim`, `prism_axial_height`, `block`, ...).
- rotor: `emachine/machines/tfm/geometry/rotors/<name>.py`, a `RotorType` with `magnets`,
  `seed`, `core_name` (and `row_extras` for further solids, or `custom_build` for a different
  ring); add it to `ROTORS` in `rotors/__init__.py`.
- Then the standard name and the geometry code in `machines/tfm/options.py` (`STATOR_CODES`,
  `ROTOR_CODES`, `ROTORS`; module names follow the standard name, `code` is the short name of the
  geometry parameter files), the variables (`design.py`), the checks (`checks.py`) and, for CAD,
  the FeatureScript in `cad/featurescript/`.

## A new geometry builder or field solver

- `GeometryBuilder.build(request, rotor_angle_deg, workdir)` returns a `Mesh` (file, regions,
  description). Register it as `("geometry", "<kind>")`; machines name it in their
  `GeometryRequest`.
- `FieldSolver.solve(mesh, excitation, workdir)` returns a `FieldSample` (torque, flux linkage per
  solved coil, saved field file). Register it as `("solver", "<name>")`. Solvers read what they
  need from the mesh description (regions with kind and side, coil area, rotor eddy widths), never
  the parameters of a particular machine.
- The field file (`core_field.npz`, read by `physics/losses.py`) holds the stator core elements and
  the rotor parts in the rotor frame, with `periodicity` (copies of the model in the whole machine),
  `electrical_period_deg` and `phases` (how many phases' loss the field holds: 1 for one TFM phase,
  all phases for a whole cross-section). The losses are returned per phase.

## ParaView export of a new geometry kind

`emachine export` picks the reader by the geometry kind (`EXPORTS` in
`emachine/cli/export.py`): `analysis/fieldexport.py` for `tfm.sector3d`,
`analysis/section_export.py` for `rfm.section2d`. A new kind needs an `export(...)` that returns the
same dictionary (summary.json) and writes the same files: `machine.pvd`, `air.pvd`, `airgap.pvd`,
`core_loss.vtu`, `full_ring.vtu`, with the cell array `material` (1 air, 2 copper, 3 magnet,
4 stator core, 5 rotor iron, 6 rotor housing). Then the view script and `open_in_paraview.py` work
unchanged. Set `ring_has_all_phases` when `full_ring.vtu` already holds every phase, and
`model` = "section2d" for a 2D solution shown from the top. A 2D section is extruded to wedges
(base triangle counter-clockwise seen from the top: VTK gives the other order a negative volume).

## A new optimizer

`Optimizer.run(problem, evaluate, budget, state_file=None, **options)`: `problem.variables` are
`Variable`s, `evaluate(list of vectors)` returns `(objectives, violation)` per vector (objectives
minimised, violation 0 = feasible), `budget` has `population`, `generations`, `seed`. Return a
state with `population` (dicts with `x`, `f`, `violation`), `generation`, `evaluations`,
`history`. Use `emachine/optimization/pareto.py` for domination and fronts. Register it as
`("optimizer", "<name>")`; `"optimizer": {"algorithm": "<name>"}` in a spec selects it.

## Dependency rule

`tests/unit/core/test_import_rule.py` checks which package may import which (table in
`docs/architecture.md`): machines, solvers and optimizers never import each other; they meet in
the pipeline through the interfaces.
