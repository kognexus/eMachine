# T06: Winding and electrical model

Status: done
Depends on: T02

## Why

The field solution works in ampere-turns. The user's limits are in volts and amperes. This
ticket connects them: resistance, induced voltage, and the choice of turns that satisfies both
the current cut-off and the bus voltage.

## Scope

`tfm/electrical.py`:

- Coil geometry: conductor area = coil cross-section * fill factor; mean turn length = 2 * pi *
  mean coil radius.
- Resistance of N turns at a temperature, using the copper temperature coefficient.
- Induced voltage per turn from the flux-per-turn waveform by spectral differentiation over the
  electrical period (the half-period samples are extended with a sign change).
- Terminal voltage waveform v = R * i + N * d(flux)/dt and its peak.
- Both voltage terms scale linearly with N at fixed ampere-turns. Therefore:
  - minimum turns = ceil(peak ampere-turns / current limit),
  - maximum turns = floor(usable bus voltage / peak volts per turn),
  - the design is electrically feasible when minimum <= maximum.
- Usable phase voltage: the bus voltage for one phase (full bridge), bus / sqrt(3) for three
  phases in star.
- Outputs: chosen turns (the maximum, which gives the lowest current), peak and RMS current,
  required bus voltage, resistance, wire area and current density.

## Acceptance criteria

- [x] Resistance matches the hand formula for a known coil.
- [x] For a sinusoidal flux the induced-voltage amplitude equals N * omega * flux amplitude.
- [x] Chosen turns keep peak current at or below the limit and required voltage at or below the
      maximum bus voltage, or the design is flagged infeasible with both numbers reported.
- [x] Copper loss is the same for any number of turns at fixed ampere-turns.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T06-1 | 10 turns, 10 x 11 mm coil, fill 0.5, mean radius 24 mm, 20 C | R = rho * N^2 * 2*pi*r / (area * fill), within 1e-9 |
| T06-2 | Same coil at 100 C | R larger by factor 1 + 0.00393 * 80 |
| T06-3 | Flux per turn = 1e-4 * cos, 18 pole pairs, 300 rpm | Peak volts per turn = omega_e * 1e-4 within 0.1 % |
| T06-4 | 200 ampere-turns peak, limit 15 A | Minimum turns = 14 |
| T06-5 | Volts per turn so high that maximum turns < minimum turns | Infeasible, violation > 0 |
| T06-6 | Copper loss for 14 turns and for 28 turns at the same ampere-turns | Equal within 1e-9 |
| T06-7 | Three phases | Usable voltage = bus / sqrt(3) |

## Result

Completed 2026-10-13.

- `tfm/electrical.py`: resistance, copper loss, spectral flux derivative, volts per turn, `choose_turns`.
- Tests in `tests/test_t06_electrical.py`: T06-1 to T06-7 pass.
- Extra tests: the flux derivative is exact for a flux with a third harmonic; peak current times
  turns returns the ampere-turns; current density and I^2 R are consistent with the turn-independent copper loss.
- Rule implemented: turns = the most the bus voltage allows, which gives the lowest current. The
  result also reports the allowed range of turns and whether the needed voltage is below the bus minimum.
