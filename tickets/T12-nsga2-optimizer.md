# T12: Multi-objective optimizer (NSGA-II)

Status: done
Depends on: T01

## Why

Torque, loss and ripple conflict. The result of the optimization is a set of best trade-offs
(a Pareto front), not one design.

## Scope

`tfm/nsga2.py`, using NumPy only:

- Real and integer variables with bounds.
- Simulated binary crossover and polynomial mutation; integers are rounded.
- Constraint handling by constrained domination: feasible beats infeasible; among infeasible
  designs the smaller total violation wins.
- Non-dominated sorting and crowding distance; elitist survival.
- Evaluation through a user function that receives a batch of designs.
- Reproducible from a seed. State is saved after every generation and a run can resume.
- Duplicate designs are not evaluated twice.

## Acceptance criteria

- [x] On a standard two-objective test problem the final front is close to the known front.
- [x] On a constrained problem every design of the final front is feasible.
- [x] Integer variables always hold integers inside their bounds.
- [x] Same seed gives the same result. Resuming after an interruption gives the same final
      population as an uninterrupted run.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T12-1 | ZDT1 with 6 variables, population 40, 60 generations | Mean distance of the front to f2 = 1 - sqrt(f1) below 0.05 |
| T12-2 | Non-dominated sort on a hand-made set of 6 points | Fronts as worked out by hand |
| T12-3 | Constrained problem (two objectives, one constraint) | All final designs feasible |
| T12-4 | Mixed problem with one integer variable | All integer values are whole numbers within bounds |
| T12-5 | Two runs with the same seed | Identical final populations |
| T12-6 | Run 6 generations at once versus 3 generations, resume, 3 more | Identical final populations |
| T12-7 | All designs infeasible at the start | Total violation of the best design decreases over generations |

## Result

Completed 2026-10-13.

- `tfm/nsga2.py`: `optimize`, `pareto_front`, `non_dominated_sort`, `crowding_distance`.
- Tests in `tests/test_t12_nsga2.py`: T12-1 to T12-7 pass, plus tests of the crowding distance and
  of duplicate designs being evaluated once.
- T12-1: on ZDT1 with 6 variables the front reaches a mean distance below 0.05 from the known
  front and covers more than 60 % of its width.
- T12-6: three generations, save, resume for three more gives exactly the population of an
  uninterrupted six-generation run, and only the remaining generations are evaluated.
- Corrections made while testing, both in the tests and not in the optimizer: the hand-worked
  fronts of T12-2 for the infeasible case were wrong (a point freed from its only dominator moves
  to the first front), and T12-3 now checks that every design satisfies the constraint and that
  the front lies within 5 % of the constraint boundary on average.
