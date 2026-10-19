# T17: Torque, speed and efficiency map

Status: in progress
Depends on: T06, T07, T09, T10, B01

## Why

The optimizer rates a design at one speed and one current. A motor is used over a range of both.
The user asked for the torque versus speed versus efficiency map of the optimized design.

## Scope

`tfm_map.py` computes the map of one design with a fixed winding (the turns chosen for it).

- Field solutions at several load levels (ampere-turns from zero to the current cut-off), each a
  sweep over half an electrical period, because torque is not proportional to current once the
  core saturates. The magnetostatic field does not depend on speed, so each load level is solved
  once and reused for every speed.
- From each load level: mean torque, flux-linkage waveform, and the two iron-loss coefficients
  (loss = a_h * f + a_e * f^2).
- Between load levels the quantities are interpolated in ampere-turns.
- For every point of a speed and torque grid: current, terminal voltage, copper loss at the
  winding temperature (thermal model of T10), iron loss, efficiency, temperatures.
- Two envelopes:
  - drive limit: current cut-off and maximum bus voltage;
  - continuous limit: also the winding and magnet temperature limits and the current-density limit.
- Outputs: `efficiency_map.csv` (one row per grid point), `envelope.csv`, `load_levels.csv`,
  `efficiency_map.svg`, `map.md` (summary with the key numbers), `load_levels.json` (the field
  results, reused when the command is run again).

Assumptions, stated in `map.md`:

- current in phase with the induced voltage (no field weakening), sinusoidal;
- losses are copper and stator iron only (rotor, magnet and mechanical losses are ticket B04);
- phases are magnetically independent.

## Acceptance criteria

- [ ] At the optimizer's operating point (rated ampere-turns, rated speed) the map reproduces the
      optimizer's torque, loss and efficiency for the same design.
- [ ] Efficiency is zero at zero speed and at zero torque, and below 100 % everywhere.
- [ ] No point inside the drive limit needs more than the maximum bus voltage or the current cut-off.
- [ ] The maximum torque of the drive limit does not rise with speed.
- [ ] The continuous envelope lies inside the drive envelope.
- [ ] The calculation of the grid from the load-level results is exact for a machine with a
      known closed-form answer.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T17-1 | Synthetic linear machine: flux = psi*cos, torque = k*NI, no iron loss, fixed resistance | Map efficiency equals T*w / (T*w + R*I^2) within 1e-6 at 20 grid points |
| T17-2 | Same machine | Corner speed and no-load speed equal the closed-form values within 1 % |
| T17-3 | Synthetic machine with iron-loss coefficients | Iron loss at (speed, load) equals a_h*f + a_e*f^2 |
| T17-4 | Interpolation between load levels of a saturating torque curve | Torque to ampere-turn inversion returns the ampere-turns of each level exactly, and is monotonic between |
| T17-5 | Dry-run map (analytic stand-in) of the reference design | All output files exist; efficiency within [0, 1); drive envelope does not rise with speed; continuous envelope <= drive envelope |
| T17-6 | Dry-run map, point at rated speed and rated ampere-turns | Torque, loss and efficiency equal `evaluate` with the same stand-in within 1 % |
| T17-7 (slow) | Field-solver map of the reference design, 3 load levels, 6 positions | Runs without failure; rated point equals a direct evaluation with the same positions within 2 %; torque per ampere-turn falls with load |
| T17-8 | Second invocation with a different grid | Field results are reused (no solver call) |

## Result

Code and tests completed 2026-10-13. The map of the optimized design is recorded below when the
optimization has finished.

- `tfm/effmap.py`: load-level field solutions with a store that is reused between invocations,
  shape-preserving interpolation in ampere-turns, the grid calculation and both envelopes.
- `tfm_map.py`: the command, with `--levels`, `--overload`, `--turns`, `--max-speed`,
  `--speeds`, `--torques`, `--dry-run`. `tfm/svgplot.py` draws the picture without a plotting library.
- `tfm/thermal.py`: `response` gives the temperature rise per watt, so the winding temperature of
  every grid point has a closed form. It agrees with the iteration of T10 to 1e-4 K (tested).
- The highest load of the map is the current cut-off or `--overload` (default 2) times the
  current-density limit, whichever is lower. For the designs so far the second applies: the
  optimizer chooses many turns, so the 15 A cut-off is far from being reached.
- Tests in `tests/test_t17_map.py`: T17-1 to T17-6 and T17-8 pass; T17-7 passes with `TFM_SLOW=1`.
  Extra tests: thermal closed form against iteration, `--turns` changes the speed range,
  interpolation with trailing axes.
- T17-7 (reference design, field solver, 6 positions, loads 0, 1 and 2.5 times rated): the rated
  point equals a direct evaluation within 2 % in torque, loss and efficiency; torque per
  ampere-turn falls from rated to 2.5 times rated; mean torque at zero current is below 5 % of rated.
- A consequence of how turns are chosen (most turns the bus voltage allows at the rated speed):
  the speed range of a map ends just above the rated speed. `--turns` shows other windings.

MAP_RESULT
