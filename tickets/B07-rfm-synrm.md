# B07: Radial-flux synchronous reluctance machine: geometry and solution

Status: backlog
Depends on: T40, T41

## Why

The machine `rfm/synrm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

Flux barriers (number, insulation ratio, ribs); 2D section; MTPA; d-q inductances from the field.

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
