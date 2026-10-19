# T26: Arched valleys between the teeth of the toothed ring

Status: done
Depends on: T24, T25

## Why

The user (2026-10-15): "In the toothed ring can we make arch from one tooth to another instead of
straight cut teeth?"

## Geometry

Option `ring_arched_valleys` (mesher) / "Arched valleys between teeth" (Onshape), off by default.
When on, each side wall is a full ring from the air gap to the slot height, and the space between
two neighbouring teeth is cut away under an arch:

- The arch is drawn in the frame of the valley centre (the bisector of the two teeth). Its ends are
  the top corners of the two teeth, on the air-gap circle, so each tooth keeps its top width
  (tooth span x pole pitch). Its deepest point is at the ring tooth height on the bisector.
- If the valley is no deeper than half its width (between the two corners), the arch is the
  circular arc through the two corners and the deepest point.
- If it is deeper, the bottom is a half circle of the valley width and the sides run straight
  (parallel to the bisector) up to the tooth corners; one arc through the three points would
  undercut the teeth.
- Tooth tops lie on the air-gap cylinder in this mode, whatever "trim pole faces" says.
- With a pole shift the valleys alternate between two widths (2 pole pitches plus and minus the shift).
- Linear arrangement: the same profile with straight walls; valleys only between teeth.

## Acceptance criteria

- [x] The mesher builds arched valleys for inner and outer stator, with and without pole shift; the
      core is one solid and its volume matches a numerical integration of the profile within 0.1 %.
- [x] Both arch cases (single arc, half circle with straight sides) are covered.
- [x] Sector meshes of an inrunner and an outrunner with arched valleys pass the mesh checks.
- [x] A no-load solution with arched valleys changes sign over one pole pitch.
- [x] The Onshape feature builds the same volumes (within 0.1 %) in both styles.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T26-1 (slow) | `--stator-only` volume, inner and outer stator, shift 0 and 3 deg, arc and half-circle case | One solid; within 0.1 % of the integral |
| T26-2 (slow) | Sector mesh, inrunner and outrunner, `check_mesh.py` | Sliding surfaces and periodic planes match |
| T26-3 (slow) | No-load flux at 0 and one pole pitch, outrunner | Sign change, same magnitude within 20 % |
| T26-4 | FeatureScript source and Onshape sheet | Field present, only `==` conditions, row on the sheet |
| T26-5 | Onshape (`test_featurescript`) | Same volumes as the mesher within 0.1 % |

## Result

2026-10-15. Test machine of T24 (air-gap radius 35 mm, 16 pole pairs, tooth span 0.6, 3 mm walls,
8 mm slot, 12 mm slot height, 4 mm yoke).

Core volume in mm3 (one phase), integral of the profile / mesher / Onshape:

| Stator | Shift | Tooth height | Arch | Integral | Mesher | Onshape |
|---|---|---|---|---|---|---|
| Inner (outrunner) | 0 | 3 mm | arc | 18 569.581 | 18 569.6 | 18 569.581 |
| Inner (outrunner) | 0 | 7 mm | half circle | 15 112.938 | (test) | 15 112.938 |
| Inner (outrunner) | 3 deg | 3 mm | arc | 18 565.593 | 18 565.6 | 18 565.593 |
| Inner (outrunner) | 3 deg | 7 mm | half circle | 15 159.263 | (test) | 15 159.263 |
| Outer (inrunner) | 0 | 3 mm | arc | 33 762.849 | 33 762.8 | 33 762.849 |
| Outer (inrunner) | 0 | 7 mm | half circle | 30 191.574 | (test) | 30 191.574 |
| Outer (inrunner) | 3 deg | 3 mm | arc | 33 758.970 | 33 759.0 | 33 758.970 |
| Outer (inrunner) | 3 deg | 7 mm | half circle | 30 216.243 | (test) | 30 216.243 |

"(test)": checked by T26-1 within 0.1 % (all eight cases pass); the cases printed during the work
agreed within 0.0002 %. Onshape, further cases: 3 phases = 3 x one phase (55 708.742 and 90 648.728);
linear arrangement, 3 pole pairs, 7 331.963 (hand calculation 7 331); the straight-cut ring is unchanged
(16 362.752).

No load, coil flux at 0, half and one pole pitch (linear iron, one turn, tooth height 5 mm):

| | Straight-cut (T24) | Arched |
|---|---|---|
| Outrunner | 89.49, -0.07, -89.67 uWb | 87.05, -0.03, -87.25 uWb |
| Inrunner | -82.38, -0.05, 82.44 uWb | -77.33, -0.00, 77.39 uWb |

The arches take away some iron next to the teeth: 2.7 % less flux for the outrunner, 6 % for the
inrunner. Three positions say nothing about cogging or ripple; that needs a full sweep.

Bugs found on the way:

- The tooth corner height in the valley frame needs the stator side's sign; without it the inner
  stator was off by up to 0.13 %.
- The arc centres, added as construction points in Gmsh, stayed in the model as free points. Gmsh
  counted their nodes but did not write them, so the pipeline's node check after merging failed.
  They are removed now, and T26-2 checks that the node count of the mesh file matches.
- On Onshape the valley cutter first reached half a pole pitch past the walls along the axis and
  cut into the neighbouring phase; it now stops at a quarter of the phase spacing.

Uploaded to "TFM stator v2" (compiles). `tfm_ui32_design.fs` was regenerated locally; the "TFM UI32
design" studio was not uploaded again (its U-I machine is not affected).
