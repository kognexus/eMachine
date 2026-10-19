# T60: Axial flux machines as quasi-3D slices: single-sided, dual rotor (YASA), dual stator, coreless, SRM

Status: done
Depends on: T55, T58

## Why

B10 (AFPM), B11 (AF-SRM) are only skeletons. Axial machines suit the ILM-E envelope (inner to
outer diameter 52/85 = 0.61, the optimum 0.58 to 0.63 of the literature).

## Scope

`emachine/machines/section2d/axial.py`: K slices at the Gauss radii of the active annulus, each
unrolled (x = r theta, y = z) and periodic over the circumference; rotor parts shifted by the rotor
angle and wrapped. Arrangements: single-sided (stator with yoke, one rotor disc), dual rotor with a
yokeless segmented stator (YASA), dual stator with a magnet rotor (AFIR), coreless dual Halbach
rotor, dual-stator salient-pole SRM. Torque per slice from the Maxwell stress in each gap band, on
the rotor side; flux per turn summed over the slices.

## Acceptance criteria

- [x] Each arrangement meshes and solves (single-sided, YASA, AFIR, coreless Halbach, dual-stator SRM: smoke test, one
      design each); periodic boundaries and two gaps with their rotor sides (T60-1).
- [x] One slice at a large radius (200 mm, 36 slots, 30 poles) against the radial section of the same machine: the
      torque at the best current angle within 5 % (T60-2). The slice is the mirror image of a section (its normal
      points the other way), so the same machine needs the opposite current sign; the evaluation finds the
      current angle and the phase sequence itself.

## Test cases

T60-1 to T60-3.

## Result

2026-10-18. `emachine/machines/section2d/axial.py`: layers from z = 0 up, each slice unrolled over 2 pi r and
periodic (Gmsh periodic mesh, Elmer periodic BC); rotor parts shifted by r theta and wrapped. Two slices at
the Gauss radii in the optimization, three in the verification. YASA: the second rotor's magnets carry
`polarity` -1, so both discs magnetise the same way and the flux passes straight through the yokeless
teeth. Meshes 20 000 to 45 000 triangles per design; a design takes about twice a radial one.
Tests: `tests/tickets/test_t59_section_kit.py` (T60-1), `tests/tickets/test_t60_axial_slices.py` (slow, T60-2, passes).
