# T72: Step skew of the rotor magnets inside each phase

Status: done (code and tests); measured effect in T74
Depends on: T70

## Why

User's item 5 (T70): skewing. T28 found a torque ripple of 53 % on the user's machine: the sixth
harmonic of the cogging of the three phases adds up. The machine already has a stator-side remedy,
the pole shift (`pole_shift_el_deg`, T22). This ticket adds the rotor-side one.

## Concept

Options `machine.rotor_skew_el_deg` and `machine.rotor_skew_steps`. Each magnet row of a phase is cut
into `steps` axial slices, turned evenly from -skew/2 to +skew/2 (electrical degrees in the spec,
mechanical in the parameter file, `rotor.skew_steps` and `rotor.skew_deg`). Spoke pole pieces turn
with their slice. The eddy-current width of a magnet is capped by the slice length.

Expectation, to be measured: skew lowers cogging and ripple and costs a little torque (literature in
`multi-topology-analysis/literature/afpm_tfm.md`: stator-tooth skew -82 % cogging for -10 % torque;
phase-segment skew -83 % for -3.4 %). Skew does not raise efficiency. At 150 rpm it changes only the
small harmonic iron loss.

## Acceptance criteria

- [x] Parameters carry the slices and the mechanical angle; skew without steps is refused.
- [x] Gmsh: twice the magnets for two steps, same volume, slices at -skew/2 and +skew/2.
- [x] Without skew the magnet names and the geometry are those of earlier runs.
- [x] Sector mesh with two steps passes `check-mesh`.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T72-1 | 20 deg el in 2 steps, 24 pole pairs; skew with 1 step; 0 steps | 20/24 deg mech; error; error |
| T72-2 | Eddy width with 3 and 5 slices | Segment width; slice length 1.8 mm |
| T72-3 (slow) | Rotor with and without skew | Twice the magnets, same volume, shifts -/+10/24 deg, names |

## Result

Tests: `tests/tickets/test_t72_rotor_skew.py`, all pass (T72-3 with `EMACHINE_SLOW=1`). The skewed sector
mesh of the user's machine passes `check-mesh` (56 218 tetrahedra, periodic planes matched). Field results: T74.
