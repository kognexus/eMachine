# B06: Radial-flux interior PM machine: geometry and solution

Status: backlog
New name (docs/naming.md, from T43): rfm/pmsm with rotor layout `interior`.
Depends on: T40, T41

## Why

The machine `rfm/ipm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

V-shaped buried magnets with bridges; 2D section on the T41 builder and solver; MTPA current angle (analysis/mtpa.py).

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
