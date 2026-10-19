# T36: Pipeline: stages, sweeps, load levels, run store

Status: done
Depends on: T35

## Why

`evaluate.py`, `em.py` and `effmap.py` hold the orchestration (staged positions, load levels,
caching) next to the physics.

## Work

1. `pipeline/sweep.py`: rotor-angle sweeps from a machine's `ExcitationPlan` (one phase with
   shifts, or all phases with d-q currents), in parallel.
2. `pipeline/evaluate.py`: design -> `Evaluation` through the interfaces; staged positions.
3. `pipeline/levels.py`: load levels and their cache; `pipeline/store.py`: run folders, signatures.
4. Machine, solver and models are passed in (dependency injection); tests use fakes.

## Acceptance criteria

- [x] Pipeline works with fake machine and solver (unit tests)
- [x] Same evaluations as before (characterization)
- [x] Old caches recognised or recomputed by signature

## Test cases

| ID | Test | Expected |
|---|---|---|
| T36-1 | Sweep with a fake solver, one-phase and all-phase plans | Correct angles, currents, phase sums |
| T36-2 | Evaluation with fakes | Objectives and constraints from the fake results |
| T36-3 | Stand-in evaluation of the reference design | Equal to characterization data |

## Result

2026-10-16.

- `emachine/pipeline/sweep.py`: sweep angles and drive currents, parallel `run_positions`,
  `sweep` (any registered geometry builder and field solver), `field_analysis(geometry, solver)`,
  `analytic_stand_in`.
- `emachine/pipeline/design_space.py`: the machine named by the spec and its variables, clip,
  vectors, dimensions, geometry and checks.
- `emachine/pipeline/evaluate.py`: staged positions, load levels, field and record caches,
  `assemble` through the Machine interface (excitation plan decides between the shifted phase sum
  and an all-phase torque; thermal network and winding of the machine; `physics.winding.turns_for`),
  `BatchEvaluator`. Load levels are skipped for machines without a current-density variable. Cache
  keys leave out `family`/`topology` = `tfm`/`pmsm`, so the caches of earlier runs stay valid.
- `emachine/physics/interpolation.py` (pchip); `core.types.Winding` gains the coil cross-section.
- `tfm/em.py` and `tfm/evaluate.py` are adapters.
- Tests: `tests/unit/pipeline/` with a fake machine (all phases solved together, no TFM keys), a
  fake geometry builder and a fake solver: sweep angles, currents, order, failures; evaluation with
  checks, objectives, losses and winding. Stand-in evaluations equal the characterization data;
  the whole slow suite passes (295 tests).
