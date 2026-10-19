# T22: Geometry options of the review paper, and a comparison of stator types

Status: in progress
Depends on: T03, T16, T19, T20, T21, B02

## Why

The user asked (2026-10-13, late evening, then went to bed):

1. Read the paper again (Kaiser and Parspour, "Transverse Flux Machine - A Review", IEEE Access
   2022), scan all figures and the whole text, and add the geometry options that were missed, in
   all places: the parametric geometry generation (`tfm_gmsh_sector.py`), the FeatureScript on
   Onshape and the `.fs` files in the folder.
2. Then run the optimization for the different stator types, all with a Halbach array.
3. Give the result as a grid with the best options for each type.

Problem for all runs: `spec_three_phase.json` (outrunner, three phases in 29 mm, 2 mm legs, 5 mm
slot, 1 mm between phases, 80 mm outer diameter, 20 mm bore, ripple limit 20 %).

## What the paper contains, and where each option stands

Read: the text of sections I.C, II, IV.D, VI.A and VII.D-E in full, and figures 3, 4, 5, 9, 14,
15, 16 and 17 as pictures. Not read as pictures: figures 1, 2 (definitions), 6 to 8 (comparison
charts), 10 to 13 (lamination concepts), 18 (power-factor curve); they hold no geometry option
for the model. Sections III, V, VI.B and VII.A-C were not re-read (comparisons, modelling
methods, control).

