# T32: Architecture, interfaces and characterization tests

Status: done
Depends on: T31

## Why

The code grew around one machine (TFM). The user (2026-10-16) wants a generic system for
PMSM, IPM, SynRM, PMaSynRM and SRM in transverse, radial and axial flux, with machines, optimizers
and the pipeline in separate extendable modules, clear interfaces, SOLID and TDD.

## Work

1. `docs/architecture.md` (agreed with the user).
2. Package `emachine/` with `core/`: `interfaces.py` (abstract base classes), `types.py`
   (dataclasses), `registry.py` (register and create plugins by kind and name).
3. Characterization tests (`tests/characterization/`): results of today's code for reference
   designs, written to JSON once and compared on every later run: spec parsing, derived dimensions,
   feasibility checks, parameter files, mesh region volumes (slow), analytic stand-in evaluation,
   loss coefficients from stored fields, torque metrics, map from synthetic levels, NSGA-II with a
   fixed seed.
4. `CHANGELOG.md` at the root with ticket progress.

## Acceptance criteria

- [x] Interfaces cannot be instantiated without their methods; dataclasses have the agreed fields
- [x] Registry: register, create, list, unknown name and double registration are errors
- [x] Characterization data captured from the code before any move; comparison passes
- [x] Dependency rule: `emachine/core` imports nothing else of `emachine`

## Test cases

| ID | Test | Expected |
|---|---|---|
| T32-1 | Abstract classes | TypeError without methods; subclass with methods works |
| T32-2 | Registry | create by name; unknown name and duplicates raise |
| T32-3 | Characterization data present and equal | All recorded values reproduced |
| T32-4 | Import rule of core | No import of other emachine packages |

## Result

2026-10-16.

- `docs/architecture.md`; `emachine/core/` with `registry.py` (kinds machine, geometry, solver,
  optimizer; register, get, create, names, load, snapshot and restore for tests), `types.py`
  (Variable, Check, Winding, OperatingPoint, phase_currents, ExcitationPlan, Excitation,
  GeometryRequest, Mesh, FieldSample, Sweep, ThermalNetwork, Losses, Temperatures, Evaluation,
  Objective, Problem) and `interfaces.py` (Machine, GeometryBuilder, FieldSolver, LossModel,
  ThermalModel, Optimizer).
- Characterization: `tests/characterization/cases.py` (spec parsing of every spec file; derived
  dimensions, checks, parameters, Onshape sheet, winding and thermal results of six designs;
  stand-in evaluations; loss coefficients from synthetic fields; torque metrics; efficiency map;
  NSGA-II with a fixed seed; slow: region volumes of ten stator and five rotor builds, one Elmer
  solution). Golden data captured from the code before any move (`golden/*.json`); all nine cases
  reproduce, the Elmer solution included (-2.3384 N m, 0.31730 mWb).
- `CHANGELOG.md`. Backup `archive/pre-refactor-2026-10-16.tar.gz`.
- Tests: `tests/unit/core/` (14 tests, written before the code), `tests/characterization/`. All
  fast tests pass; `EMACHINE_SLOW=1` is accepted next to `TFM_SLOW=1`.
