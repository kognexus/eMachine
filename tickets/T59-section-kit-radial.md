# T59: General 2D section kit for radial machines (inner, outer, dual stator), all rotor layouts

Status: done
Depends on: T41, T49, T58

## Why

`rfm/pmsm surface` is the only radial machine with a mesh. The backlog tickets B06 (IPM), B07
(SynRM), B08 (PMaSynRM), B09 (SRM), B15 (vernier) and B17 (slot openings, tooth tips) need a
geometry, and the study needs outer-rotor and dual-stator machines.

## Scope

`emachine/machines/section2d/`: a radial machine is a list of rings from the bore to the outer
diameter, each a stator or a rotor; every air gap between a stator and a rotor ring carries the
Arkkio torque on its rotor side.

- Stators: slotted with tooth tips and slot openings (B17; open slots when the opening equals the
  slot width), split teeth (vernier flux modulation), salient poles (SRM); facing inwards or
  outwards; slot star winding (FSCW or integer slot) from `winding_layout`.
- Rotors: surface (parallel or radial magnetised arcs), Halbach (2 or 3 segments per pole),
  consequent pole, interior V, spoke, flux barriers (SynRM), flux barriers with magnets (PMaSynRM),
  salient poles (SRM), cup rotor with magnets on both faces (dual-stator vernier).
- Mesher with region description for the 2D Elmer solver; multi-gap torque.

## Acceptance criteria

- [x] Every layout meshes for a reference design (one drawable random design per topology, two rotor angles); magnet
      areas as computed analytically within 2 % (T59-1).
- [x] The inner-rotor surface PM design of `specs/rfm_spm_12s10p*.json` gives the same torque as the T41 mesher within 2 %
      (T59-2: 0.06 % and 0.05 % at two positions, flux linkages equal to 4 digits).
- [x] Outer-rotor torque sign and dual-gap torque: the outer-rotor SPM finds its torque at the current angle 180 deg from
      the inner rotor's (its coils link the magnet flux the other way round); the dual-stator vernier sums two gaps.

## Test cases

T59-1 to T59-3 (fast: parameter checks and region lists; slow: meshes and one solve each).

## Result

2026-10-18. `emachine/machines/section2d/` (`shapes.py`, `radial.py`, `axial.py`, `mesher.py`, `builder.py`),
solver `emachine/solvers/elmer/sections.py` ("elmer_sections"), and the case writer of `section2d.py` with a
remanence and permeability per magnet. A radial section is a list of rings from the bore out; stators:
slotted with parallel teeth (or parallel slots, as T41), tooth tips and openings (B17), notches and split
teeth (vernier); rotors: surface (parallel, segmented radial), Halbach (2 to 4 segments), consequent pole,
interior V with pockets ending at the bridge, spoke with pockets, flux barriers (circles around the q
axis) with or without ferrite, salient (SRM), magnet ring between two stators. Iron poles carry a priority
name (`rotor_pole`) merged into the rotor core after fragmenting.

Bugs found by drawing every topology (`emachine/io/section_svg.py`, sketches looked at): pockets of flat V
bars swept along the rotor surface (now at most one magnet thickness long, checked against the pole
width); salient and consequent iron poles lost to the air band of their layer; a wrap tolerance in the
axial slices. Meshing takes about 1 s per position, a solve about 1 s (10 000 to 30 000 triangles).
Tests: `tests/tickets/test_t59_section_kit.py` (catalogue drawable, gap range, magnet areas; slow: T41).
