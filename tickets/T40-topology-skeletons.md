# T40: Skeletons of the other machines

Status: done
Depends on: T34, T36

## Why

The user wants PMSM, IPM, SynRM, PMaSynRM and SRM in TFM, RFM and AFM. This ticket makes them
known to the system with their options, variables and checks; solving comes ticket by ticket.

## Work

1. `machines/rfm/`: pmsm (surface), ipm, synrm, pmasynrm, srm; `machines/afm/`: pmsm, srm;
   `machines/tfm/`: srm (reluctance TFM). Options, variables, derive, checks; geometry raises a
   clear "not yet implemented" error naming the follow-up ticket.
2. `OperatingPoint.current_angle_deg` used by the pipeline; MTPA search helper in `analysis/`.
3. `emachine list` shows which machines can be solved.

## Acceptance criteria

- [x] All listed machines registered
- [x] Spec of each validates; checks run
- [x] Solving a skeleton gives a clear message

## Test cases

| ID | Test | Expected |
|---|---|---|
| T40-1 | Registry lists all machines | Families x topologies as agreed |
| T40-2 | Variables, derive, checks of each skeleton | Run without error on its default spec |
| T40-3 | Geometry of a skeleton | NotImplementedError with the ticket name |

## Result

2026-10-16.

- `emachine/machines/base.py`: `SlottedMachine` (slots, concentrated or distributed winding;
  variables pole pairs, bore ratio, tooth ratio, slot depth ratio, yoke, current density; derived
  dimensions with slot area, coil area, turn length, ampere-turns and frequency; checks; winding;
  a four-node thermal network; all-phase excitation) and `NotSolvableYet`.
- `machines/rfm/topologies.py`: `rfm/pmsm` (T41), `rfm/ipm` (B06), `rfm/synrm` (B07),
  `rfm/pmasynrm` (B08), `rfm/srm` (B09); `machines/afm/topologies.py`: `afm/pmsm` (B10),
  `afm/srm` (B11); `machines/tfm/srm.py`: `tfm/srm` (B12). Each adds its options and variables;
  geometry raises `NotSolvableYet` naming its ticket. Backlog tickets B06 to B12 written.
- `analysis/mtpa.py`: golden-section search of the current angle of maximum torque per ampere
  (checked against the analytic MTPA angle of an IPM). `OperatingPoint.current_angle_deg` and
  `phase_currents` exist in `core.types`; the all-phase sweep that uses them comes with T41.
- Tests: `tests/unit/machines/test_skeletons.py` (all nine machines registered; each runs
  variables, dimensions, checks, winding, thermal network and excitation on its default spec;
  geometry of the skeletons raises with the ticket; options validated).
