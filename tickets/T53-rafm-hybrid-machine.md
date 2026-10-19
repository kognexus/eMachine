# T53: Hybrid machines: the radial-axial ("raxial") PMSM with a toroidal winding

Status: done
Depends on: T43 to T52; takes over B14 (skeleton part)

## Why

The user (2026-10-17) sent Zhang, Liu, Wu, "Research on a Novel High-Torque-Density Axial-Radial-
Flux Permanent-Magnet Motor with Annular Winding for an Elevator-Traction Machine", Electronics
2023, 12, 2867 (ARF-PMSM): "We'll collect such exotic options in 'hybrid' machines. I'd like to
have a separate feature script for raxial and also run the analysis on the topology proposed in
the paper for our voltage bus and amperage and see all analysis as we've done with others."

The machine: an SMC ring yoke with 24 teeth that stand out radially (facing an outer rotor with
radial magnets) and axially on both end faces (facing two rotor discs with axial magnets); 24
toroidal ("annular") coils around the yoke between the teeth, each with three active sides (outer,
both ends) and a passive inner side; 20 poles.

## Scope

- Naming: "hybrid machines" group flux paths that combine gap directions; `rafm` (alias `raxial`)
  is the first. Stator `toroidal_slotted`, winding span `toroidal` (one coil around the yoke per
  slot, label "toroidal"), rotor layout `three_sided_surface` (radial ring plus two discs),
  rotor placement `outer`. `docs/naming.md`, `docs/machines.md`, matrix.
- `rafm/pmsm` in `machines/rafm/`: variables as lengths and arcs (`docs/parameters.md`: radial
  rotor iron, radial magnet, radial tooth height and axial length, yoke width, axial tooth height,
  disc iron, axial magnet, slot width, slot opening, tooth tip, coil thickness, magnet arcs,
  current density); derived: stator radius, yoke inner radius, stator core length (closing
  dimension along the axis), coil loop, slot and tooth widths; checks; toroidal winding layout and
  factor; turn length; coil area; masses (copper, magnets, SMC, rotor steel); thermal network.
- `specs/rafm_zhang2023.json` and `_design.json`: Table 1 of the paper; the dimensions the paper
  does not give (yoke axial length, slot and coil width, coil thickness, tips, stator bore) chosen
  from Figures 2, 3 and the masses of Table 2, listed as assumptions.

## Acceptance criteria

- [x] Derived dimensions of the paper design: stator radius 175 mm, core length 80 mm, total 112 mm,
      axial magnets on r = 120..150 mm, radial magnets 28 mm long.
- [x] Toroidal winding of 24 slots, 20 poles, 3 phases: balanced, 8 coils per phase, k_w1 = 0.966.
- [x] Masses against Table 2: magnets 2.24 kg and copper 6.80 kg within 10 %, SMC core 18.6 kg
      within 20 % (the core details are reconstructed).
- [x] Old names still read; catalogue test (T48) covers the new variables.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T53-1 | derive of the paper design | as above |
| T53-2 | toroidal layout 24/20/3 | balanced, 8 coils per phase, k_w1 = cos 15 deg = 0.966 |
| T53-3 | masses | Table 2 within the tolerances |
| T53-4 | checks: coil thicker than the axial tooth room | `coil_axial` violated |

## Result

2026-10-17. `emachine/machines/rafm/` (`pmsm.py`: `RadialAxialFluxPMSM`, registered `rafm/pmsm`;
`dimensions.py`), `winding_layout.toroidal` and `toroidal_factor` (label "toroidal"), loader:
`toroidal` like `ring` has no layers / pitch / slot class, `raxial` read as `rafm`. Variables as
`docs/parameters.md` lists them (section "Radial-axial machine"); checks `radial_tooth_width`,
`axial_tooth_width`, `slot_width`, `slot_opening`, `yoke_length`, `radial_tooth_length`,
`coil_radial`, `coil_axial`, `coil_inner`, `balanced_winding`; masses of magnets, copper, SMC core
and rotor steel; thermal network (coils to core over the insulation, core to the support at the
bore, three gaps to the rotor, rotor to ambient).

The paper design (`specs/rafm_zhang2023*.json`), Table 1 and reconstructed details. The paper gives
no yoke length, slot width, coil build, tips or bore. They were chosen from Figures 2 and 3 and then
fitted to the three masses of Table 2 at once: bore 200, yoke 40 mm long (axial teeth 20), slot
16 mm, coil 17 mm thick, opening 4, tips 2, fill factor 0.6. Masses: magnets 2.40 kg (paper 2.24,
+7 %), copper 6.98 kg (6.80, +3 %), SMC core 19.35 kg (18.6, +4 %). A first reconstruction with
20 mm slots matched the copper only (core -9 %) and saturated its teeth (T55).

Tests (`tests/unit/machines/test_rafm.py`, 5): T53-1 to T53-4 and the names.
