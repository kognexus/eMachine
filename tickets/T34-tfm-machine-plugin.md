# T34: TFM as a machine plugin in `emachine/machines/tfm`

Status: done
Depends on: T33

## Why

Spec section, variables, derived dimensions, checks, parameter files, mesher and Onshape
support of the TFM are spread over `spec.py`, `design.py`, `feasibility.py`,
`tfm_gmsh_sector.py` and `onshape.py`.

## Work

1. `machines/base.py`: shared helpers for `Machine` implementations.
2. `machines/tfm/`: `machine.py` (`tfm/pmsm`), `options.py` (spec section), `variables.py`,
   `derive.py`, `checks.py`, `stators/` (u, ui, cp, tr, c, e, z: one module each), `rotors/`
   (surface, halbach, flux concentrating, axial), `geometry.py` (Gmsh sector builder using them),
   `thermal.py` (TFM network), `cad/` (Onshape FeatureScript sources, parameter sheet, UI32 build).
3. Registered as `machine tfm/pmsm` and `geometry tfm.sector3d`.
4. `tfm_gmsh_sector.py`, `tfm/design.py`, `tfm/feasibility.py`, `tfm/onshape.py` re-export.

## Acceptance criteria

- [x] Every stator and rotor type in its own module
- [x] Characterization tests unchanged (slow mesh volumes too)
- [x] Adding a stator type touches only its module and a registration line

## Test cases

| ID | Test | Expected |
|---|---|---|
| T34-1 | Machine interface of tfm/pmsm | variables, derive, checks, geometry as before |
| T34-2 | Stator and rotor registries | All types listed; unknown type error |
| T34-3 (slow) | Mesh of every analysable stator type | Region volumes equal to the characterization data |

## Result

2026-10-16.

- Spec: the section `machine` has the common keys plus `family` and `topology` (default
  `tfm`/`pmsm`, so old files load unchanged); the loader asks the registered machine for its
  options and validation (`Machine.options`, `Machine.validate`). Built-in plugins load at the
  first registry lookup (`emachine/plugins.py`, hook set in `emachine/__init__.py`).
- `emachine/machines/tfm/`: `machine.py` (`TransverseFluxPM`, registered `tfm/pmsm`),
  `options.py`, `design.py` (variables, derived dimensions, parameter files), `checks.py`
  (`core.types.Check`), `thermal.py`, `geometry/` and `cad/`.
- `geometry/`: `stators/` (frame.py with `StatorFrame` and `StatorType`; u_core.py with U and
  UI, claw_pole.py, toothed_ring.py with the valley profile, c_core.py, e_core.py, z_core.py;
  `STATORS` table), `rotors/` (frame.py, surface.py, halbach.py, flux_concentrating.py, axial.py,
  magnets.py; `ROTORS` table), `shapes.py`, `parameters.py`, `sector.py` (sector mesher and its
  command line), `preview.py`. A new stator or rotor type is one class in its own module plus one
  entry in the table (unit test adds a type that way).
- `cad/`: the FeatureScript files (`featurescript/`, same names), `ui32_build.py`, `sheet.py`.
- Adapters: `tfm/design.py`, `tfm/feasibility.py` (dictionaries as before), `tfm/onshape.py`,
  `tfm/spec.py` (with the full TFM `DEFAULTS`), `tfm_gmsh_sector.py`, `tfm_ui32_build.py`.
- Tests: unit tests of the spec sections, the machine and the geometry types (written first);
  characterization data unchanged (the spec case leaves out the two new keys `family` and
  `topology`), mesh volumes of all ten stator and five rotor builds and the Elmer solution
  identical; slow tests T22, T24, T26, T27, T30 pass; 289 fast tests pass.
