# T48: Parameter catalogue: what describes an RFM, AFM and TFM, and what the optimizer chooses

Status: done
Depends on: T43 to T47

## Why

The user (2026-10-17), after using the eMachine dialog: "I find the ratios weird. I'd rather like
to select the yoke height, slot height. Please find out the different parameters required to
design motors in all radial, axial and transverse flux motors and check which one of them are
suitable to be parametrized. Avoid arbitrary ratios."

The slotted machines (RFM, AFM) take `bore_ratio`, `tooth_ratio` and `slot_depth_ratio`, each a
fraction of a room that depends on the other ratios; the rotor layouts take `magnet_width_ratio`,
`insulation_ratio`, `magnet_fill_ratio`, `rotor_pole_arc_ratio`, `stator_pole_arc_ratio`; the TFM
hides the claw tip as 0.5 x root. The same value means a different part in every design.

## Scope

- `docs/parameters.md`: per flux path and rotor layout every quantity, classed as specification,
  design variable, derived (and checked) or geometry constant, with its name and unit; the rules
  (absolute lengths, arcs in electrical degrees, one derived closing dimension per direction, no
  ratio of a derived room); old names and their conversion.
- A test that holds the code to the catalogue: every design variable of every machine and rotor
  layout is listed with its unit suffix, and none is a ratio.

## Acceptance criteria

- [x] Catalogue written; RFM, AFM, TFM, every rotor layout of the matrix.
- [x] Test: variables of all machines of the matrix (all layouts, TFM stators and rotors) appear
      in the catalogue; no variable name contains `ratio` or `span`; every length ends in `_mm`.
      (Passes once T49 to T51 are done.)

## Test cases

| ID | Test | Expected |
|---|---|---|
| T48-1 | Names of `variables(spec)` of every machine, layout, stator | in the tables of `docs/parameters.md` |
| T48-2 | Same names | no `ratio`, no `span`; units `_mm`, `_deg`, `_el_deg`, `_A_mm2` or a count |

## Result

2026-10-17. `docs/parameters.md`: rules (specification = envelope; design variables = lengths,
counts and arcs in electrical degrees; one derived closing dimension per direction; no ratio of a
derived room; every derived dimension checked), tables for the RFM stator and its five rotor
layouts, the AFM, the TFM (all stators and rotors) and the SRM pole arcs, the geometry constants left
(I-bridge taper, Halbach segments, open slots: B17) and the old names with their conversion.

Tests (`tests/unit/machines/test_parameter_catalogue.py`, 2, 27 machines): every variable of every
registered machine, rotor layout and supported TFM stator is in the catalogue; no name contains
`ratio` or `span`; every name ends in `_mm`, `_deg` (`_el_deg`) or `_A_mm2`, or is `pole_pairs`.
