# T52: eMachine dialog and sheet in the dimensions of the catalogue

Status: done
Depends on: T49, T50, T51 (dialog only for the machines built: AFM stays an error)

## Why

The dialog of the eMachine feature (T47) shows the ratios the user found weird. It must take the
design variables of `docs/parameters.md`: slot height, slot width, yoke height in mm, arcs in
electrical degrees, magnet length, barrier width, SRM pole arcs and pole height, claw tip.

## Scope

- `emachine_main.fs`: fields, defaults (the converted reference: slot 12 x 7.069, yoke 8), the
  derivation `emRfmDimensions` (bore from the outer diameter), checks with field names; rotors use
  the new fields. Rebuild `emachine_design.fs`.
- `cad/sheet.py`: rows in the new names; derived checks (bore, tooth width at the bore, stator pole
  arc of the SRM).
- Tests: the derivation of the feature equals `derive` for the reference and a distributed design.

## Acceptance criteria

- [x] No ratio field left in the dialog (test on the source).
- [x] Defaults equal the converted reference design; derived bore 30 mm.
- [x] Compile check in Onshape (if the connection is available).

## Result

2026-10-17. Dialog: "Yoke height" and "Slot height" for every machine; RFM "Slot width
(parallel-sided slot)"; "Tooth arc (electrical, 180: whole pole pitch)" (TFM); "Magnet arc
(electrical, 180: whole pole)"; "Claw tip height"; "Magnet length (each bar of the V)"; "Barrier
width"; "Magnet width (across the q axis)"; "Rotor pole arc (mechanical)", "Rotor pole height".
Gone: bore, tooth and slot depth ratios, tooth span, magnet arc ratio, V width ratio, insulation
ratio, magnet fill, rotor pole arc ratio, "Minimum iron thickness (claw tip)". `emRfmDimensions`:
bore = outer radius - yoke - slot height, tooth at the bore, with errors naming the fields; the
barrier rotor stops when the barrier width reaches the barrier pitch. Defaults: the reference
(slot 12 x 7.07, yoke 8, magnet arc 153 el. deg). `cad/sheet.py` prints the new fields and, to
check, bore, rotor diameter, tooth width at the bore (and the stator pole arc of an SRM).

Onshape: the main part (with stubs of the copied TFM functions, as for T47) compiles in the scratch
studio. The full `emachine_design.fs` (rebuilt, 2482 lines) has to be pasted into the studio
"eMachine" again. Tests: `test_t52_no_ratio_fields`, the reference defaults and the derivation
terms (`tests/unit/cad/test_featurescript.py`).
