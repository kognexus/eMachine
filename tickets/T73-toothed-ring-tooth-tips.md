# T73: Tooth tips on the toothed ring, reaching over the coil slot

Status: done (code and tests); measured effect in T74
Depends on: T24, T26, T27, T70

## Why

Found in the baseline field of the study (T74), not on the user's list: the teeth of the gear stand
only on the 2 mm side walls and collect flux from 2 of the 9 mm of magnet row. With staggered teeth,
the space over the slot at a front tooth is free, because the back wall has its valley there. A tooth
can therefore reach over the slot (a tip, or claw) without meeting the other wall. The tips of the
two walls interleave one pole pitch apart, as in a claw-pole stator, but the ring and its valleys
stay. The claw-pole stator gave the most torque in T22.

This also covers the user's item 4 ("cutouts or holes to take the flux path"). The arched valleys
(T26) are the cutouts. The tips decide where the flux enters.

## Geometry

Option `machine.ring_tooth_tips` (mesher: `stator.ring_tip_overhang`, `stator.ring_tip_height`, 0 = off).

- Each tooth gets a block as wide as the tooth, from the air gap down to the tip height, reaching
  `ring_tip_overhang` from its wall over the slot (and half a leg into its own wall, so it fuses).
  Its top is trimmed to the air-gap cylinder. The tips are added after the valleys are cut, so the
  valley cutters of one wall do not cut the tips of the other.
- The coil sits below the tips: coil height = slot height - clearance - margin - tip height.
- Checks: staggered teeth: overhang <= slot width - core gap, and neighbouring tips (one pole pitch
  apart) at least the core gap apart. Aligned teeth: two overhangs <= slot width - core gap. Tip
  height <= ring tooth height - 0.5 mm.
- The Onshape features do not have the tips yet (the `onshape-fs` connection needs re-authorisation).

## Acceptance criteria

- [x] Variables `ring_tip_overhang_mm` and `ring_tip_height_mm` only with the option; coil height
      and pole-face area follow; values map back from the parameters.
- [x] Checks reject a tip reaching the opposite wall, a tip as thick as the tooth, and colliding tips.
- [x] Gmsh: one core solid; added volume equals 2 p x overhang x tip cross-section (closed form)
      within 0.1 %; front tip present at angle 0, no back tip there.
- [x] Sector mesh passes the pipeline's node check (no stray construction entities).

## Test cases

| ID | Test | Expected |
|---|---|---|
| T73-1 | Variables, coil height, pole-face area, round trip | Present; -1.5 mm; x (2 + 3.5) / 2; equal |
| T73-2 | Checks: good tips; overhang 4.9 mm and height 8 mm; tooth arc 171 deg | Pass; violated; tip gap violated |
| T73-3 | Option on a U-I core | Error |
| T73-4 (slow) | Stator volume with and without tips, probes | Closed form within 0.1 %, (True, False) |

## Result

Tests: `tests/tickets/test_t73_tooth_tips.py`, all pass (T73-4 with `EMACHINE_SLOW=1`).

First field run failed: "Sliding surfaces did not join cleanly". The cylinder used to trim the tips
was removed without its faces, which were then meshed as loose nodes (the trap T26 describes).
Removing it recursively fixed this: the model and the mesh file now both have 11 954 nodes.
Field results: T74.
