# T51: Axial flux machine dimensions: annulus, axial stack, arrangement

Status: done
Depends on: T48, T49

## Why

The AFM machines use the dimensions of the radial machine on the mean radius (a placeholder of
T40): a "bore ratio" and a slot depth in the radial direction mean nothing for a disc machine.
`docs/parameters.md` lists what describes an AFM.

## Scope

- `AxialFlux.derive`: annulus between `inner_diameter_mm` and the outer diameter; rectangular slots
  of `slot_width_mm` and axial depth `slot_height_mm`; stator yoke `yoke_height_mm`; the rotor back
  iron is what is left of the axial length (`stack_length_mm`) after the stators, gaps and magnets
  of the arrangement (single: 1 stator, 1 rotor; double_rotor: 1 stator with two slotted faces,
  2 rotors; double_stator: 2 stators, 1 rotor with magnets on both faces).
- Checks: tooth width at the inner diameter, slot width, inner diameter above the bore, rotor back
  iron (double_stator: may be zero, a coreless rotor), slot class, balanced winding.
- Winding (turn length: two radial active lengths and the end turns), thermal network of a disc.
- AFM rotor layouts: `surface` (magnet thickness and arc), `salient` (SRM: pole arc and axial pole
  height).

## Acceptance criteria

- [x] Hand-calculated design (each arrangement): annulus, tooth, slot area, rotor back iron.
- [x] Middle designs of `afm/pmsm` and `afm/srm` give finite checks; geometry still stops with B10 / B11.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T51-1 | Outer 200, inner 120, 24 slots, slot 8 x 15, yoke 6, magnet 4, gap 1, L 40, double_rotor | stator 36, back iron (40 - 36 - 2 - 8) / 2 = -3: infeasible; with L 50: 2 mm |
| T51-2 | Same, single | stator 21, back iron 50 - 21 - 1 - 4 = 24 |
| T51-3 | Tooth at the inner diameter | 2 pi 60 / 24 - 8 = 7.708 |

## Result

2026-10-17. `machines/afm/base.py`: variables `inner_diameter_mm`, `slot_height_mm` (axial),
`slot_width_mm`, `yoke_height_mm`; `derive` per arrangement (`DISCS`: stators, slotted faces, rotor
discs, rotor faces): stator length, rotor back iron from the axial length, tooth at the inner
diameter, slot area width x height, turn length on the radial active length, coils of every slotted
face; checks `tooth_width`, `slot_width`, `inner_diameter`, `rotor_back_iron` (zero allowed for the
double-stator rotor); thermal network of discs. The salient AFM rotor checks the pole arcs at the
mean radius; the salient poles take the room of the magnets.

Tests (`test_dimensions.py`, AxialFluxTest, 4): the ticket's hand cases (double rotor -3 / 2 mm,
single 24 mm, double stator), tooth 7.708 mm, coils of two faces, SRM pole arcs. The skeleton tests
(middle designs, geometry stops with B10 / B11) pass.
