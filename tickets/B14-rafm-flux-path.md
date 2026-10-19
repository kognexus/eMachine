# B14: Radial-axial flux machine (RAFM): flux path, skeleton, geometry

Status: done (T53 to T56; the 3D model is B18)
Depends on: T43, T44, T45

## Why

The naming standard (`docs/naming.md`, 2026-10-16) adds the flux path `rafm`: the flux of one rotor
crosses radial and axial gap faces (for example a cup rotor facing the bore and the end faces of
the stator), so the flux path is three-dimensional. It is a column of the machine matrix (T45)
with no machine yet.

## Scope

1. Skeleton `rafm/pmsm` as T40 did for the other machines: options (radial and axial gap, which
   faces carry magnets), variables, dimensions, checks, winding (span from T46), thermal network;
   `geometry` raises `NotSolvableYet`.
2. Geometry and solution: a 3D sector on the Elmer 3D solver (as the TFM), since no 2D section
   holds the flux path.

## Acceptance criteria

- [ ] Skeleton registered; matrix cell `rafm/pmsm` `specified`.
- [ ] `geometry` returns a request for a registered geometry builder; torque and flux of every
      phase from the solver.
- [ ] The radial part alone (axial faces without magnets) agrees with `rfm/pmsm` of the same
      dimensions within 5 % (2D against 3D, end effects aside).
- [ ] Validated against a published machine.
