# T42: ParaView export of a radial-flux machine (2D section)

Status: done
Depends on: T18, T29, T41 (first item of B13)

## Why

`python -m emachine export` stops with "not supported yet" for `rfm/pmsm`: the field export reads
the 3D sector of a TFM. The user (2026-10-16) asked to continue the ParaView work of the backlog.

## Scope

The 2D field solution (whole cross-section, all phases, re-meshed per rotor position) is written as
the same set of files as the TFM export, so that the view script, `open_in_paraview.py` and
`--refresh --map` work unchanged:

- `emachine/analysis/section_export.py`: sweeps one full electrical period of the `rfm.section2d`
  geometry with the fields kept (loaded with all phases, and at no load), reads every position and
  extrudes the triangles to wedges over the stack length (z from -L/2 to L/2).
  - `machine.pvd` (solid parts), `air.pvd` (air, gap, shaft), `airgap.pvd` (cylinder in the
    middle of the gap, sampled every 0.5 degrees).
  - Cell data as for the TFM (`region`, `material`, `side`, `B_cell`, `mu_r`, `saturation`,
    `magnetization`, `B_along_magnetization`, `current_density`) plus `phase` (1..m on coil sides,
    0 elsewhere). Point data `B`, `B_magnitude`, `B_radial`, `B_tangential` and `A_z` (vector
    potential: its contour lines are the flux lines).
  - `core_loss.vtu`, `full_ring.vtu` (whole section at the step of highest torque) and the tables.
- `full_motor.vtu`: the section already holds every phase (`ring_has_all_phases` in
  summary.json), so it is written once, with its `phase` array, instead of one copy per phase.
- `vtk.py`: triangle and wedge cells.
- `cli/export.py`: chooses the export by the geometry kind of the machine; summary and charts
  without the TFM legs; columns that do not exist (phase torque of an all-phase solution) are left
  out of `waveforms.csv`.
- View script: generic material labels, top view and flux lines (contours of `A_z`) for a
  section, torque chart with the columns present.

## Acceptance criteria

- [x] Wedges: positive volume as ParaView computes it (base triangle counter-clockwise seen from
      +z), total volume = area x stack length.
- [x] Air-gap sampling of a known uniform field returns its radial and tangential components.
- [x] `full_motor.vtu` of a ring with all phases: one copy, `phase` array kept.
- [x] Export of the reference design (`specs/rfm_spm_12s10p*.json`): every file valid, no air in
      `machine.pvd`, only air in `air.pvd`; 2 x positions steps.
- [x] Machine torque of the export equals the sweep of the evaluation at the same positions
      within 0.5 %.
- [x] Magnetisation magnitude = Br / (mu0 mu_r) within 0.1 %; magnets alternate in direction.
- [x] Mean radial air-gap flux density < 2 % of its peak.
- [x] `core_loss.vtu` total = stator iron loss of all phases (loss model) within 1 %.
- [x] With ParaView 6.2: five pictures, five tabs, no failure, no warning; the pictures looked at.
- [x] TFM export unchanged (T18, T29 tests pass).

## Test cases

| ID | Test | Expected |
|---|---|---|
| T42-1 | Extrude two triangles of opposite orientation, read back | 2 wedges, volumes positive, sum = area x L |
| T42-2 | Gap sampling of B = (0.3, 0.4) T on a triangulated annulus | B_r, B_t at every angle within 1e-9 |
| T42-3 | `full_motor` with `ring_has_all_phases` | cells unchanged, `phase` kept; TFM ring still 3 copies |
| T42-4 | `waveform_table` with no phase torque | no `phase_torque_Nm` column; view inputs complete without it |
| T42-5 (slow) | Export of the reference design, 6 positions per half period | files, counts, torque, magnets, gap, core loss as above |
| T42-6 (slow) | pvpython on that export, with the map of `runs/rfm_spm_12s10p/map` | 5 pictures, 5 tabs, no failure |

## Result

2026-10-16. `emachine/analysis/section_export.py` (new), `cli/export.py` (dispatch by geometry kind,
section summary and chart), `io/vtk.py` (triangle, wedge), `io/paraview_files.py` (ring with all
phases), `io/paraview_views.py` (section views, text on a light box), `solvers/elmer/section2d.py`
(`body_ids` shared by the case writer and the export). Tests: `tests/unit/analysis/test_section_export.py`.

Reference export (`runs/rfm_spm_12s10p/paraview`, with the map; 12 positions per half period, 24
steps, 11 583 triangles, 14 s, 58 MB; pictures in `views/`):

- Mean torque 2.054 N m (as T41), ripple 1.2 %, cogging 0.020 N m peak to peak; 19 turns, flux
  linkage 33.5 mWb peak (1.76 mWb per turn), induced voltage 26.4 V peak at 1500 rpm
  (= omega_e psi); magnet working point 0.30 T or more; 59 C winding and magnet.
- T42-5 (6 positions): torque equal to the evaluation sweep within 0.5 %; magnetisation =
  Br / (mu0 mu_r) within 0.1 %, both directions present; mean radial gap flux density under 2 % of
  its peak; core loss file total = 3 x stator iron loss per phase within 1 %.
- T42-6: pvpython 6.2 renders the five pictures and builds five tabs with no failure and no
  warning; ParaView's own cell volumes of `full_motor.vtu` are all positive and add up to the same
  total as the test. Pictures looked at: full motor cut open; cross-section from the top with
  |B| per material and the flux lines; mesh close-up at a slot opening; torque and cogging over
  the period; efficiency map with limits (best 88.3 %).

Found on the way:

- The wedge order: the vtkWedge documentation says the base normal points away from the top
  triangle, but vtkCellSizeFilter and vtkMeshQuality give that order a negative volume. The first
  export had every volume negative (the pictures looked right, so only ParaView's volume showed
  it). Bases now run counter-clockwise seen from the top; T42-6 checks the volumes in ParaView.
- `full_motor.vtu` is the step of highest torque, which has its own mesh (the mesh is made again
  at every position): the test compared it with step 0 and was corrected.
- Text labels of all views now sit on a light box (`ShowBorder` "Always"; the background alone
  is not drawn in 6.2), so they stay readable over the model. This also changes the TFM pictures;
  the material label "Somaloy stator core" is now "Stator core" (the radial machine may use
  laminations).

TFM export unchanged: T18, T19, T28 and T29 tests pass with `EMACHINE_SLOW=1` (33 tests, 186 s),
including the render of the user's export (T29-6).

Full slow suite after T42: 333 tests pass (1 skipped) in 1124 s.
