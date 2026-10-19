# T23: Coil of stacked flat copper rings (strip winding)

Status: done
Depends on: T11, T17

## Why

The coil of the machine is not many turns of thin round wire. It is a stack of flat copper
rings, a thick rectangular strip wound like the coil in the user's picture of 2026-10-14. Such
a coil has few turns, a high copper fill and a phase resistance in the milliohm range.

The model so far assumes round wire: copper fill 0.45 and as many turns as the bus voltage
allows (198 turns of 0.26 mm wire in the T22 best compromise).

## Physics the change rests on

- At given ampere-turns N I, the copper loss is rho * l_turn * (N I)^2 / A_copper. It does not
  depend on the number of turns; it falls only with more copper area A_copper = fill * A_coil.
- The resistance scales with N^2 and the current with 1 / N. Few turns give a small resistance
  and a large current at a low voltage, with the same loss.
- The real gain of a strip coil is the fill: about 0.85 instead of 0.45. At equal torque the
  copper loss falls to 0.45 / 0.85 = 53 %.

## Scope

- `winding.conductor`: `"round_wire"` (default, unchanged) or `"strip"`.
- `winding.strip_fill_factor` (default 0.85): copper share of the coil cross-section for a strip
  coil. `winding.fill_factor` keeps its meaning for round wire.
- `winding.strip_min_thickness_mm` (default 0.3): thinnest copper strip that can be wound. The
  layers are stacked across the coil height (a flat spiral, as in the picture), so a coil of
  copper height h * fill holds at most floor(h * fill / t_min) layers.
- `winding.turns`: `null` (default) chooses the number of turns as before: the most turns the
  bus voltage allows, now also capped by the strip thickness. A whole number fixes the turns
  (layers); the limits on current and bus voltage still apply to it.
- Copper fill, copper loss, current density, efficiency map, thermal input and the parameter
  sheet all use the fill of the chosen conductor.
- Parameter sheet: for a strip coil it lists layers, strip width x thickness, copper area,
  current and the phase resistance in milliohm.
- Not in scope: eddy currents in the strips (small at the 125 Hz of the rated point; the strip
  is thinner than the skin depth of 5.8 mm), and the better heat conduction along the strips
  (the thermal model keeps the conductivity of a wire bundle, which is conservative).

## Acceptance criteria

- [x] With the default specification all results are exactly as before.
- [x] A strip coil at the same ampere-turns has copper loss lower by the ratio of the fills.
- [x] The number of layers never exceeds floor(h * fill / t_min); the strip thickness of the
      chosen layers is at least t_min.
- [x] A fixed `winding.turns` is used as given; a value that breaks the current or the voltage
      limit is reported as a violation.
- [x] The parameter sheet of a strip design shows layers, strip size and resistance in milliohm.
- [x] The specification rejects an unknown conductor and fills outside (0, 1].

## Test cases

| ID | Test | Expected |
|---|---|---|
| T23-1 | `choose_turns` with default spec against values stored before the change | Equal |
| T23-2 | Same design, round wire and strip, same ampere-turns | Loss ratio = 0.45 / 0.85 within 1e-9 |
| T23-3 | Strip coil, voltage allows 198 turns, h = 5.64 mm, fill 0.85, t_min 0.3 | 15 layers, strip at least 0.3 mm |
| T23-4 | Fixed `winding.turns` = 4 with a 15 A limit and 118 ampere-turns peak | 4 turns used, violation > 0 |
| T23-5 | Parameter sheet of a strip pick | Rows for layers, strip size, resistance in mOhm |
| T23-6 | Spec with conductor "litz" and with strip fill 1.2 | SpecError naming the key |
| T23-7 | Dry-run optimization with a strip coil | Runs; every trade-off design within the limits |

## Result

Code and tests completed 2026-10-14.

- `tfm/spec.py`: `winding.conductor`, `strip_fill_factor`, `strip_min_thickness_mm`, `turns`;
  `copper_fill(spec)`. `tfm/design.py`, `tfm/electrical.py`, `tfm/effmap.py` use it.
- `tfm/electrical.py` `choose_turns`: layer cap for a strip coil, fixed turns, violation of the
  current limit, the bus voltage or the layer cap; strip width and thickness in the result.
- Report (`tfm_optimize.py`): coil type in the Problem table, layers and phase resistance per pick.
  Parameter sheet (`tfm/onshape.py`): layers, strip size, resistance in milliohm. ParaView report
  prints the resistance in milliohm when it is below 1 ohm.
- `spec_three_phase.json` and `specs/three_phase_*.json` now set `"conductor": "strip"`.
- Tests in `tests/test_t23_strip_coil.py`: T23-1 to T23-7 pass; full suite 195 tests OK.
- The field solutions are untouched: the coil region carries the same ampere-turns with a uniform
  current density whether it is made of wire or of strip.

Measured on the T22 best compromise (U-I, 25 pole pairs; direct solution, medium mesh, 24
positions), with the strip coil at the same ampere-turns (118.5 A peak), so on the very same
field solution:

| Coil | Torque | Loss | Efficiency | Winding | Turns | Peak current | Resistance | Bus voltage |
|---|---|---|---|---|---|---|---|---|
| Round wire, fill 0.45 | 0.534 Nm | 7.98 W | 67.8 % | 69 C | 197 of 0.26 mm wire | 0.60 A | 12.74 ohm | 47.9 V |
| Strip, fill 0.85 | 0.534 Nm | 4.48 W | 78.9 % | 49 C | 15 layers of 4.00 x 0.32 mm | 7.90 A | 36.5 milliohm | 3.2 V |

The bus voltage of the strip coil is below the 12 V lower end of `limits.bus_voltage_V` (flagged,
not a violation). The current limit of 15 A peak allows no fewer than 8 layers at this load.
The optimization has not been rerun with the strip coil.
