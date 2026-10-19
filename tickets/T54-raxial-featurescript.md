# T54: Onshape feature "Raxial machine" (hybrid studio)

Status: done
Depends on: T53

## Why

The user wants a separate FeatureScript for the raxial machine; exotic machines are collected as
"hybrid" machines.

## Scope

- Feature Studio `emachine/cad/featurescript/hybrid/raxial.fs` (hand-written; built into
  `hybrid_design.fs` by `python -m emachine featurescript`), feature "Raxial machine": the dialog
  takes the spec inputs and the design variables of T53 (lengths, arcs), derives the rest as
  `rafm/pmsm` does and stops with messages naming the fields.
- Parts: SMC stator (yoke ring, radial teeth with tips, axial teeth with tips on both faces, inner
  teeth), 24 toroidal coils (rectangular loops around the yoke, coloured by phase), radial rotor
  ring with magnets, two rotor discs with magnets (N/S coloured), full 360 degrees.
- `python -m emachine onshape --spec specs/rafm_zhang2023.json --design ...` prints the dialog values.

## Acceptance criteria

- [x] Compiles in Onshape; builds the paper design.
- [x] Volumes of magnets, coils and the stator core equal the Python masses / densities within 1 %.
- [x] Sheet fields exist in the dialog (test).

## Result

2026-10-17. `emachine/cad/featurescript/hybrid/raxial.fs` (feature "Raxial machine"),
`python -m emachine featurescript` writes `hybrid_design.fs` (with the shape helpers of
`emachine_main.fs`), `python -m emachine onshape --spec specs/rafm_zhang2023.json --design ...`
prints the Raxial dialog and, to check, stator diameter, yoke radii, core and yoke length, volumes.

Onshape: Feature Studio "Hybrid machines" created in the document (element
26898babea777c1d5d76e609) and the studio written into it; it compiles. A harness run of the
feature on the paper design built 1 stator, 24 coils, 20 radial and 40 axial magnets and the rotor;
volumes against `dimensions.py`: coils, magnets and rotor equal (0.0000 %), stator core -0.20 % (the
slot boxes leave thin slivers where a flat slot side meets a circle). That run used the first
reconstruction (20 mm slot); the defaults are now 16 / 17 mm and the studio was rewritten with them.

Tests (`tests/unit/cad/test_featurescript.py`, HybridTest): studio up to date, one feature, no real-
valued (ratio) fields; every sheet field in the dialog; defaults equal the paper design.
