# B09: Radial-flux switched reluctance machine: geometry, solution and excitation

Status: backlog
Depends on: T40, T41

## Why

The machine `rfm/srm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

Salient stator and rotor poles; phase-by-phase switched current (excitation plan with current pulses instead of a sinusoidal drive); torque from flux-linkage curves.

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
