# T13: Optimization command and report

Status: done
Depends on: T11, T12

## Why

The user runs one command with a specification file and gets the trade-off designs in a form
they can read, compare and take back to CAD.

## Scope

`tfm_optimize.py --spec spec.json --run runs/opt1`:

- Builds the variables from the specification, creates a feasible initial population by
  sampling, runs the optimizer with the evaluation function, saves state every generation,
  and resumes if the run folder already holds a state.
- Outputs in the run folder:
  - `pareto.csv`: one row per trade-off design with variables, objectives, turns, current,
    voltage, losses and temperatures.
  - `all_designs.csv`: every evaluated design.
  - `report.md`: inputs, limits, how many designs were evaluated, the trade-off table, and three
    picks: highest torque, lowest loss, best compromise.
  - `designs/<name>.json`: mesher and pipeline parameter file for each pick, so it can be
    re-analysed at fine fidelity or entered in the Onshape features.
- `--dry-run` uses the analytic stand-in instead of the field solver, to test the workflow
  quickly.

## Acceptance criteria

- [x] `--dry-run` completes in under a minute and writes all outputs.
- [x] A real run with a small budget completes and every trade-off design satisfies all limits.
- [x] Interrupting and restarting the command continues from the last saved generation.
- [x] The report lists the limits that were applied, taken from the specification.
- [x] The parameter file of a pick is accepted by `tfm_pipeline.py`.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T13-1 | `--dry-run` with population 12, 5 generations | Exit 0; `pareto.csv`, `all_designs.csv`, `report.md` and three design files exist |
| T13-2 | Dry run: check every row of `pareto.csv` against the limits | Current <= limit, voltage <= bus maximum, iron thickness within limits |
| T13-3 | Dry run interrupted after 2 generations, then restarted | Final result identical to an uninterrupted run |
| T13-4 (slow) | Real run for the user's case with a small budget | Completes; trade-off table recorded in this ticket |
| T13-5 (slow) | Re-analyse the best-compromise pick at fine fidelity | Mean torque within 10 % of the optimization value |

## Result

Completed 2026-10-13.

- `tfm_optimize.py` with `--spec`, `--run`, `--dry-run`, `--population`, `--generations`, `--seed`.
- Tests in `tests/test_t13_optimize.py`: T13-1 to T13-3 pass in under a second each with the dry
  run, plus tests that a pick's parameter file is accepted by the pipeline and that
  `all_designs.csv` lists every evaluated design.

T13-4, real run for the example case (`spec_example.json`: outrunner, U-core with I-bridge,
Halbach rotor, 80 mm, 23 mm stack, one phase, 300 rpm), population 12, 4 generations, in
`runs/opt_example/`:

- 57 designs evaluated in 31 minutes. 10 rejected by the geometry checks, 47 analysed with the
  field solver, 29 met every limit.
- After two generations all 12 designs of the population met every limit.
- 12 trade-off designs. Extremes and compromise:

| Pick | Torque | Loss | Ripple | Efficiency | Pole pairs | Turns | Peak current | Bus voltage | Winding |
|---|---|---|---|---|---|---|---|---|---|
| Highest torque | 1.05 Nm | 6.12 W | 5.8 | 84.3 % | 26 | 125 | 1.69 A | 47.7 V | 68 C |
| Best compromise | 0.83 Nm | 3.27 W | 10.6 | 88.9 % | 24 | 151 | 1.19 A | 47.9 V | 54 C |
| Lowest loss | 0.06 Nm | 0.48 W | 32 | 78.5 % | 9 | 608 | 0.08 A | 47.9 V | 28 C |

- The limit that rejected most random designs was the core flux density: thin iron sections carry
  too much flux. The optimizer learned to avoid them.

T13-5, best-compromise pick re-analysed at `fine` fidelity (156 000 elements instead of 41 000):

| Quantity | Fast | Fine | Difference |
|---|---|---|---|
| Mean torque | 0.831 Nm | 0.856 Nm | +2.9 % (limit 10 %) |
| Total loss | 3.27 W | 3.38 W | +3.3 % |
| Torque ripple | 10.6 | 8.8 | -16 % |
| Turns | 151 | 145 | |

The design still meets every limit at fine fidelity.

Additional check, three phases with the field solver: the reference design as a three-phase
machine (73 mm stack) gives 3.04 Nm with a ripple of 0.59, against 1.01 Nm and 3.58 for one
phase, 123 turns, 2.95 A peak, 47.8 V bus, 85.3 % efficiency.

Notes:

- The budget of this run is small. It shows the system works; it is not a converged optimum.
  The specification default is population 16 and 8 generations, about 80 minutes.
- Turns are always chosen at the bus-voltage limit, so the current cut-off of 15 A was never the
  binding limit in this case.
- Single-phase ripple is dominated by cogging torque and is large by nature.
