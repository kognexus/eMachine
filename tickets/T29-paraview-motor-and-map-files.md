# T29: Whole motor and efficiency map as files ParaView opens

Status: done
Depends on: T17, T18, T28

## Why

The user (2026-10-15) opened the T28 export in ParaView and found no efficiency map and no full
motor. The export held only the sector time series and the ring of one phase; the whole motor (all
phases) and the map were assembled only by the picture script `tfm_paraview_views.py`, from CSV
files in another folder. In the GUI they did not exist.

## Work

1. `tfm/paraviewfiles.py` (numpy only):
   - `full_motor.vtu`: `full_ring.vtu` repeated per phase, phase k moved k x phase pitch along Z, its
     stator (core, copper) and the flux density on it turned by k x phase turn; cell array `phase`.
   - `efficiency_map.vtu`: the map grid as quadrilaterals, x speed in 1000 rpm, y torque in N m, all
     columns as point data, `efficiency_percent`, cells `within_drive_limits` and `continuous`.
   - `efficiency_limits.vtu`: drive and continuous limit as line cells (`curve` 0 and 1).
2. `tfm_paraview.py` writes `full_motor.vtu` after every export; `--map` adds the map files to the
   export; `--refresh` rewrites these files of an existing export without solving.
3. `tfm_map.py` writes the two map VTK files into its own folder.
4. `open_in_paraview.py` of an export runs the view script (copied next to it) with `--interactive`:
   the five views as tabs of the GUI. The view script reads `full_motor.vtu` and `efficiency_map.vtu`
   instead of building them in ParaView.
5. `vtkio`: line cells.

## Acceptance criteria

- [x] `full_motor.vtu`: phases at the right axial place, stator turned, rotor not, vectors turned with the stator.
- [x] `efficiency_map.vtu`: regular grid, counter-clockwise quads, cells outside the drive limit marked.
- [x] Refresh of an existing export writes everything the view script reads; open script compiles.
- [x] User's export refreshed.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T29-1 | Full motor from a two-cell ring, 3 phases | z shift 9.1 mm per phase, stator 5 deg per phase, rotor 0, B turned on the stator only |
| T29-2 | Map of a 3 x 3 grid | 4 quads, positive area, the cell at the outside corner marked, best efficiency, 2 x 2 limit lines |
| T29-3 | `--refresh` on a small export | `check_inputs` empty; open script compiles, has `--interactive` and the absolute path |
| T29-4 | View script | Five tab titles, reads `full_motor.vtu` and `efficiency_map.vtu` |
| T29-5 | User's export | Inputs complete, `phase` array present |
| T29-6 (slow) | pvpython 6.2: pictures and tabs of the user's export | 5 pictures, 5 tabs, no failure, no warning |

## Result

2026-10-15. `runs/user_tr48/paraview` refreshed in 4.5 s: `full_motor.vtu` 1 612 728 tetrahedra (3 x
537 576), phases at z = -4.5..4.5, 4.6..13.6, 13.7..22.7 mm, stator turned 0, 5, 10 deg, rotor not;
stator and rotor share no points. `efficiency_map.vtu`: 61 x 61 points, 3600 cells, 2764 within the
drive limits, best 91.2 % at 3965 rpm and 0.748 Nm (as `map.md`). All fast tests pass (221, 32
skipped); T17 and T18 slow tests pass.

Then the user ran `open_in_paraview.py` in ParaView 6.2 (now installed on this Mac): views 1, 2, 3
and 5 failed. Fixed and checked by rendering with the local pvpython and looking at each picture:

- `ColorBy(display, None)` raises "invalid association string 'NONE'" in 6.2: solid colours are set
  with `ColorArrayName = ["POINTS", ""]`.
- Materials were taken from the range of the `material` array (2..6), which includes rotor iron (5)
  that an outrunner does not have; the empty selection had no field array. Now every material is
  kept only when its selection has cells.
- Pictures: clean (not crinkle) cut of the full motor; colour bars with dark text, beside the
  model; number formats `{:.2f}` from ParaView 6.1 on (`%.2f` before); efficiency map cut along the
  drive limit (`drive_margin_Nm` = 0) instead of along whole cells, torque axis in N m with even ticks
  (the display stretches the torque axis; custom tick positions are given in stretched units), limit
  lines ending where the limit torque is zero.

T29-6 (slow, needs ParaView): renders the five pictures of the user's export with no failure and no
warning, and `open_in_paraview.py` builds five tabs (also without `__file__`). 222 fast tests pass,
T29 slow tests pass.

Second report of the user (same errors): ParaView had kept the first, broken copy of
`tfm_paraview_views` in its Python shell, and `open_in_paraview.py` imported that copy again (the
traceback showed old code with the new file's source lines). `open_in_paraview.py` now drops the
module from `sys.modules` before the import. Checked with pvpython: a stale module in `sys.modules`
and two runs in one session both build all five tabs.
