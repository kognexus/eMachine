# B08: Radial-flux PM-assisted SynRM: geometry and solution

Status: backlog
New name (docs/naming.md, from T43): rfm/synrm with rotor layout `flux_barrier_pm`.
Depends on: T40, T41

## Why

The machine `rfm/pmasynrm` is registered (T40): its options, variables, dimensions, checks, winding and
thermal network work, but `geometry` raises `NotSolvableYet`.

## Scope

B07 rotor with magnets in the barriers (fill ratio); 2D section; MTPA.

## Acceptance criteria

- [ ] `geometry` returns a request for a registered geometry builder; the solver gives torque and the
      flux linkage of every phase.
- [ ] Validated against a published machine or an analytic reference.
