# T37: Optimization: interface, NSGA-II, random search

Status: done
Depends on: T36

## Why

NSGA-II is the only optimizer and `tfm_optimize.py` knows it directly.

## Work

1. `optimization/problem.py`: `Problem` (variables, objectives, constraints) built from a spec and
   a machine.
2. `optimization/nsga2.py` as `Optimizer` "nsga2"; `optimization/random_search.py` "random".
3. `optimization/seeding.py`; `optimization/run.py`: generations, checkpoints, picks.
4. Spec `optimizer.algorithm` chooses the optimizer.

## Acceptance criteria

- [x] NSGA-II results equal to characterization (fixed seed)
- [x] Random search finds the optimum of a test function
- [x] A new optimizer needs only its module

## Test cases

| ID | Test | Expected |
|---|---|---|
| T37-1 | NSGA-II on ZDT1 with fixed seed | Equal to the recorded front |
| T37-2 | Random search on a convex problem | Within tolerance of the optimum |
| T37-3 | Optimizer chosen by spec | Registry lookup; unknown name error |

## Result

2026-10-16.

- `emachine/optimization/pareto.py` (constrained domination, sorting, crowding, front, key),
  `nsga2.py` (`NSGA2`, registered "nsga2"; the algorithm unchanged), `random_search.py`
  (`RandomSearch`, registered "random"). The optimizer package imports only `core`: it sees a
  `Problem` and an evaluation function.
- Spec key `optimizer.algorithm` (default "nsga2"), validated against the registry; the optimize
  command creates the optimizer by that name.
- Seeding moved to `emachine/pipeline/seeding.py` (it needs the design space and the caches).
- `tfm/nsga2.py`, `tfm/seeding.py` are adapters.
- Tests: NSGA-II through the interface reproduces the characterization run (fixed seed); random
  search finds the minimum of a sphere within 5e-3; algorithm chosen by the spec, unknown name
  rejected; the optimize command runs a dry run with random search. Slow T12, T13, T15, T16 pass.
