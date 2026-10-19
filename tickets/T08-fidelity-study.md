# T08: Mesh fidelity study for optimization

Status: done
Depends on: T07

## Why

An optimization evaluates many designs. Each must be as cheap as possible while keeping the
ranking of designs correct. This ticket measures how results change with mesh size and number
of positions, and fixes the default fidelity levels.

## Scope

- Script `studies/fidelity_study.py` runs the reference design at several air-gap cell sizes
  and records mean torque, peak flux, core-field level and run time.
- Define two named levels in the specification defaults: `fast` for optimization and `fine`
  for checking the final designs.
- Record the table of results in this ticket.

## Acceptance criteria

- [x] At least three mesh sizes compared against the finest.
- [x] The `fast` level deviates from the finest by less than 5 % in mean torque and peak flux.
- [x] Run time per design at the `fast` level is recorded.
- [x] The chosen levels are the defaults of the `fidelity` section of the specification.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T08-1 (slow) | Run the study script | Table with one row per mesh size written to `studies/fidelity_results.csv` |
| T08-2 | Compare `fast` with the finest level in that table | Mean torque and peak flux within 5 % |
| T08-3 | `load_spec` defaults | `fidelity.level` exists and maps to the chosen cell-size factor |

## Result

Completed 2026-10-13.

Study: reference design, 12 positions over half an electrical period, sinusoidal drive, six
positions in parallel. Script `studies/fidelity_study.py`, results in `studies/fidelity_results.csv`.

| Cell factor | Cell size | Elements | Mean torque | Peak flux per turn | Torque peak-to-peak, 1 phase | Torque peak-to-peak, 3 phases | Time |
|---|---|---|---|---|---|---|---|
| 0.6 | 0.30 mm | 211 833 | 1.023 Nm | 367.1 uWb | 3.24 Nm | 2.09 Nm | 119 s |
| 1.0 | 0.50 mm | 93 081 | 1.013 Nm (-1.0 %) | 365.0 uWb (-0.6 %) | 3.45 Nm (+6 %) | 1.92 Nm (-8 %) | 50 s |
| 1.5 | 0.75 mm | 54 347 | 1.013 Nm (-1.0 %) | 361.7 uWb (-1.5 %) | 3.62 Nm (+12 %) | 1.80 Nm (-14 %) | 36 s |
| 2.0 | 1.00 mm | 38 028 | 0.988 Nm (-3.5 %) | 357.5 uWb (-2.6 %) | 3.95 Nm (+22 %) | 1.74 Nm (-17 %) | 30 s |
| 3.0 | 1.50 mm | 22 489 | 0.970 Nm (-5.2 %) | 348.8 uWb (-5.0 %) | 4.10 Nm (+26 %) | 1.76 Nm (-15 %) | 24 s |

Decision:

- `fast` = factor 1.5: mean torque and flux within 1.5 % of the finest mesh, 36 s per design.
- `fine` = factor 0.6, for checking final designs.
- Both are now the defaults of the `fidelity` section.

Caveat: torque ripple is much more mesh-sensitive than mean torque. At the `fast` level the
peak-to-peak torque is off by 12 to 14 %. Ripple values from an optimization are good for ranking
designs but should be confirmed at the `fine` level.

Tests in `tests/test_t08_fidelity.py`: T08-1 (table has five sizes), T08-2 (fast level within 5 %
of the finest in mean torque and peak flux) and T08-3 (defaults) pass.
