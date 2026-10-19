# T24: Toothed-ring stator of the review paper's Fig. 17, inner and outer stator

Status: done
Depends on: T22

## Why

The user (2026-10-15): some geometries of Kaiser and Parspour, "Transverse Flux Machine - A
Review" (IEEE Access 2022, arnumber 9709772) are missing from the FeatureScript and the geometry
script, especially Fig. 17, in both inrunner and outrunner style.

T22 listed Fig. 17 as "shift of stator poles" and added only the shift (`pole_shift_deg`), applied
to separate U-cores. The figure shows a different core: **one piece of iron**, a continuous
U-shaped ring (yoke and two side walls) that holds the ring coil, with rectangular teeth standing
on both walls towards the air gap. Teeth on the two walls are aligned; neighbouring tooth pairs
are one pole pair apart plus the additional shift angle. Neither the Onshape feature nor the
mesher could build such a core.

## Geometry (same in both places)

Heights are measured from the air gap away from the rotor, as for the other cores.

| Part | Axial extent | Height | Around the circumference |
|---|---|---|---|
| Teeth | each wall: slot width / 2 to slot width / 2 + leg width | 0 to tooth height | tooth span x pole pitch wide, parallel sides, one pair per pole pair; every second pair offset by the pole shift |
| Side walls | as the teeth | tooth height to slot height | continuous ring |
| Yoke | whole core width | slot height to slot height + yoke height | continuous ring |
| Coil | as for the U-core | top of the slot window | ring |

- New core type: mesher `core_type: "tr"`, Onshape "Toothed ring (Fig. 17)".
- New parameter: mesher `ring_tooth_height`, Onshape "Ring tooth height". It must lie between 0 and
  the slot height.
- Inner stator (outrunner, teeth point outwards, as drawn in Fig. 17) and outer stator (inrunner,
  teeth point inwards) are both built; the pole faces are trimmed to the air-gap cylinder as for
  the U-core.
- Each tooth is modelled up to the slot height and fused with the ring, so its flat end lies inside
  the wall. Its volume outside the ring is exactly the part between the air-gap cylinder and the
  cylinder at the tooth height, which gives a closed form for the core volume.

## Acceptance criteria

- [x] The mesher builds the toothed ring for inner and outer stator, with and without pole shift,
      and its core volume matches the closed form within 0.1 %.
- [x] A sector mesh of an inrunner and an outrunner with the toothed ring passes the mesh checks.
- [x] A no-load field solution shows a flux linkage that changes sign between the aligned position
      and the next pole.
- [x] `tfm_stator.fs` has the new core type and parameter, and the stator code in
      `tfm_ui32_design.fs` is kept identical to it.
- [x] The Onshape feature builds the toothed ring in both styles (needs the `onshape-fs` connection).

## Test cases

| ID | Test | Expected |
|---|---|---|
| T24-1 (slow) | `--stator-only` volumes: inner and outer stator, pole shift 0 and 3 deg | Core within 0.1 % of the closed form; coil exact |
| T24-2 (slow) | Sector mesh, inrunner and outrunner, Halbach rotor, `check_mesh.py` | Sliding surfaces and periodic planes match |
| T24-3 (slow) | No-load solution at 0 and one pole pitch, outrunner | Flux linkage changes sign, same magnitude within 20 % |
| T24-4 | FeatureScript source | Enum entry and label present, parameter validated, stator code of both `.fs` files identical |
| T24-5 | Mesher rejects a tooth height outside (0, slot height) | Error message |

## Result

Run on 2026-10-15. Machine of the tests: air-gap radius 35 mm, 16 pole pairs, tooth span 0.6, 3 mm
walls, 8 mm slot, 12 mm slot height, 4 mm yoke, 5 mm teeth, Halbach rotor with two rows 8 mm apart.

- Mesher: `core_type: "tr"` and `ring_tooth_height` in `tfm_gmsh_sector.py`. The core is one solid.
  Core volume against the closed form: outer stator 30 700.60 against 30 700.65 mm3 (-0.0002 %),
  inner stator 16 362.80 against 16 362.75 mm3 (+0.0003 %), the same with a 3 degree pole shift.
  Coil exact.
- Sector mesh (T24-2): outrunner 73 075 and inrunner 74 343 tetrahedra; no node shared across the
  sliding surface, all sliding and periodic nodes matched (mismatch below 3e-14 mm), lowest
  element quality 0.155.
- No load (T24-3, linear iron, one turn), coil flux at 0, half and one pole pitch:
  outrunner 89.49, -0.07, -89.67 uWb; inrunner -82.38, -0.05, 82.44 uWb. The phase works in both
  styles. Cogging torque at these three points is at most 0.0125 Nm.
- FeatureScript: "Toothed ring (Fig. 17)" in the core structure list and "Ring tooth height" in
  `tfm_stator.fs`, built for linear segments and rotary rings, inner and outer stator, with phases
  and pole shift; the stator code in `tfm_ui32_design.fs` was replaced by the new one (test T24-4).
- Onshape parameter sheet (`tfm/onshape.py`): core name and "Ring tooth height".
- Tests: `tests/test_t24_toothed_ring.py`, all five pass (T24-1, 2, 3, 5 with `TFM_SLOW=1`); the
  fast suite passes (201 tests).

### Onshape (2026-10-15, second session)

- `tfm_stator.fs` compiled without errors in the scratch studio and was then written to "TFM stator
  v2" (`d334ef1663ba5be0eadd7209`) with `put_featurescript` (no errors), and read back.
- `test_feature` still fails with the workspace error noted in T22, so the feature body was run
  through `test_featurescript` (code transformed into one lambda; the toothed-ring branch verbatim).
  Results on Onshape:

| Case | Core solids | Core mm3 | Coil mm3 | Check |
|---|---|---|---|---|
| Outrunner (inner stator), shift 0 and 3 deg | 1 | 16 362.752 | 5 717.699 | closed form 16 362.75, mesher 16 362.80 |
| Inrunner (outer stator), shift 0 and 3 deg | 1 | 30 700.646 | 9 676.105 | closed form 30 700.65, mesher 30 700.60 |
| Outrunner, 3 phases | 3 | 49 088.257 | 17 153.096 | 3 x one phase |
| Inrunner, 3 phases | 3 | 92 101.939 | 29 028.316 | 3 x one phase |
| Outrunner, faces not trimmed | 1 | 16 370.768 | 5 717.699 | flat pole faces, slightly more iron |
| Linear, 3 pole pairs | 1 | 6 420 | 2 100 | hand calculation 6 420 and 2 100 |
| Rotary with feature defaults | 1 | 413 769.693 | 105 859.106 | builds |
| Tooth height = slot height | - | - | - | "The ring tooth height must be smaller than the slot height." |
| U defaults, U-I outrunner, claw-pole outrunner | 2, 32, 1 | built | | earlier types still build |

Open:

- The dialog was not opened in the Onshape interface (the MCP tools cannot do that).
- The "TFM UI32 design" studio still holds the earlier stator code; it uses only the U-I core, so
  its geometry is unchanged. The local `tfm_ui32_design.fs` already carries the new code.
- The optimizer (`tfm/design.py`, specification `stator_type`) does not offer the toothed ring yet.
