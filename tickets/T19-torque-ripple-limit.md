# T19: Torque ripple limit

Status: done
Depends on: T05, T11, T13

## Why

The user looked at the torque of the single-phase reference design (0.86 Nm mean, swinging
between -0.9 and 2.1 Nm) and asked that designs with a torque ripple above a limit be discarded.
The limit is to be a parameter with a default of 20 %.

## Scope

- `limits.max_torque_ripple_percent`, default 20. `null` switches the limit off.
- Ripple is defined as before: (highest - lowest) / mean of the machine torque over one
  electrical period, here in percent.
- A design above the limit is infeasible. It never appears among the trade-off designs or picks.
  The constraint value grows with the excess, so the search is drawn towards smooth designs.
- The report lists the limit and shows ripple in percent. Result tables get a `ripple_percent` column.
- One phase: a single phase under sinusoidal current pulsates between about zero and twice its
  mean, so its ripple is about 200 % before cogging is added. The optimizer says so before it
  starts when the machine has one phase and the limit is below 150 %.
- The single-phase example `spec_example.json` is kept as a regression case with the limit
  switched off. The user's problem is `spec_three_phase.json`: three phases in 29 mm, as the user
  specified: 2 mm legs, 5 mm slot, 1 mm between the phases (3 x 9 mm + 2 x 1 mm = 29 mm).
- Space between the phases: it is the parameter `machine.phase_spacing_mm` (since T02) and is now
  shown with the macro inputs in the report. It is not an optimization variable: phases are
  modelled as magnetically independent, so the model sees no cost in a smaller space and the
  search would always end at the lower bound. The leg width is fixed with `variables.leg_width_mm`.

Also in this ticket, because changing a limit should not cost hours:

- Field solutions are cached separately from the limits (`cache/fields/`). Changing a limit, the
  speed, the thermal data or the objectives re-uses every field solution of the run folder.
- The field cache is keyed by geometry, mesh, materials, ampere-turns, positions and model
  version, and by whether the field solver or the dry-run estimate produced it.

## Acceptance criteria

- [x] With the default specification the limit is 20 %.
- [x] A design with more ripple than the limit has a positive violation; one below has none
      from this constraint.
- [x] `null` switches the limit off.
- [x] No trade-off design of an optimization exceeds the limit.
- [x] A negative or zero limit is rejected with a clear message.
- [x] The report states the limit; a single-phase run with a 20 % limit prints the warning.
- [x] Evaluating the same design with a different limit does not call the field analysis again.
- [x] A dry-run result is never served to a field-solver run from the same folder.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T19-1 | Default specification | `limits.max_torque_ripple_percent` = 20 |
| T19-2 | Three-phase design with 12.6 % ripple (stand-in), limit 20 %, 10 % and null | Violation 0; positive and equal to 12.6/10 - 1; 0 |
| T19-3 | Single-phase design (ripple above 200 %), limit 20 % | Violation positive, capped at 10 |
| T19-4 | Limit -5 and limit "x" | `SpecError` naming the key |
| T19-5 | Dry-run optimization of `spec_three_phase.json` with limit 15 % | Every row of `pareto.csv` has `ripple_percent` <= 15; report shows "15 %" |
| T19-6 | Dry-run optimization, one phase, limit 20 % | Warning in the output; exit with "No design met every limit" |
| T19-7 | Evaluate a design, then again with another limit, counting analysis calls | One call |
| T19-8 | Evaluate with the stand-in, then with another analysis function in the same folder | The second function is called |
| T19-10 | `spec_three_phase.json` | Phase width 9 mm, leg fixed at 2 mm, slot 5 mm, spacing 1 mm |
| T19-9 (slow) | Field-solver evaluation of a three-phase design in 29 mm | Runs; ripple reported; record says whether the limit is met |

## Result

Completed 2026-10-13.

- `limits.max_torque_ripple_percent` (default 20, `null` = off) in `tfm/spec.py`; constraint
  `torque_ripple` in `tfm/evaluate.py`, capped at 10 so that it does not swamp the other limits.
- `tfm_optimize.py`: the limit is listed in the report, ripple is shown in percent, the tables
  have a `ripple_percent` column, the log names the limits a design violates, and a single-phase
  run with a limit below 150 % prints a warning before it starts.
- `spec_three_phase.json`: three phases in 29 mm with 2 mm legs (fixed), 5 mm slots and 1 mm
  between the phases, as the user specified. `spec_example.json` keeps the single-phase case
  with the limit switched off.
- Field cache `cache/fields/`: `evaluate.field_key`. Dry-run results carry the name of the
  analysis function in their keys, so they are never served to a field-solver run.
- Tests in `tests/test_t19_ripple_limit.py`: T19-1 to T19-8 and T19-10 pass; T19-9 passes with `TFM_SLOW=1`.
- T19-9 (field solver, 29 mm, 18 pole pairs, 3 A/mm2, 6 positions): 0.134 Nm, ripple 15.1 %.
- Evidence for the phase count, from the 36 single-phase designs cached before: summed as three
  phases their ripple ranges from 3.6 % to over 1000 %; 6 of 36 are below 20 %.
- Older single-phase tests (T11) now switch the limit off explicitly.
