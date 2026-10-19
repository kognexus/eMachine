# T35: Field solvers behind `FieldSolver`

Status: done
Depends on: T34

## Why

`tfm_pipeline.py` mixes mesh conversion, Elmer case writing, solving and result reading for
one geometry kind; the analytic stand-in lives in `evaluate.py`.

## Work

1. `solvers/elmer/`: `case.py` (case file), `run.py` (ElmerGrid, ElmerSolver), `results.py`
   (torque, flux linkage, core fields), `sector3d.py` (today's solver as `FieldSolver` "elmer3d").
2. `solvers/analytic.py`: the stand-in as `FieldSolver` "analytic".
3. Solver output is a `FieldSample` with flux linkage per phase.
4. `tfm_pipeline.py` re-exports.

## Acceptance criteria

- [x] Solvers registered and created by name
- [x] Same torque and flux as before (slow test)
- [x] No machine-specific code in `solvers/`

## Test cases

| ID | Test | Expected |
|---|---|---|
| T35-1 | Case file of a reference mesh | Identical to the old case file |
| T35-2 (slow) | One rotor position, reference design | Torque and flux equal to characterization data |
| T35-3 | Analytic solver | Same stand-in results |

## Result

2026-10-16.

- `emachine/solvers/elmer/`: `materials.py` (B-H curves, material of a region), `results.py`
  (body names, .vtu fields, scalars), `fields.py` (saved core and rotor fields, coil flux),
  `sector3d.py` (case writer, mesh conversion, `ElmerSector3D`, registered "elmer3d").
- `emachine/solvers/analytic.py`: `AnalyticStandIn`, registered "analytic"; the old
  `analytic_stand_in` now runs it position by position.
- `emachine/machines/tfm/geometry/builder.py`: `SectorBuilder`, registered "tfm.sector3d"
  (runs the sector mesher as `python -m emachine.machines.tfm.geometry.sector`).
- `emachine/io/process.py`: running external programs (shared by builder and solver).
- The solver no longer reads TFM parameters: the mesher records the coil area and the rotor
  eddy-current widths in the region description (older meshes fall back to the parameters).
  `Excitation` carries the coil ampere-turns, the electrical angle and the drive amplitude.
- `tfm_pipeline.py` keeps its command and names; `solve_position` composes builder and solver.
- Tests: `tests/unit/solvers/` (registration, analytic solver against the formula, case file
  identical to the one written by the code before T35, recorded in `golden/`); the Elmer
  characterization case reproduced; the whole slow suite passes (292 tests, 22 minutes).
