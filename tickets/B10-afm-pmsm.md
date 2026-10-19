# B10: Axial-flux PM machine: geometry and solution

Status: backlog
Depends on: T40, T41

## Why

The machine `afm/pmsm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

Single or double sided; quasi-3D (several 2D slices on radii) or a 3D sector on the Elmer 3D solver.

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
