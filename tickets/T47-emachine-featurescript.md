# T47: Onshape feature "eMachine": flux path, principle and rotor layout to choose

Status: done (two criteria partly, see Result)
Depends on: T43 to T46, T16, T29

## Why

The user (2026-10-16): "create feature script with which I could choose flux path, torque
principle, rotor layout so that we could directly design the output motor in the onshape". Today
Onshape has the TFM features only ("TFM stator", "TFM rotor", "TFM UI32 machine"), and the radial
flux machine optimized in T41 has no CAD at all (B13).

## Scope

1. One Feature Studio, `emachine_design.fs`, with one feature "eMachine":
   - choices with the names of `docs/naming.md`: flux path, torque principle, rotor layout,
     stator layout (TFM), rotor placement, winding span and layers;
   - the dimensions of the geometry parameter file a design produces (as the parameter sheet of
     T16), so that a design of the optimizer is typed in, or pasted from the sheet;
   - every cell of the machine matrix (T45): built, or stopped with an error that names the
     ticket (Vernier B15, RAFM B14, AFM B10/B11, TFM SRM B12; RFM outer rotor not built).
2. Built:
   - **TFM PMSM**: the existing stator and rotor code (all stators, rotors halbach, surface,
     spoke, axial_ring), copied into the studio as functions by the build script (as for UI32).
   - **RFM**, inner rotor, 2D section extruded over the stack (z from -L/2 to L/2), the same
     geometry as the Gmsh section of `machines/rfm/section.py`: slotted stator (parallel-sided slots),
     coil sides in the slot halves coloured by phase (slot star of `machines/winding_layout.py`,
     double or single layer), shaft, and the rotor of the layout:
     - `surface` (PMSM): magnets on the rotor yoke, rotor turned to the d axis of phase 1;
     - `interior` (PMSM): one V of two magnets per pole, iron bridge to the surface;
     - `flux_barrier`, `flux_barrier_pm` (SynRM): circular barriers around the q axis, ribs at the
       surface; magnets in the middle of each barrier for `flux_barrier_pm`;
     - `salient` (SRM): rotor teeth.
     Interior, flux barrier and salient rotors are CAD only until B06 to B09 analyse them.
3. Build script `python -m emachine featurescript` (`--check`): writes the studio from
   `emachine/cad/featurescript/emachine_main.fs` and the TFM studios.
4. `python -m emachine onshape` for any design: the field values of the eMachine dialog.

## Acceptance criteria

- [ ] The studio compiles in Onshape (FeatureScript 3095) with no error and no warning. Partly:
      the main part compiles (with stubs of the copied TFM code); the whole studio is confirmed
      when it is pasted into the Feature Studio "eMachine".
- [x] RFM reference design (`specs/rfm_spm_12s10p*`): parts and volumes in Onshape equal the
      areas of the Gmsh section times the stack length within 0.5 % (stator, coils, magnets, rotor
      core); coil sides carry the phases of the slot star.
- [ ] TFM reference (UI32 design): same parts and volumes as the "TFM UI32 machine" feature.
      Partly: the rotor is identical (387 bodies, same volumes); the stator fields are checked by
      name only.
- [x] Each RFM rotor layout builds with its default values; every unsupported cell gives its
      ticket in the error.
- [x] The enums use the names of `docs/naming.md` (test compares them with the Python tables).
- [x] `onshape` writes the dialog values of the RFM and the TFM reference designs; the build
      check passes.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T47-1 | Enums of the studio against `options.ROTORS`, `STATOR_CODES`, `matrix` | same names (upper case) |
| T47-2 | Build script `--check` | studio up to date; contains the main feature and `tfmStator`, `tfmInrunnerRotor` |
| T47-3 | `onshape` on the RFM reference | slots 12, pole pairs 5, bore radius, slot width and depth, magnet as `derive` |
| T47-4 (Onshape) | Feature on the RFM reference values | volumes as the Gmsh areas x L within 0.5 %; 24 coil sides, 8 per phase |
| T47-5 (Onshape) | Each rotor layout, each unsupported cell | builds / error with the ticket |
| T47-6 (Onshape) | TFM UI32 values | same volumes as the UI32 feature |

## Result

2026-10-16. `emachine/cad/featurescript/emachine_main.fs` (hand-written: the feature, its enums,
the matrix check, the RFM cross-section, the slot star and the TFM mapping), `emachine/cad/build.py`
(`python -m emachine featurescript`, `--check`) writes `emachine_design.fs` (2414 lines, 109 kB:
the main part plus the TFM stator and rotor code as functions), `emachine/cad/sheet.py` and
`python -m emachine onshape --spec --design` (or `--run --pick`) for the dialog values.

