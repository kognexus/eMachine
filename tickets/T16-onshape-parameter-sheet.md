# T16: Parameter sheet for the Onshape model

Status: done
Depends on: T03, T13

## Why

The optimizer finds a design as a set of numbers. The CAD model is built by two Onshape features,
"TFM stator" and "TFM rotor". The user needs the optimized values in the words of those two
dialogs, so they can be typed in without translation.

## Scope

- `tfm/onshape.py` turns a parameter file into a sheet with one row per dialog field, using the
  exact field names of `tfm_stator.fs` and `tfm_rotor.fs`, in dialog order, with units.
- Only fields that the dialog shows for the chosen core structure, configuration and rotor type
  are listed.
- The sheet also gives: the winding (turns, copper area per turn, round-wire diameter, currents),
  the placement of the phases for a three-phase machine (axial pitch and angular shift), and
  cross-checks (air gap, overall diameter, overall length).
- Values are printed with enough digits that the CAD model equals the analysed model (0.001 mm).
- A value outside the range the dialog accepts is flagged.
- `tfm_onshape.py --params FILE` prints the sheet for any parameter file.
- `tfm_optimize.py` writes `designs/<pick>.onshape.md` for every pick, adds the sheets to the
  report and prints the sheet of the best compromise at the end of the run.

## Acceptance criteria

- [x] Every field name in the sheet exists as a `"Name"` annotation in the matching `.fs` file.
- [x] Typing the sheet values into the features reproduces the analysed geometry: the sheet
      values equal the values in the parameter file used by the mesher.
- [x] Fields that the dialog hides are not listed.
- [x] The optimizer prints the sheet of the best compromise and writes one per pick.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T16-1 | Sheet of the reference design (outrunner, UI, Halbach) | Every label found in `tfm_stator.fs` or `tfm_rotor.fs` |
| T16-2 | Same sheet, values | Equal to the mesher parameters within 0.0005 mm |
| T16-3 | Inrunner, U-core, surface magnets | Lists "Outer diameter (air gap)", "Shaft diameter", "Magnet arc / pole pitch"; no I-bridge and no "Segments per pole" rows |
| T16-4 | Flux-concentrating rotor | Lists "Magnet radial height" and "Magnet width", not "Magnet thickness" |
| T16-5 | Three-phase specification | Placement gives axial pitch = phase width + spacing and angular shift = 120 / pole pairs degrees |
| T16-6 | Tooth span 1.2 in a hand-made parameter file | The row is flagged as outside the dialog range |
| T16-7 | Dry-run optimization | `designs/best_compromise.onshape.md` exists, the report has a section "Onshape parameters", the sheet is in the command output |
| T16-8 | `tfm_onshape.py --params` on a pick file | Exit code 0 and the same sheet |
| T16-9 (slow) | Pick file with the new `machine` and `summary` sections given to the mesher | Accepted: the extra sections are ignored |

## Result

Completed 2026-10-13.

- `tfm/onshape.py` builds the sheet; `tfm_onshape.py --params FILE` prints it for any parameter
  file (`--markdown` for tables). Exit code 1 when a value is outside the range a dialog accepts.
- `tfm_optimize.py` writes `designs/<pick>.onshape.md` for every pick, adds a section
  "Onshape parameters" to the report and prints the sheet of the best compromise at the end.
- Pick files gained two sections, `machine` (the macro inputs) and `summary` (torque, loss,
  turns, wire area, currents, voltage, temperatures). The mesher ignores both.
- The sheet has four parts: the "TFM stator" dialog, the "TFM rotor" dialog, checks on the
  finished model (air gap, overall diameters, lengths, phase placement for three phases) and the
  winding (turns, copper area per turn, equivalent round-wire diameter, currents, resistance).
- Tests in `tests/test_t16_onshape.py`: T16-1 to T16-8 pass; T16-9 passes with `TFM_SLOW=1`.
- Field names are read from the `"Name"` annotations of the two `.fs` files in the test, so a
  renamed dialog field makes T16-1 fail.
- Not done: writing the values into the Onshape document automatically. The sheet is typed in by hand.
