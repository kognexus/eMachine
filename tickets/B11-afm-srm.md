# B11: Axial-flux switched reluctance machine

Status: backlog
Depends on: T40, T41

## Why

The machine `afm/srm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

As B09 on the axial geometry of B10.

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
