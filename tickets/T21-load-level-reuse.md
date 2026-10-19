# T21: Reuse of field solutions across current density

Status: done
Depends on: T17, T20

## Why

Current density changes the ampere-turns and nothing else in the geometry. The search spends
field solutions on rediscovering this one axis: in the earlier runs half of the trade-off
designs were the same geometry at different current densities.

## Scope

- With `fidelity.load_levels` = L (2 to 5), a geometry is solved at L current densities spread
  over the range of the current-density variable. Any current density of that geometry is then
  evaluated by interpolation in ampere-turns (shape-preserving cubic, as in the efficiency map):
  torque waveform, flux waveform and iron-loss coefficients.
- The optimizer gets, for every geometry it asks about, `optimizer.current_steps` further designs
  of the same geometry along the current-density range at no field cost. They join the
  offspring of that generation.
- Combined with T20: all levels of a geometry are solved at the first stage; the geometry is
  refined unless every current density of it fails the limits by more than the margin.
- `fidelity.load_levels` = 0 (default) keeps one field solution per design, as before.
- Cost: a new geometry costs L sweeps instead of one. Whether the search as a whole gets
  faster depends on how many of the free designs are useful; that needs a comparison of two
  optimizations with the field solver, which is not part of this ticket.

## Acceptance criteria

- [x] At a current density equal to a level, the result equals the direct result.
- [x] Between levels, torque is within 2 % and ripple within 3 percentage points of a direct
      field solution (three levels, reference geometry).
- [x] The free designs of a geometry cost no field solution.
- [x] With the feature off, results and optimizer behaviour are exactly as before.
- [x] A design that came from interpolation is marked as such.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T21-1 | Levels for a range of 1 to 10 A/mm2 and L = 3; a fixed current density | 1, 5.5, 10; a single level |
| T21-2 | Stand-in (linear in current): design between levels against direct evaluation | Torque, loss and ripple equal within 1e-6 relative |
| T21-3 | Geometry asked twice with different current densities, counting analysis calls | L calls the first time, none the second |
| T21-4 | `evaluate_geometry` with 6 further designs | 7 records, same geometry, current densities spread over the range, all marked |
| T21-5 | Optimizer with an evaluator that hands back further designs | They are in the archive and compete for survival; without them the result is unchanged |
| T21-6 | Dry-run optimization with `load_levels` 3 | Runs; every trade-off design within the limits; report states the setting |
| T21-7 (slow) | Field solver, reference geometry, L = 3: current densities halfway between levels | Torque within 2 %, ripple within 3 percentage points of direct solutions |
| T21-8 (slow) | Same with L = 2 | Deviation recorded in the result (no pass mark) |

## Result

Code and tests completed 2026-10-13. Off by default; not yet compared in a full optimization.

- `tfm/evaluate.py`: `load_levels`, `interpolate_fields`, `sibling_densities`,
  `evaluate_geometry`; `BatchEvaluator.take_extra`. `tfm/nsga2.py` adds designs handed back by
  the evaluator to the archive and to the offspring.
- `fidelity.load_levels` (0 = off, 2 to 5) and `optimizer.current_steps` (default 6).
- Tests in `tests/test_t21_load_levels.py`: T21-1 to T21-6 pass; T21-7 and T21-8 pass with `TFM_SLOW=1`.
- Measured with the field solver (three phases in 29 mm, 18 pole pairs, levels over 1 to 10 A/mm2):

| Levels | Current density | Direct torque, ripple | Interpolated torque | Ripple | Loss |
|---|---|---|---|---|---|
| 3 | 3.25 A/mm2 | 0.1445 Nm, 17.2 % | +0.07 % | -0.12 points | +0.20 % |
| 3 | 7.75 A/mm2 | 0.3409 Nm, 10.6 % | -0.03 % | 0.00 points | 0.00 % |
| 2 | 3.25 A/mm2 | 0.1445 Nm, 17.2 % | -0.39 % | -0.23 points | +0.66 % |
| 2 | 7.75 A/mm2 | 0.3409 Nm, 10.6 % | -0.22 % | -0.17 points | +0.13 % |

- Two levels are enough for this machine: its thin cores saturate little over the current range.
  A machine that saturates more (the single-phase reference lost 10 to 17 % of torque over its
  load range) would need three.
- First use: the stator-type comparison of 2026-10-14 runs with two levels (see T22).
