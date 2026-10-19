# T38: Analysis and I/O modules

Status: done
Depends on: T36

## Why

Map, field export, ParaView files and validation are generic but call TFM functions.

## Work

1. `analysis/effmap.py`, `analysis/fieldexport.py`, `analysis/validation.py` on the interfaces
   (current angle in the map, d-q ready).
2. `io/vtk.py`, `io/svg.py`, `io/paraview_files.py`, `io/paraview_views.py`, `io/report.py`.

## Acceptance criteria

- [x] Map and export of the user's machine unchanged
- [x] Validation cases reproduce T31 numbers (--losses-only)

## Test cases

| ID | Test | Expected |
|---|---|---|
| T38-1 | Map from synthetic levels | Equal to characterization |
| T38-2 | Validation cases, losses only | Equal to T31 results |
| T38-3 (slow) | ParaView views | Five pictures, no failure |

## Result

2026-10-16.

- `emachine/analysis/`: `effmap.py` (through the Machine interface: winding, thermal network,
  excitation plan decides the phase sum), `fieldexport.py` (Elmer sector post-processing; the
  phase layout only for TFM), `validation.py`, `mtpa.py` (T40).
- `emachine/io/`: `vtk.py`, `svg.py`, `paraview_files.py`, `paraview_views.py` (pvpython,
  self-contained; copied into every export).
- `emachine/pipeline/`: `solve_position` and `run_rows` (one row per rotor angle, used by the old
  pipeline command, the export and the validation), `picks.py`.
- Adapters: `tfm/effmap.py`, `fieldexport.py`, `vtkio.py`, `svgplot.py`, `paraviewfiles.py`,
  `picks.py`; wrappers `tfm_validate.py`, `tfm_paraview_views.py`.
- Tests: map of an all-phase fake machine (no phase sum) and of a three-phase TFM (phase sum);
  validation losses-only reproduces T31 (59.86 W rotor, 94.45 W total, 84.58 %); characterization
  map equal; the whole slow suite passes (301 tests), ParaView views rendered.
