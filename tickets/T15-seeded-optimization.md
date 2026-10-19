# T15: Seeded optimization

Status: in progress
Depends on: T12, T13

## Why

Every optimization so far started from random designs and stopped long before it converged. The
best designs of earlier runs are known and should be the starting point of the next run.

## Scope

- `tfm_optimize.py --seed-from PATH [PATH ...]` starts the search from existing designs.
  A path is one of:
  - a run folder (its `pareto.csv` is used);
  - a `.csv` table with one column per design variable;
  - a `.json` parameter file written by the optimizer (`designs/*.json`), a dictionary of design
    variable values, or a list of such dictionaries.
- Seed designs are fitted to the current specification: values outside the current ranges are
  clipped, variables the source does not have take the middle of their range, and seeds that
  fail the geometry checks are dropped. The command says how many were clipped, filled or dropped.
- Every seed is evaluated with the current specification. If there are more seeds than the
  population holds, the population is chosen from all of them by the normal survival rule.
  `--max-seeds` caps the number that is evaluated.
- Places not taken by seeds are filled with random feasible designs, as before.
- A seed whose result is already in the cache of the source run (same specification) is not
  solved again.
- `--seed-from` on an existing run adds the seeds to its current population.
- The run folder records the specification (`spec.json`) and the seeds (`seeds.json`); the report
  says where the seeds came from.

## Acceptance criteria

- [ ] A run seeded with a design contains that design in its first generation.
- [ ] A seeded run never ends with a worse trade-off than its seeds: every seed is either in the
      final trade-off set or dominated by a member of it.
- [ ] Seeds outside the current ranges are clipped and reported, not rejected.
- [ ] Runs without `--seed-from` give exactly the same result as before this ticket.
- [ ] Seeds already evaluated under the same specification are read from the cache.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T15-1 | Read seeds from a run folder, a CSV file, a pick file and a dictionary | Same values come back for all four forms |
| T15-2 | Seed with a pole-pair count above the current limit | Clipped to the limit, counted as clipped |
| T15-3 | Seed from a source without `bridge_height_mm` into a UI specification | Filled with the middle of the range, counted as filled |
| T15-4 | `nsga2.optimize` with more starting designs than the population | All are evaluated, population has the requested size and holds the best of them |
| T15-5 | Dry run A, then dry run B seeded from A with 0 generations | Every trade-off design of A is in B's archive and in B's trade-off set |
| T15-6 | Dry run B seeded from A with 3 more generations | No trade-off design of A dominates a trade-off design of B that it is not equal to; report names the seed source |
| T15-7 | Seeding with the same specification | Cache files are copied; seeds are reported as cached, not re-analysed |
| T15-8 | `--seed-from` on an existing run | Seeds are added to the archive and the run continues |
| T15-9 | Existing T12 and T13 tests | Unchanged and passing |

## Result

Code and tests completed 2026-10-13. The result of the seeded field-solver run is recorded below
when the run has finished.

- `tfm/seeding.py` reads and fits seeds; `tfm_optimize.py --seed-from PATH ... [--max-seeds N]`.
- `tfm/nsga2.py`: `optimize(initial=...)` accepts more starting designs than the population and
  keeps the best by the survival rule; `optimize(inject=...)` adds designs to a resumed run.
- Run folders now hold `spec.json` (complete specification) and `seeds.json`.
- Seeds from a run folder are read with the exact values of its cache records, not the rounded
  values of `pareto.csv`, so cached results match.
- Tests in `tests/test_t15_seeding.py`: T15-1 to T15-8 pass; T12 and T13 tests pass unchanged
  (T15-9), except that the T13 pick-file test now expects the two sections added in T16.
- T15-5 was reworded while testing: the place not taken by a seed holds a random design, which
  may join the trade-off set, so the seeded set contains the seeds' set rather than equals it.

SEEDED_RUN_RESULT
