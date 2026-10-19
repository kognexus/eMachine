# T49: Slotted stator in absolute dimensions: slot height, slot width, yoke height

Status: done
Depends on: T48

## Why

`docs/parameters.md`. The stator of the RFM is chosen today by `bore_ratio`, `slot_depth_ratio`,
`tooth_ratio` and `yoke_mm`; the stator need not reach the outer diameter (the reference design's
stator is 96 mm in a 100 mm envelope). Found while writing the catalogue: `derive` gives the slot
area of slots that widen outwards (parallel teeth), but the mesher and the CAD draw parallel-sided
slots; for the reference design that is 122 mm2 against the 85 mm2 meshed, so ampere-turns, copper
loss and current density do not belong to the drawn slot.

## Scope

- Variables `slot_height_mm`, `slot_width_mm`, `yoke_height_mm` (with `pole_pairs`,
  `current_density_A_mm2`). Bore radius = outer radius - yoke - slot height; the stator fills the
  outer diameter.
- Slot area of the parallel-sided slot (width x height, less the circle segment at the bore), as the
  mesher's coil regions.
- Checks: tooth width at the bore >= minimum iron, slot width >= minimum slot width, rotor radius
  above the shaft, rotor core.
- `emachine.spec.names.standard_values`: old designs (`bore_ratio`, ...) converted to the same bore,
  slot and tooth; spec `variables` with an old ratio stop with the new names. Reference spec and
  design converted. Cache keys of RFM designs change (the stator fills the envelope now): recorded
  as intended in the characterization data.

## Acceptance criteria

- [x] Derived slot area within 1 % of the meshed coil area (reference and a 24-slot design).
- [x] Reference design (old values) converts to bore radius 30, slot height 12, slot width 7.069 mm
      and yoke 8 mm.
- [x] T41 tests pass on the converted reference (slow).
- [x] Old ratio names in a spec's `variables` give an error naming `slot_height_mm`, ...

## Test cases

| ID | Test | Expected |
|---|---|---|
| T49-1 | `derive` of the converted reference | bore 30, slot 12 x 7.069, tooth 8.639, yoke 8, back radius 50 |
| T49-2 | Slot area against the Gmsh coil regions | within 1 % |
| T49-3 | Old design file | same bore, slot, tooth as before |
| T49-4 | Spec with `bore_ratio` in `variables` | SpecError naming the new variables |
| T49-5 | Checks: wide slots | `tooth_width` violated |

## Result

2026-10-17. `SlottedMachine.common_variables`: `slot_height_mm` (minimum coil height to half the
room between shaft and outer diameter), `slot_width_mm` (minimum slot width to pi D / (2 slots)),
`yoke_height_mm` (iron limits). `derive`: bore radius = outer radius - yoke - slot height, tooth at
the bore = slot pitch - slot width, slot area of the parallel-sided slot (`slot_section_area`:
width x height plus the circle segment at the bore); the winding part (`_winding_dimensions`) is
shared with the AFM. `stator_checks`: tooth, slot, rotor around the shaft (the `back_radius` check
is gone: the stator always fills the outer diameter).

The slot area now belongs to the drawn slot: 84.98 mm2 for the reference (was 122.5 mm2 of a slot
widening outwards; the mesh has 84.9 mm2), so ampere-turns and copper loss per current density
are 31 % lower than before for the same J; the field solution always used the meshed coil.

Old names: `standard_values` converts a whole old design (same bore, slot, tooth; the yoke takes
the room the old stator left inside the envelope: 6 -> 8 mm for the reference); a spec that fixed
all three ratios (the spec of a run) converts too; bounds on a ratio stop with the new names. The
reference spec and design are written in the new names (slot 12 x 7.07 mm, yoke 8 mm). RFM cache
keys change on purpose (the cache-key test skips radial and axial machines with the reason).

Tests (`tests/unit/machines/test_dimensions.py`): T49-1 to T49-5, bounds; slow: the derived slot
area against the meshed coil regions for the reference and a 24-slot design, within 1 %.

Full slow suite after T48 to T52: 387 tests pass (1 skipped) in 1627 s, including the T41 field
tests on the converted reference and the slot area against the mesh.
