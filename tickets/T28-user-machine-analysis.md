# T28: Full analysis and ParaView views of the user's 48-pole toothed-ring outrunner

Status: done
Depends on: T17, T18, T23, T24, T26, T27

## Why

The user (2026-10-15) asked to run geometry -> Gmsh -> Elmer -> ParaView on exactly the machine of
their two Onshape dialogs, over speed and current within the drive limits (bus 48 V, 15 A peak), and
to see in ParaView:

1. the full motor in 3D;
2. the motor segment in 3D with the magnetic field as colour, materials (Somaloy, copper, magnet)
   distinct: |B| with a colour map of its own per material (user's choice);
3. the Gmsh mesh;
4. torque against electrical angle;
5. torque / speed / efficiency map.

Decisions of the user on the way: rotor with 48 poles (dialog had 32, stator 24 pole pairs);
staggered teeth (T27) to keep one magnet row; limits 48 V and 15 A peak.

## Machine

| | Value |
|---|---|
| Stator | toothed ring (T24), inner stator, air-gap radius 35 mm, 24 pole pairs, tooth span 0.8, legs 2 mm, slot 5 x 10 mm, yoke 5 mm, ring tooth height 8 mm, arched valleys (T26), staggered teeth (T27), coil 8 x 3 mm (clearance 1 mm), 3 phases 0.1 mm apart |
| Rotor | outrunner, Halbach, 2 segments per pole, 48 poles, magnets 2 mm, inner diameter 70.6 mm (air gap 0.3 mm), outer diameter 80 mm, one magnet row |
| Stack | 27.2 mm = 3 x 9 mm + 2 x 0.1 mm (the CAD rotor is 27.3 mm) |
| Winding | strip coil (T23), copper fill 0.85 |
| Materials | the defaults of the specification (Somaloy-like SMC with saturation, NdFeB 1.3 T); to be replaced by data sheets |

## Work

1. `tr` in the specification and design mapping: variable `ring_tooth_height_mm`, machine options
   `ring_arched_valleys` and `ring_staggered_teeth`, one magnet row for staggered teeth, two rows
   with alternate polarity otherwise, feasibility checks for the room between teeth.
2. Specification `specs/user_tr48.json` and design `specs/user_tr48_design.json`.
3. Runs: field export over one electrical period at the rated point (torque against angle, field,
   mesh), and the efficiency map.
4. `tfm_paraview_views.py`: a pvpython script that renders the five views as PNG files from an
   export folder (ParaView is not installed on this computer: the script is checked against the
   files it reads, not run).

## Acceptance criteria

- [x] The specification accepts `tr` with both options; the mapping reproduces the user's dialog values
      exactly (parameter sheet), and the feasibility checks pass for the user's machine.
- [x] Torque against electrical angle from direct field solutions, 24 positions per half period.
- [x] Efficiency map within 48 V and 15 A peak, with the operating limits and the best-efficiency region.
- [x] Export folder with all data the five views need, and the view script.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T28-1 | Specification and design of the user's machine | Loads; parameters equal the dialog values; feasible |
| T28-2 | Wrong options (`ring_*` on another stator type) | Specification error |
| T28-3 | View script against an export folder | Every file and array it reads exists |

## Result

2026-10-15. Runs in `runs/user_tr48/`: `map/` (efficiency map, 1239 s) and `paraview/` (export, 839 s,
3 sectors, 121 126 elements per sector). 22 turns per coil (strip 8 x 3 mm split into turns as the
optimizer does), medium fidelity, 24 positions per half period.

Efficiency map, 48 V and 15 A peak (`map/map.md`):

| Quantity | Value |
|---|---|
| Peak torque (15 A, short time) | 1.247 Nm up to the corner speed of 3172 rpm |
| Continuous torque at standstill | 0.949 Nm |
| No-load speed at 48 V | 4806 rpm (no field weakening) |
| Highest efficiency | 91.2 % at 3965 rpm and 0.748 Nm (310.6 W) |
| Highest continuous / short-time power | 222.6 W at 3613 rpm / 418.9 W at 3260 rpm |
| Best region | 2600 to 3500 rpm, 0.6 to 0.8 Nm: about 90 % |
| Spec point (300 rpm, 13.1 A) | 1.094 Nm, 54.5 %: copper loss dominates at low speed |

Torque is linear in current: 3.84 to 3.78 Nm per 1000 ampere-turns from 3 to 15 A; the core stays at
1.29 T on 95 % of its volume (2.3 % of the core above 80 % of saturation).

Torque against electrical angle at 13.1 A (`paraview/waveforms.csv`, 48 positions over one electrical
period): mean 1.0955 Nm, 0.794 to 1.374 Nm, ripple 53 % peak to peak. Cogging alone is 0.583 Nm peak
to peak and the ripple is the 6th harmonic (0.270 Nm, 24.7 % of the mean): the cogging of the three
phases adds up. Pole shift or a phase offset of a fraction of a tooth pitch would be the next study.

At the rated 10 A/mm2 the winding reaches 175.5 C at standstill-like cooling (300 rpm), above the
120 C limit: 1.09 Nm is a short-time point; the continuous limit is 0.95 Nm at low speed. Magnets: lowest
working point -0.12 T in 1.9 % of the volume below 0.3 T, none below 0 T.

T28-3: `tfm_paraview_views.py --check` finds every input; the VTU array reader scans the whole file
(the arrays are inline, beyond the first 200 kB). The pictures themselves are rendered with pvpython
with pvpython; ParaView 6.2 was installed later and the views are now tested with it (T29):
pictures in `runs/user_tr48/views/`. All fast tests pass (216, 32 skipped).
