# B13: Radial-flux PMSM: ParaView export, CAD, published reference, lamination data

Status: backlog
Depends on: T41

## Why

T41 made `rfm/pmsm` optimizable and mappable, checked against theory only. Still missing:

- ~~`python -m emachine export` stops with "not supported yet" for radial flux machines~~ (T42).
- No CAD output (Onshape or STEP) of the cross-section.
- No comparison with a published or measured radial flux machine.
- The stator core material defaults to SMC (SOMALOY 500); a lamination grade (for example
  M270-35A loss coefficients) belongs in the material defaults of radial machines.

## Acceptance criteria

- [x] ParaView export of the 2D section (fields over the rotor positions, extruded to the stack)
      and the efficiency map view: done in [T42](T42-rfm-paraview-export.md).
- [ ] STEP of the cross-section, extruded.
- [ ] Back-EMF and torque within 10 % of a published 12-slot 10-pole (or similar) machine.
- [ ] Lamination steel loss coefficients with source, used by default for `rfm` and `afm`.
