# T11: Design evaluation: objectives and constraints

Status: done
Depends on: T04, T05, T06, T07, T08, T09, T10

## Why

One function must turn a design vector into the numbers the optimizer compares.

## Scope

`tfm/evaluate.py`: `evaluate(spec, values, workdir)` returns objectives, constraint violations
and a full result record.

Steps: feasibility check; if infeasible stop without field analysis; parameters; field analysis
at the chosen fidelity; torque metrics for the number of phases; electrical model and turns;
iron loss; thermal iteration with copper loss; constraints; objectives.

- Objectives (all minimised internally): negative mean torque, total loss, torque ripple.
- Constraints: geometry, turns feasible (current and voltage), winding temperature, magnet
  temperature, current density.
- Cache: results are stored under a hash of specification and design, so repeated designs cost
  nothing and an interrupted optimization can resume.
- Failures (meshing or solver errors) are caught and returned as an infeasible result with the
  reason recorded.

## Acceptance criteria

- [x] An infeasible geometry returns in under 10 ms with no field analysis started.
- [x] A second call with the same design reads the cache and starts no solver.
- [x] The record contains every intermediate number: torque waveform, turns, currents,
      voltages, losses, temperatures, run time.
- [x] A solver failure does not raise; it yields a result marked failed.
- [x] The reference design evaluates end to end with plausible numbers.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T11-1 | Infeasible design (hub collision) | Violation > 0, `analysed = false`, under 10 ms |
| T11-2 | Evaluation with a stand-in field analysis (analytic waveform) | Objectives equal hand-computed values |
| T11-3 | Same design twice with the stand-in | Second call reports a cache hit; stand-in called once |
| T11-4 | Stand-in that raises an error | Result marked failed, no exception |
| T11-5 (slow) | Reference design, real analysis, fast fidelity | Mean torque > 0, losses > 0, temperatures above ambient, record complete |

## Result

Completed 2026-10-13.

- `tfm/evaluate.py`: `evaluate`, `cache_key`, `BatchEvaluator`, and `analytic_stand_in` for testing
  the workflow without the field solver.
- Tests in `tests/test_t11_evaluate.py`: T11-1 to T11-4 pass; T11-5 passes with `TFM_SLOW=1` (35 s).
- Extra tests: three-phase objectives (three sin^2 phases give three times the torque and no
  ripple), an electrically infeasible design is flagged, the batch adapter evaluates duplicates once.
- T11-5, reference design with the field solver at `fast` fidelity, 300 rpm, one phase:

| Quantity | Value |
|---|---|
| Mean torque | 1.013 Nm |
| Total loss | 5.49 W (copper 4.25 W, stator iron 1.25 W) |
| Torque ripple (peak-to-peak / mean) | 3.58, as expected for a single phase |
| Turns | 213 (allowed range 25 to 213) |
| Peak current | 1.70 A |
| Bus voltage needed | 47.8 V |
| Winding / magnet temperature | 64.8 C / 39.5 C |
| Output power, efficiency | 31.8 W, 85.3 % |
| Evaluation time | 35 s |

- Added constraint `core_flux_density` (see T09), so the optimizer cannot exploit the linear
  material model.
- Failures of the analysis are not cached, so a later call retries them.

### Correction, 2026-10-13 (ticket B05)

The iron losses and core flux densities above were computed from Elmer's smoothed nodal flux
density, which loses about a fifth of the flux in thin iron parts. Since B05 the element field
is used. Iron loss is about 25 % higher than stated above (reference design, saturating core:
0.93 W before, 1.16 W now). Torque, flux linkage, voltages, turns and copper loss are unchanged.
