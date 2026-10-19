# T27: Staggered teeth on the toothed ring

Status: done
Depends on: T24, T26

## Why

The user's machine (2026-10-15): toothed ring, outrunner, 48-pole Halbach rotor with one magnet row
across each phase. With the teeth of both walls aligned, both walls face the same pole at every
instant and the coil links no flux. Measured (no load, 24 pole pairs, arched valleys, one turn):
0.03 / 0.01 / 0.03 uWb at 0, half and one pole pitch, against 67.2 / -0.09 / -67.2 uWb with two
magnet rows of opposite polarity. The Halbach segments are magnetised radially or tangentially,
with no axial component, so the machine is mirror symmetric about the coil plane.

The user chose to keep one magnet row and to stagger the stator teeth instead: the teeth of the
back wall sit one pole pitch after those of the front wall, so the two walls of a phase face
opposite poles and the flux closes around the coil (front tooth, yoke, back tooth, rotor).

## Geometry

Option `ring_staggered_teeth` (mesher) / "Staggered teeth" (Onshape), off by default.

- Front wall (-axial side): teeth at pole positions 2k, as before. Back wall (+axial side): teeth at
  2k + 1. Every second tooth of each wall carries the pole shift, as before.
- Straight-cut and arched valleys both work; each wall gets its own valleys, cut only through that
  wall (the cutter stops at the coil mid-plane).
- Volume: the same as without stagger (each wall keeps the same teeth and valleys).
- Rotor for the analysis: one magnet row over the whole phase (as for the claw pole).

## Acceptance criteria

- [x] Mesher: staggered core has the volume of the aligned core (straight-cut and arched, both
      stator styles), and the back-wall tooth sits at one pole pitch (point-in-solid check).
- [x] Sector mesh of the user's machine passes the mesh checks.
- [x] No load, user's machine with one magnet row: coil flux changes sign over one pole pitch and is
      far from zero.
- [x] Onshape: same volumes, and the back-wall teeth one pole pitch after the front-wall teeth.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T27-1 (slow) | Volume staggered vs aligned, straight and arched, inner and outer stator | Equal within 0.01 % |
| T27-2 (slow) | Point in the back-wall tooth at one pole pitch, and not at zero | Inside / outside as expected, front wall the other way round |
| T27-3 (slow) | Sector mesh, user's machine | `check_mesh.py` passes; node count of the file matches |
| T27-4 (slow) | No-load flux, one-row Halbach | Sign change, magnitude > 20 uWb |
| T27-5 | FeatureScript and sheet | Field present, `==` only, sheet row |

## Result

2026-10-15, user's machine (one phase: air-gap radius 35 mm, 24 pole pairs, tooth span 0.8, 2 mm walls,
5 mm slot, 10 mm slot height, 5 mm yoke, 8 mm tooth height):

| Core volume, mm3 | Mesher aligned | Mesher staggered | Onshape staggered |
|---|---|---|---|
| Inner stator, straight-cut | 10 485.16 | 10 485.16 | 10 485.165 |
| Inner stator, arched | 10 014.33 | 10 014.33 | 10 014.326 |
| Outer stator, straight-cut | 18 457.90 | 18 457.90 | - |
| Outer stator, arched | 19 558.32 | 19 558.32 | 19 558.317 |

Onshape: 3 phases, arched, staggered: 30 042.977 = 3 x one phase. Probes 2 mm into the stator in the
middle of each wall: front wall iron at 0 and air at one pole pitch, back wall the other way round,
in the mesher and on Onshape.

No load, 48-pole Halbach rotor with one magnet row over the phase, one turn: coil flux 115.25, -0.08,
-115.17 uWb at 0, half and one pole pitch (aligned teeth: 0.03, 0.01, 0.03 uWb; aligned with two rows
of opposite polarity: 67.2, -0.09, -67.2 uWb).

Uploaded to "TFM stator v2" (compiles). Tests: `tests/test_t27_staggered_teeth.py`, all pass; T24 and
T26 slow tests pass again with the per-wall valley cutters.
