# T39: Command line, compatibility, tests layout, README

Status: done
Depends on: T37, T38

## Why

Many top-level scripts; tests named by ticket only.

## Work

1. `python -m emachine <command>`: optimize, map, export, validate, onshape, mesh, list.
2. Old scripts as thin wrappers; `tfm/` package removed or reduced to re-exports.
3. Tests in `tests/unit`, `tests/integration`, `tests/characterization`; ticket IDs kept in names.
4. README rewritten for the new structure; `docs/` for architecture and how to add a machine.

## Acceptance criteria

- [x] Every old command works through its wrapper
- [x] Old spec files and run folders read
- [x] README describes the new layout

## Test cases

| ID | Test | Expected |
|---|---|---|
| T39-1 | CLI commands | Help and dry runs work |
| T39-2 | Old wrappers | Same outputs as the new commands |
| T39-3 | Old spec and run folder | Loaded and converted |

## Result

- `python -m emachine <command>` (`emachine/cli/`): optimize, map, export, validate, compare,
  onshape, mesh, check-mesh, solve, ui32, list. The root scripts (`tfm_optimize.py`, `tfm_map.py`,
  `tfm_paraview.py`, `tfm_pipeline.py`, ...) are thin wrappers; copies of the old scripts in
  `archive/scripts_before_t39/`.
- Reports and summaries name the machine through `cli/describe.py` (family, topology, options), so
  the commands work for every solvable machine, not only the TFM.
- Tests: `tests/unit/<package>/`, `tests/tickets/` (the old ticket tests), `tests/characterization/`.
- T39-1 to T39-3 pass: the old wrapper and the new command give the same table (dry run); every
  spec file written before the refactor loads as `tfm/pmsm`.
- Full slow suite: 308 of 309 passed; the one failure was T39-3 picking up the new radial flux
  spec, now excluded (specs older than the refactor only).
