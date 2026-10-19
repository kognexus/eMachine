# T56: Full analysis of the paper's raxial machine at our bus and current

Status: done
Depends on: T53 to T55

## Why

The user wants the analyses made for the other machines (T28, T41, T42) for this topology, at the
project's drive limits (`limits.bus_voltage_V` up to 48 V, `limits.max_current_A` 15 A peak),
not the paper's 270 V / 7.3 A.

## Scope

- Evaluation of the paper design at our limits: turns chosen from the bus voltage, current, copper
  and core losses (SMC Somaloy 700HR 5P), rotor and magnet eddy losses, thermal network, torque,
  ripple; the same at the paper's operating point for comparison.
- Efficiency map (`python -m emachine map`) at our limits.
- ParaView files: radial section and axial slices with their fields, and the efficiency map.
- Report `runs/rafm_zhang2023/report.md`: paper against our model, our limits, what limits the
  machine at 48 V / 15 A.

## Acceptance criteria

- [x] `evaluate`, `map`, `export` run on `specs/rafm_zhang2023*.json` without code paths of the
      other machines failing.
- [x] Report with both operating points and the map; views checked by eye.

## Result

2026-10-17. `runs/rafm_zhang2023/report.md`. Maps at our drive with the optimizer's turns (97: the
current cut-off needs them, the bus allows 16; 219 Nm at standstill, 27 rpm no-load) and with 18
turns (43.6 Nm at 120 rpm, 548 W, 81 %), and at the paper's drive (140 turns, 400 V: 231.9 Nm at
120 rpm, 2.91 kW, 78.7 %, best 85.5 %). ParaView export of the paper's rated load (48 steps per
period): the radial section as `machine.pvd` (the views of T42 work unchanged) and the axial slices
on both discs as `axial.pvd`, `core_loss_axial.vtu`; a sixth view for hybrid machines shows both
(`views/6_radial_and_axial_field.png`). All six views checked by eye.

Changes on the way:
- `section_export`: the quasi-3D geometry (parts, axial rings, torque shares); magnets with a given
  magnetisation.
- `losses.resample_nearest`: an exact grid search for large meshes (the brute force was O(n^2):
  hours for the 85 000 core elements of the quasi-3D model); small meshes keep the brute force,
  so the results of the other machines do not change (characterization data equal).
- `map`: when no number of turns meets both drive limits the note says so instead of claiming the
  bus voltage chose them.
