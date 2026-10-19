# B03: Thermal finite-element check in Elmer

Status: backlog
Depends on: T10

## Why

The lumped thermal network uses assumed coefficients. A finite-element heat-conduction
solution on the same sector mesh would check its temperatures.

## Scope

- Elmer heat equation on the stator solids with loss densities from T09 and convective
  boundaries from the `thermal` section.
- Comparison of winding and core temperatures with the lumped network.

## Acceptance criteria

- [ ] Heat balance of the finite-element solution closes within 1 %.
- [ ] Lumped and finite-element winding temperatures agree within 10 K for the reference
      design, or the network is recalibrated and the change documented.

## Test cases

| ID | Test | Expected |
|---|---|---|
| B03-1 (slow) | Reference design at its rated point | Temperatures reported for both models, difference recorded |
