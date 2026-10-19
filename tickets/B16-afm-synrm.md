# B16: Axial flux synchronous reluctance machine

Status: backlog
Depends on: T45, B10

## Why

A cell of the machine matrix (T45, 2026-10-16): axial flux and the SynRM principle. Axial flux
SynRMs are described in the literature (flux barriers cut into the rotor disc), but nothing is
registered yet.

## Scope

1. Skeleton `afm/synrm` with the rotor layouts `flux_barrier` and `flux_barrier_pm` (variables,
   checks, estimates), as T40 did for the other machines.
2. Geometry with the axial flux geometry of B10 (quasi-3D slices or a 3D sector).

## Acceptance criteria

- [ ] Registered; the matrix cell `afm/synrm` turns `specified`.
- [ ] Geometry and solution; saliency ratio L_d / L_q against an analytic estimate.
