# B12: Transverse-flux reluctance machine

Status: backlog
Depends on: T40, T41

## Why

The machine `tfm/srm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

TFM stators of machines/tfm with a rotor of iron teeth (no magnets) in the 3D sector; switched excitation as B09.

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
