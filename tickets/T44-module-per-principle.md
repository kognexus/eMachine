# T44: One module per principle, rotor and stator layouts as modules

Status: done
Depends on: T43

## Why

The user (2026-10-16) asked why `machines/tfm/srm.py` is a file of its own while the radial flux
machines are all in `machines/rfm/topologies.py`. The two flux paths follow different layouts.
The naming standard (`docs/naming.md`) fixes one: a module per principle, a module per rotor or
stator layout. This is done before B06 to B12 make the classes grow.

## Scope

```
emachine/machines/<flux_path>/
  __init__.py
  base.py              shared dimensions, checks and thermal network of the flux path
  pmsm.py, synrm.py, srm.py (, vernier.py)      one class per principle
  rotors/<layout>.py   surface, interior, spoke, halbach, flux_barrier, salient, ...
  stators/<layout>.py  RFM, AFM: slotted (in base.py until a second stator layout exists);
                       TFM: geometry/stators and geometry/rotors stay where they are (see Result)
  geometry/, cad/      unchanged (TFM)
```

- `machines/tfm/machine.py` becomes `machines/tfm/pmsm.py`, `machines/rfm/topologies.py` and
  `machines/afm/topologies.py` are split per principle. Class names `<FluxPath><Principle>`.
- `emachine/plugins.py` lists the new modules; registry keys do not change (T43).
- No behaviour changes.

## Acceptance criteria

- [x] Every flux path has the same layout; each principle module holds one machine class.
- [x] `python -m emachine list` unchanged.
- [x] Characterization tests and the full slow suite pass unchanged.
- [x] `docs/architecture.md` and `docs/extending.md` show the layout and the steps to add a principle
      or a rotor layout.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T44-1 | Layout test: for every flux path, the principle modules register `<flux_path>/<principle>` | one class per module, names as the standard |
| T44-2 | Import rule test | passes (machines import no solvers, no other flux path) |
| T44-3 | Characterization suite | identical numbers |

## Result

2026-10-16 (done together with T43, which touched the same classes). `machines/rfm/` and
`machines/afm/`: `base.py` (flux path), `pmsm.py`, `synrm.py`, `srm.py`, `rotors/<layout>.py`
(`RotorLayout`: variables, checks, geometry; the surface rotor holds the T41 geometry);
`machines/tfm/machine.py` became `pmsm.py` (`TransverseFluxPMSM`), `srm.py` holds
`TransverseFluxSRM`. The switched reluctance principle is a mixin in `machines/base.py`, shared by
`rfm/srm` and `afm/srm` without one flux path importing the other. The slot star moved to
`machines/winding_layout.py` (all slotted machines).

Changed from the scope: the TFM keeps its stator and rotor layouts in `geometry/stators/` and
`geometry/rotors/` (they are the Gmsh builders); the two rotor modules were renamed to the standard
names (`spoke.py`, `axial_ring.py`), and their `code` stays the short name of the parameter files.

Tests (`tests/unit/machines/test_layout.py`, 4): one class per principle module, named
`<FluxPath><Principle>`, every registered machine found; every rotor layout in
`<flux_path>/rotors/<layout>.py`; the TFM rotor geometry modules carry the standard names; no flux
path imports another. Import rule and characterization tests pass.

Full slow suite after T43 to T47: 366 tests pass (1 skipped) in 1374 s.