| Option in the paper | Where | Onshape feature | Mesher | Optimizer |
|---|---|---|---|---|
| Rotary, inner or outer rotor | II.A | yes | yes | yes |
| Linear machine | II.A | yes (stator) | no | no |
| Double-sided stator | II.A, II.C | no | no | no |
| Rotor: surface magnets | Fig. 3a | yes | yes | yes |
| Rotor: flux concentrating | Fig. 3b | yes | yes | yes |
| Rotor: axially magnetised ring between toothed discs | Fig. 3c | new in the v2 rotor feature | yes (new, `rotor.type = axial`) | accepted by the specification (`rotor_type: axial`), not run |
| Rotor: Halbach array (not in the paper; the user's choice) | - | yes | yes | yes |
| Passive, stator-excited, electrically excited, induction rotors | II.B | no | no | no |
| U-core, U-core with I-bridge | Fig. 4a, b | yes | yes | yes |
| Claw-pole core | Fig. 4d | yes | yes (new) | yes (new) |
| E-core (two coils) | Fig. 4e | yes | geometry only (new, `--stator-only`) | no: see below |
| C-core (rotor between the legs) | Fig. 4c | yes | geometry only (new, `--stator-only`) | no: see below |
| Z-core (rotor between tooth and limb) | Fig. 4f | yes | geometry only (new, `--stator-only`) | no: see below |
| Sheared U-cores with two coils | Fig. 9 | no | no | no |
| Phases side by side along the axis | Fig. 5a | new in the v2 features (number of phases, spacing) | yes (independent phases) | yes |
| Phases around the circumference | Fig. 5b | no | no | no |
| Magnetically coupled phases | Fig. 14 | no | no | no |
| Phase split into segments with several coils | Fig. 15 | no | no | no |
| Tooth span | Fig. 16 | yes | yes | yes (variable) |
| Mixed tooth spans in one machine | VI.A.4 | no | no | no |
| Shift of stator poles | Fig. 17 | new in the v2 stator feature | yes (new, `pole_shift_deg`) | fixed input `machine.pole_shift_el_deg`, not a search variable |
| One-piece toothed ring: continuous U-ring with teeth on both walls (the core drawn in Fig. 17) | Fig. 17 | yes (T24, "TFM stator v2") | yes (T24, `core_type: tr`) | no |
| Skewed or tapered teeth, skewed rotor | VI.A.2 | no | no | no |
| Claw overlap | VI.A.3 | yes (claw tip gap) | yes (new) | yes (variable `claw_tip_gap_mm`) |

## Why E-, C- and Z-cores were not optimized

- **E-core.** One phase needs two outer legs, a middle leg and two slots. With 2 mm iron and
  3 mm slots that is 12 mm. Three phases with 1 mm between them need 38 mm; 29 mm are available.
  The specification check rejects it for that reason. It also needs two coils with opposite
  current, which the solver set-up does not have yet.
- **C-core.** The rotor runs through the opening between the two legs, and the legs sit one pole
  pitch apart. Flux enters the rotor on one axial face and leaves on the other, one pole further.
  That needs a rotor with iron pole pieces (flux concentrating). A Halbach array has one strong
  face, so it cannot serve both legs: "all with a Halbach array" cannot be met for this type.
- **Z-core.** The rotor ring runs between the tooth and the return limb, with an air gap on both
  sides and flux straight through the ring. Again a one-sided Halbach array is the wrong rotor.
- For both C and Z the air gap is not one cylinder, so the present mesh (two domains joined on a
  cylinder in the gap) does not apply. Since every rotor position is meshed anew, a single-domain
  mesh would do; that and the two rotors are the work left (ticket B02).
- The Onshape rotor feature has no rotor for C- and Z-cores either.

## Findings on the way

- Claw pole, first field solution (18 pole pairs, 5 A/mm2): the flux linkage peaks 60 electrical
  degrees away from the aligned position, so the flux of the coil current is about 1.7 times the
  magnet flux. That is the low power factor the paper describes in section VII.
- Ripple needs a finer model than the first pass used. See "First pass" below.
- Pole shift, one test (UI core, 18 pole pairs, 5 A/mm2, 30 electrical degrees): torque 0.221 Nm
  to 0.217 Nm, ripple 12.3 % to 23.9 %, sixth harmonic of the phase torque 0.0060 to 0.0055 Nm.
  No reduction is visible above the mesh noise. The model with a shift covers two pole pairs
  (66 640 elements against 34 212).

- Axially magnetised rotor (Fig. 3c), built and solved once with the claw-pole stator at no load:
  the coil flux is 324 uWb at the aligned position, 324 uWb a quarter period later and 317 uWb
  one pole pitch later. The ring magnet sends a constant flux through the ring coil and the
  rotation changes it by only 2 %, so this pairing gives almost no voltage as parameterised.
  The geometry option exists in all three places; a stator that suits it is not worked out.

## Onshape

- New Feature Studios in the user's document, made by a helper agent: "TFM stator v2"
  (`d334ef1663ba5be0eadd7209`) and "TFM rotor v2" (`e22080f19ed9234f30ca535d`). The original
  studios were not changed. Local sources: `tfm_stator.fs`, `tfm_rotor.fs`; the originals are
  kept as `tfm_stator_v1.fs`, `tfm_rotor_v1.fs`.
- New in v2: "Number of phases" and "Phase spacing" in both features (phase k is moved along +Z;
  the stator ring is also turned by 120 electrical degrees per phase), "Pole shift angle" in the
  stator, and the rotor type "Axially magnetised ring between toothed discs".
- How they were checked: the feature bodies were executed on Onshape through code snippets for
  U-I with 3 phases and pole shift, claw pole with 3 phases, the defaults, E, C and Z with several
  phases, and the rotor in every type with 1 to 3 phases. The studios compile without errors.
  The whole features could not be run through the test tool (it failed with a workspace error),
  and the dialogs were not opened in the Onshape interface.
- A second agent read both new studios back from Onshape and compared them with the local files:
  identical, byte for byte (stator 781 lines, rotor 765 lines).

## Plan and order of work (overnight)

1. U and UI runs start at once from a frozen copy of the code (`runs/types/_code`).
2. Claw-pole core in the mesher, design mapping, checks, parameter sheet; then its run.
3. E-core: two coils with opposite current. It needs 2 legs + middle leg + 2 slots per phase:
   with 2 mm iron and 3 mm slots that is 12 mm per phase, more than the 9 mm available.
4. C-core and Z-core: the rotor runs inside the stator, so the air gap is not one cylinder. They
   need a rotor of their own and a mesh without the cylindrical sliding surface.
5. Options for the features: axially magnetised rotor, pole shift, skew.
6. `tfm_compare.py` writes the grid from the run folders.

## Acceptance criteria

- [ ] Every geometry option of the paper is listed with its status in the three places.
- [ ] Each stator type that the mesher builds has the same geometry as the Onshape feature
      (same parameters, same volumes within 1 %).
- [ ] The optimization ran for every stator type that can be analysed, with a Halbach rotor.
- [ ] A grid gives the best designs of each type, with numbers from direct field solutions.
- [ ] Types that could not be run are listed with the reason.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T22-1 | Claw-pole ring from the mesher: core volume against the closed-form volume of the feature's outline | Within 1 % |
| T22-2 | Claw-pole sector mesh | Meshes; sliding surfaces and periodic planes match (`check_mesh.py`) |
| T22-3 (slow) | Claw-pole design, field solver, no load | Flux linkage alternates sign over half a period; torque finite |
| T22-4 | Design variables and Onshape sheet for a claw-pole specification | Claw fields listed; values equal the mesher parameters |
| T22-5 | `tfm_compare.py` on dry-run folders of two types | Grid with one row per type and the three picks |

## Result

### First pass: fast mesh, 12 rotor positions (2026-10-14, 23:53 to 04:41)

Specifications `specs/three_phase_{ui,u,cp}.json`, population 12, 4 generations, two load levels,
two-stage sweep. Folders `runs/types/{ui,u,cp}`.

| Stator | Designs (analysed) | Within every limit | Run time | Highest torque in the run | Its ripple in the run |
|---|---|---|---|---|---|
| U-core with I-bridge | 287 (285) | 61 | 75 min | 0.619 Nm | 13.7 % |
| U-core | 317 (313) | 21 | 51 min | 0.339 Nm | 11.3 % |
| Claw pole | 305 (301) | 77 | 163 min | 0.716 Nm | 5.8 % |

Verification of the nine picks on the medium mesh (sliding cells as large as the air gap) with 24
positions per half electrical period (`runs/types/grid.md`): torque within 3 % of the run, but
ripple far higher, and no pick within the 20 % limit:

| Stator | Highest torque | Best compromise | Lowest loss |
|---|---|---|---|
| U-core with I-bridge | 0.602 Nm, ripple 21.5 % (run: 13.7 %) | 0.329 Nm, 45.1 % (7.8 %) | 0.116 Nm, 123 % (17.5 %) |
| U-core | 0.329 Nm, 28.9 % (11.3 %) | 0.249 Nm, 40.0 % (11.1 %) | 0.127 Nm, 73.2 % (20.0 %) |
| Claw pole | 0.692 Nm, 71.9 % (5.8 %) | 0.521 Nm, 67.8 % (7.0 %) | 0.215 Nm, 212 % (18.1 %) |

Two causes, both measured:

1. **Too few rotor positions.** The largest harmonic of the three-phase torque is the 12th
   (electrical): 0.06 Nm for the best U-I design, 0.13 to 0.21 Nm for the claw-pole designs. With 12
   positions per half period it lies exactly at the sampling limit and can fall between the
   samples. Taking every second of the 24 verified positions gives 8 % instead of 21 % (U-I) and
   16 % instead of 68 % (claw pole). The optimizer then favours designs whose ripple it cannot see.
2. **Too coarse a mesh.** On the fast mesh (sliding cells 1.5 times the air gap) the torque jumps by
   up to 0.4 Nm between neighbouring positions on a curve of +-1 Nm; solving the same design at 24
   positions on that mesh gives 185 % ripple. On the medium mesh the largest jump is 0.14 Nm and the
   curve is smooth. The medium mesh costs about the same time per position.

Consequence: the first-pass ripple values, the ripple numbers of T19, T20 and T21 (all fast mesh,
12 or fewer positions) and the ParaView and map exports of the first pass understate ripple. Torque,
losses, efficiency and temperatures are not affected (within 3 %).

### Second pass: medium mesh, 24 rotor positions

Specifications `specs/three_phase_{ui,u,cp}_24.json`, seeded from the first pass, same budget.
Folders `runs/types24/`; grid `runs/types24/grid.md`, refreshed after each type.

U-core with I-bridge (06:01 to 08:46): 325 designs, all analysed, 26 within every limit, no
analysis failures. Picks solved again directly (same mesh and positions, own current, no
interpolation), all within every limit:

| Pick | Torque | Ripple | Loss | Efficiency | Pole pairs | Turns | Peak current | Winding |
|---|---|---|---|---|---|---|---|---|
| Highest torque | 0.644 Nm | 15.0 % | 12.08 W | 62.6 % | 25 | 180 | 0.80 A | 93 C |
| Best compromise | 0.534 Nm | 18.0 % | 7.98 W | 67.8 % | 25 | 197 | 0.60 A | 69 C |
| Lowest loss | 0.431 Nm | 17.7 % | 6.90 W | 66.2 % | 21 | 222 | 0.50 A | 63 C |

U-core and claw pole: running in the same way after it (`runs/types24/u.log`, `cp.log`); the
grid is refreshed after each.

### Onshape check of the v2 features (2026-10-14)

The user reported errors in Onshape with the new feature scripts. Checked against the live
document (`TFM stator v2`, `TFM rotor v2` studios hold the same code as `tfm_stator.fs`,
`tfm_rotor.fs`):

- Both files compile (put into a scratch Feature Studio, no errors).
- `test_feature` and `create_geometry` cannot run in this document ("Workspace starting point is
  not a child of the specified parent"), so the feature bodies were run as `test_featurescript`
  lambdas: stator 22 cases (all six cores, linear and rotary defaults, the U, U-I and claw-pole
  picks of both passes, C, E and Z at the 3-phase outrunner size, pole shift, inrunner), rotor
  12 cases (the picks, surface, Halbach 1 row, axial inrunner and outrunner, flux concentrating
  inrunner and outrunner, defaults). All build without error.
- Not covered by that check: the dialog itself (preconditions in the Part Studio). Errors the
  features raise on purpose include the Z core's "The tooth is too wide for this core" when the
  default tooth width (10 mm) is kept on a 5 mm slot, and the claw-pole core with a pole shift.
  The exact message from the user is needed to go further.
