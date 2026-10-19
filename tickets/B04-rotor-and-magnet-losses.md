# B04: Rotor iron and magnet eddy-current losses

Status: done (in T31)
Depends on: T09

## Why

The loss model covers copper and stator iron. Rotor iron and magnet eddy currents can matter at
high pole counts and speeds.

## Scope

- Field history in rotor parts in the rotor frame.
- Loss estimates for rotor iron and for eddy currents in magnets, with segmentation.

## Acceptance criteria

- [x] Rotor and magnet losses reported separately and included in the total (T31).
- [x] Speed dependence: the eddy-current loss rises with the square of the frequency (T31, validated on the Guo et al. TFM).

## Test cases

| ID | Test | Expected |
|---|---|---|
| B04-1 (slow) | Reference design at two speeds | Rotor-side losses rise with speed |
