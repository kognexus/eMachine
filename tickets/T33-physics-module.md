# T33: Machine-independent physics in `emachine/physics`

Status: done
Depends on: T32

## Why

Electrical, loss, thermal and torque models are generic in substance but take TFM-specific
inputs (ring coil, one-phase network). They move behind the interfaces of `core`.

## Work

1. `physics/winding.py` (resistance, copper loss, induced voltage, turns choice) from a
   `Winding` description instead of TFM dimensions.
2. `physics/losses.py` (stator core per harmonic ellipse, rotor eddy currents) as a `LossModel`.
3. `physics/thermal.py`: a generic network solver; the TFM network moves to `machines/tfm`.
4. `physics/torque.py`: machine torque from per-phase or all-phase sweeps, ripple metrics.
5. `tfm/electrical.py`, `tfm/losses.py`, `tfm/thermal.py`, `tfm/torque.py` re-export.

## Acceptance criteria

- [x] Physics modules depend only on `core` and NumPy
- [x] Characterization tests unchanged
- [x] Old tests pass through the re-exports

## Test cases

| ID | Test | Expected |
|---|---|---|
| T33-1 | Winding from a description | Same resistance and turns as the TFM functions |
| T33-2 | Loss model interface | Same coefficients as T31 on stored fields |
| T33-3 | Thermal network solver on a given network | Same temperatures as before |
| T33-4 | Torque from per-phase and all-phase sweeps | Per-phase shift equals old result; all-phase sum direct |

## Result

2026-10-16.

- `emachine/physics/winding.py`: resistivity, one-turn resistance, resistance, copper loss, flux
  slope, volts per turn, usable phase voltage, turns choice, all from explicit quantities (copper
  material, copper area, turn length, voltage per turn, limits).
- `emachine/physics/thermal.py`: network solver on a `ThermalNetwork`, response per source,
  coupled copper-loss iteration, `LumpedNetwork` (ThermalModel). The TFM network moved to
  `emachine/machines/tfm/thermal.py`.
- `emachine/physics/torque.py`: machine torque for any number of phases (90 degrees for two), over
  half or full period samples; metrics.
- `emachine/physics/losses.py`: the T31 loss model, `CoreAndRotorLoss` (LossModel).
- `emachine/spec/`: the specification loader (still with the TFM sections; they move in T34).
- `tfm/electrical.py`, `thermal.py`, `torque.py`, `losses.py`, `spec.py` are adapters with the old
  signatures.
- Layering test for all packages (`tests/unit/core/test_import_rule.py`).
- Tests: `tests/unit/physics/` (13 tests, written first); characterization data reproduced
  (fast and slow); all 276 fast tests pass.
