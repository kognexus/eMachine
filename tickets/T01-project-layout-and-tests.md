# T01: Project layout and test harness

Status: done
Depends on: none

## Why

The mesher and the pipeline are two standalone scripts. The optimization system needs
importable modules and a repeatable way to run tests.

## Scope

- Create the `tfm/` package. Existing scripts stay where they are and keep working.
- `tfm/paths.py`: project root, Elmer location, Python interpreter.
- `tests/` with a shared helper for slow tests (`TFM_SLOW=1`).
- A regression test that pins the validated geometry of the default machine.

## Acceptance criteria

- [x] `import tfm` works from the project root.
- [x] `.venv/bin/python -m unittest discover -s tests -v` runs and exits 0.
- [x] Slow tests are skipped by default and run with `TFM_SLOW=1`.
- [x] The two existing scripts still run unchanged.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T01-1 | Run test discovery without `TFM_SLOW` | Exit code 0, slow tests reported as skipped |
| T01-2 | `tfm.paths` reports the Elmer solver and the mesher script | Both files exist |
| T01-3 (slow) | Build the default machine geometry without meshing | Stator core 8493.9 mm3, coil 6616.2 mm3, back iron 21135.1 mm3 per sector, each within 0.1 % |

## Result

Completed 2026-10-13.

- Created the `tfm/` package with `tfm/paths.py`, and `tests/` with `tests/helpers.py`.
- T01-1: `python -m unittest discover -s tests` exits 0; the slow test is reported as skipped.
- T01-2: passed. Elmer solver, ElmerGrid, mesher and pipeline scripts are found.
- T01-3: passed with `TFM_SLOW=1`. Sector volumes match the validated values within 0.1 %.
  The core volume is now split over two regions (core and core inside the coil shell); the test sums them.
- Both existing scripts still respond to `--help` and run unchanged.