Checked in Onshape (document of the TFM features; `test_feature` still fails there with "Workspace
starting point is not a child of the specified parent", so the code ran through `test_featurescript`
harnesses generated from the studio, and compiled through `put_featurescript`):

- Compile: the main part with stubs of the copied TFM code compiles (no error); the copied TFM code
  is the code of the "TFM UI32 design" studio, which compiles in the same document.
- RFM reference (defaults of the feature = `specs/rfm_spm_12s10p*`), volumes in mm3 against the
  Gmsh section areas x 40 mm: stator core 135 649.12 / 135 649.22, coil sides 40 782.72 /
  40 782.63 (24 sides, 8 per phase: A+, A-, B+, ...), magnets 17 816.60 / 17 816.60, rotor core
  74 353.96 / 74 353.96, shaft 12 566.37 / 12 566.37: all within 1e-5.
- Interior V magnets (47 bodies), flux barriers (p = 2 and p = 5), flux barriers with magnets (12
  magnets + core), salient SRM rotor, single-layer winding (24 half-slot sides): all build.
- Vernier, AFM, RAFM, TFM SRM, RFM outer rotor, RFM PMSM with a Halbach rotor: each stops with its
  message and ticket.
- TFM: the eMachine feature with the UI32 values and the direct call of the TFM rotor function as
  the UI32 feature makes it give the same 387 bodies with identical volumes per part; an inner-rotor
  surface TFM builds. The stator half of the TFM was not run through the harness (too large to
  retype); its field names are checked by a test against the defaults of the TFM features, and
  every field the UI32 feature passes is passed by the eMachine feature.

Not done: the studio is not pasted into the Onshape document by the tool. An empty Feature Studio
"eMachine" (element 92990404717d28f82b7fe18c) was created in the document with a note; pasting
`emachine_design.fs` into it is one copy and paste (retyping 109 kB through the API could
introduce silent numeric typos that still compile). The precondition uses only == and != (the
dialog analysis of Onshape rejects < and >), which the build test checks.

Tests (`tests/unit/cad/test_featurescript.py`, 7): enums against the naming tables and
`docs/naming.md`; dialog texts of the sheet against the enum annotations; every field of the sheet
exists in the dialog (RFM all layouts, TFM user design); TFM keys against the TFM defaults; build up
to date, one feature, no < or > in the precondition; RFM reference values and the defaults of the
feature equal `derive`; the command's Markdown output.


Full slow suite after T43 to T47: 366 tests pass (1 skipped) in 1374 s.

### Revision 2026-10-17: inputs instead of dimensions

The user pasted the studio and found that most machines did not build. Cause: the dialog asked for
the dimensions of stator and rotor separately (air-gap radius, rotor diameter at the gap, shaft or
outer diameter, bore radius, slot width, ...), so most combinations did not fit together; even the
defaults failed when the flux path was switched to TFM (an 80 mm "shaft" inside a 70 mm rotor).

Now the dialog takes what the specification and the design variables take (outer diameter, total
stack, air gap, bore diameter, pole pairs; RFM: slots, bore, tooth and slot depth ratios, yoke; TFM:
tooth span, leg width, slot height, yoke, rotor iron, bridge, ring tooth, claw, coil clearance and
margin, magnet), and `emRfmDimensions` / `emTfmDimensions` derive the rest with the formulas of
`SlottedMachine.derive` and `design.derived` / `to_parameters`, with checks that name the fields to
change ("The stator reaches into the bore", "Slot depth and yoke reach beyond the outer diameter",
...). `python -m emachine onshape` prints these inputs and, under "To check on the finished
model", the derived dimensions.

Checked in Onshape: the derived dimensions equal Python for the user's 48-pole toothed-ring outer
rotor (air-gap radius 35, rotor gap diameter 70.6, slot 5, coil 8, phase width 9 mm, one magnet
row) and the UI design of `specs/three_phase_ui.json` (30.25, 61.5, 5, 3.5, 9 mm, two rows); the
claw-pole midpoint design stops with "The stator reaches into the bore", as Python rejects it
(`bore_clearance`); the defaults switched to TFM (inner and outer rotor) give consistent
dimensions. RFM reference, interior, SRM and a 150 mm 24-slot 8-pole distributed machine build
from the inputs; the stator core is now 135 649.22 mm3, equal to the Gmsh value. The dialog part
compiles (scratch studio).
