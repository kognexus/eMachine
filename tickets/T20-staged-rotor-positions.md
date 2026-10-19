# T20: Rotor positions in two stages

Status: done
Depends on: T07, T11, T19

## Why

Most candidate designs fail a limit, above all the torque ripple limit, and that is visible long
before all rotor positions are solved. The user asked for a hierarchical search: coarse rotor
positions first, more positions only for designs worth it.

## Scope

- A design is first solved at every second rotor position (6 of 12). The other positions are
  solved only if the design passes a check. The two halves together are exactly the positions of
  a full sweep, so nothing is solved twice and the refined result equals an unstaged one.
- What the first stage gives:
  - mean torque, flux, voltage, turns and losses: close to final (for three phases the dominant
    ripple harmonic cancels in the mean of the half sweep);
  - torque ripple: a lower bound. The full sweep contains the same samples plus others, so its
    peak-to-peak value cannot be smaller.
- Check: the design is stopped after the first stage when it violates the limits by more than
  `fidelity.early_stop_margin` (default 0.1, that is 10 %) in total. It is then infeasible
  whatever the second stage shows, so it can never be a trade-off design.
- A design stopped early keeps its first-stage numbers, marked as such: its ripple is a lower bound.
- `fidelity.staged` (default true) switches the behaviour off. Staging is also off when the
  number of positions is odd, below 6, or for three phases not a multiple of 6.
- Not done: stopping designs that meet the limits but look worse than known designs. A design
  dropped that way would keep an optimistic ripple value and could later appear among the
  trade-off designs when its better neighbour leaves the population. Only the limit check is safe.

## Acceptance criteria

- [x] A design that passes the check has the same result as with staging switched off.
- [x] A design that fails the check costs half the rotor positions.
- [x] No design stopped early is feasible.
- [x] The ripple of the first stage never exceeds the ripple of the full sweep, on the same solver.
- [x] Reports and tables say which designs were stopped early and how many positions were solved.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T20-1 | `staging` for 12 positions and 1 or 3 phases; 9 positions; 6 positions and 3 phases; switched off | 6; none; none; none |
| T20-2 | Half sweep and shifted half sweep of the stand-in, interleaved | Equal to the full sweep, sample for sample |
| T20-3 | Design within the limits, staged and unstaged, counting solved positions | Identical records; 12 positions in both |
| T20-4 | Design far above the ripple limit, staged | Stopped after 6 positions; marked; infeasible; ripple not above the unstaged ripple |
| T20-5 | Analysis function without a `shift` argument | Still works: the refinement solves the full sweep |
| T20-6 | Dry-run optimization with staging on and off, same seed | Same trade-off designs; fewer positions solved with staging |
| T20-7 (slow) | Field solver, three phases: one design staged against unstaged | Torque samples equal within 0.5 % of the peak; the first-stage ripple is not above the full ripple |
| T20-8 (slow) | Field solver: a design with ripple far above the limit | Stopped after 6 positions; time about half |

## Result

Completed 2026-10-13.

- `tfm/evaluate.py`: `staging`, `solve_fields` (first stage, check, second stage), `interleave`.
  `tfm/em.py` and `tfm/electrical.py` take a `shift`, so the second stage solves the positions in
  between and the two stages together are the full sweep.
- `fidelity.staged` (default true) and `fidelity.early_stop_margin` (default 0.1).
- The log, the tables (`positions`, `stopped_early`) and the report say which designs were
  stopped and how many rotor positions were solved.
- Tests in `tests/test_t20_stages.py`: T20-1 to T20-6 pass; T20-7 and T20-8 pass with `TFM_SLOW=1`.
- Measured with the field solver (three phases in 29 mm, 18 pole pairs, 12 positions):
  - staged and unstaged torque samples agree within 0.5 % of the peak;
  - full ripple 18.7 %, first-stage ripple 15.1 % (a lower bound, as intended);
  - mean torque of the first stage / full sweep = 1.0008;
  - a design stopped after the first stage takes 27 s instead of 54 s.
- T20-6 holds for the stand-in because its first-stage violation equals the full one. With the
  field solver the two searches may take different paths, since a stopped design keeps slightly
  different numbers; the guarantee is only that no stopped design is feasible.
- A first stage read from the cache has no raw solution left, so its refinement solves all
  positions again. This happens only when a limit is relaxed between runs.
