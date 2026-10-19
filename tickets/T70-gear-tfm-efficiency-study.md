# T70: Gear TFM at 85 mm and 150 rpm: study frame and efficiency objective

Status: done
Depends on: T24, T26, T27, T28

## Why

The user (2026-10-18): "I'd like to try the gear shaped tfm with three phase with OD of 85mm and I'd like
to optimize the geometry of the motor to get highest efficiency >90% at 150 RPM." Allowed beyond the
current parameters: magnet slots against flux leakage, up to 48 poles, alternate or Halbach rotor,
cutouts or holes along the flux path, skewing. New concepts go into the code base, backward compatible.
The study lives in its own folder, `gear-tfm-150rpm/` (user's request).

"Gear-shaped TFM" is the toothed ring (T24) with arched valleys (T26) and staggered teeth (T27), as
in the user's machine of T28 (`specs/user_tr48.json`).

## Frame

| | Value |
|---|---|
| Machine | toothed ring, outrunner, 3 phases, 85 mm outer diameter (T28: 80 mm), stack 27.2 mm, bore 30 mm, air gap 0.3 mm |
| Speed | 150 rpm |
| Poles | at most 48 (24 pole pairs) |
| Drive | 48 V, 15 A, strip winding (T23), as in T28 |
| Objectives | highest efficiency at 150 rpm and highest torque (trade-off) |

The user named no torque. The efficiency of a machine at one speed has a maximum over the load, where
copper loss equals the other losses. So the study reports the peak efficiency and the torque range
with an efficiency of 90 % or more, and the optimizer keeps efficiency and torque as two objectives.

## Work

1. Objective `max_efficiency` (efficiency at the operating point), and a pick `highest_efficiency`.
   Cached records take the objective vector of the current specification. Their cache key leaves the
   objectives out, so a run with other objectives can reuse them.
2. Study folder `gear-tfm-150rpm/` with `specs/` (baseline: the user's T28 machine at 85 mm and
   150 rpm), `scripts/`, `runs/` and the report.

## Acceptance criteria

- [x] `max_efficiency` is accepted, minimised as -efficiency, and works on cached records.
- [x] `highest_efficiency` is picked when the records carry efficiency; older fronts are unchanged.
- [x] Baseline specification of the study loads (85 mm, 150 rpm, toothed ring, 3 phases).
- [x] Report in `gear-tfm-150rpm/report/` (T74).

## Test cases

| ID | Test | Expected |
|---|---|---|
| T70-1 | Spec with `max_efficiency`; misspelt name | Accepted; error |
| T70-2 | Evaluate with the stand-in, objectives efficiency, torque, losses | f = (-eta, -T, P) |
| T70-3 | Cached record evaluated again with other objectives | Cache hit, f follows the new objectives |
| T70-4 | `choose_picks` with and without efficiency | `highest_efficiency` only when present |
| T70-5 | Study specification | Loads with the values of the frame |

## Result

Tests: `tests/tickets/test_t70_efficiency_objective.py`, all five pass.

Baseline (user's machine at 85 mm, fast mesh, 6 positions per half period, 3 A/mm2): see T74.
