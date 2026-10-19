# T58: Multi-topology study in the ILM-E85x23 envelope: frame, reference, drive-based evaluation

Status: done
Depends on: T41, T46, T53 to T57

## Why

The user (2026-10-18): extend the machine implementations to the missing topologies, improve
rotor and stator design parameters and torque-ripple methods from the papers of the Zotero
collection "Robotics/Actuators", then analyse every topology that fits the TQ RoboDrive
**ILM-E85x23** form factor (stack 30 mm) at the same bus voltage and current, with an interactive
Pareto chart per topology, the optimal design of each, ParaView analysis of the optimal and
highest-torque designs, Motor-CAD-like phase voltage analysis, and a report against the ILM-E85x23.
Everything goes to `multi-topology-analysis/`. Ultimate objective: the most torque at the same
dimensions and input power at low speed, efficiency above 80 %, ripple reasonable (deterministic
ripple is removed by the controller).

Constraints set by the user: air gap 0.3 to 1 mm; bus voltage and current of the TQ motor; copper
fill 0.5 to 0.7 with the AWG (and strands in hand) chosen so the winding carries the peak current;
windings integer-slot or fractional-slot concentrated, not purely distributed; exotic machines
welcome (dual-rotor axial flux, raxial, dual-stator vernier, skewing).

## Reference: ILM-E85x23 (extended datasheet Rev 0101, star-serial; `multi-topology-analysis/reference/`)

| | |
|---|---|
| Stator outer diameter, rotor inner diameter | 85 mm, 52 mm |
| Stator length (with end windings), rotor length | 35.7 mm, 25.2 mm |
| Rated voltage | 48 V |
| Rated current (phase amplitude) | 10.5 A |
| Rated torque, peak torque (20 % linearity deviation) | 2.58 Nm, 8.31 Nm |
| Torque constant, motor constant (20 C) | 0.247 Nm/A, 0.503 Nm/sqrt(W) |
| Terminal resistance, inductance | 322 mOhm, 938 uH (line to line) |
| No-load speed at 48 V | 1606 rpm |
| Copper loss at rated torque (20 C) | 26.7 W |
| Pole pairs, max. efficiency, mass | 10, 94 %, 629.8 g |

Peak current: 8.31 Nm at 20 % below the linear torque, 8.31 / (0.8 x 0.247) = **42 A**.

## Decisions (made while the user was away; to be confirmed)

- Envelope: outer diameter 85 mm, bore (inner diameter of the active parts) 52 mm as the ILM-E's
  hollow rotor; active axial length 30 mm. Radial machines: 30 mm lamination stack, end windings
  outside it (reported). Axial machines: 30 mm for all discs, gaps and stators; end windings in the
  radial room between 52 and 85 mm.
- Drive: 48 V DC link, space-vector modulation: phase voltage amplitude at most 48 / sqrt 3 x 0.95.
  Rated current 10.5 A amplitude (7.42 A rms), peak 42 A. SRM: asymmetric half bridge on the same
  48 V, the same rms phase current at the rated point and at most 42 A peak.
- Rated point: **1000 rpm** ("lower rpm" than the ILM-E's 1606 rpm no-load speed). The number of
  turns of each design is the most the bus allows at 10.5 A and 1000 rpm, unless the efficiency
  limit (80 % at the rated point) asks for fewer.
- Objectives: rated torque (max), peak torque at 42 A (max), torque ripple at the rated point (min).
  Constraints: efficiency >= 80 % at the rated point, copper fill 0.5 to 0.7, current density
  <= 10 A/mm2 rms at rated and <= 40 A/mm2 rms at peak, geometry checks.

## Scope

- `docs/design_principles.md` from the literature notes (T62).
- Drive evaluation of a design at fixed bus voltage and current (`emachine/physics/drive.py`,
  `emachine/pipeline/drive.py`): FE at a few ampere-turn levels, turns from the voltage, AWG and
  strands from the fill, dq torque and MTPA angle, rated sweep for ripple, flux and voltage
  waveforms, iron loss, efficiency.
- Study runner `python -m emachine study` (T63), report (T64), ParaView (T65), reference model (T66).

## Acceptance criteria

- [x] `multi-topology-analysis/` holds the specifications, run data, Pareto charts, ParaView files, pictures and
      the report.
- [x] Every analysed design satisfies the user's limits (gap, fill, winding type, drive); designs that violate a
      study limit (efficiency, current density, voltage) are marked infeasible, and the report lists the limits
      each verified pick meets.
- [x] The report compares every topology with the ILM-E85x23 datasheet and with the same-rule reference model (T66).

## Test cases

- T58-1 turns from the voltage: a design with known flux per turn gets the turns that just meet
  48 / sqrt 3 x 0.95 V at 1000 rpm.
- T58-2 AWG and strands: fill between 0.5 and 0.7 when possible; violation otherwise.
- T58-3 the drive limits of the study config equal the datasheet values above.

## Result

2026-10-18. Configuration `multi-topology-analysis/study.json`; datasheet in `reference/`; literature in
`literature/`; runs in `runs/`; reference model in `reference_model/`; speed sensitivity in `speed_sensitivity/`;
ParaView in `paraview/`; report in `report/`. Command line: `python -m emachine study`,
`python -m emachine.analysis.topology_study --reference --speeds --skew-check`, `python -m emachine.analysis.topology_postprocess`.
Tests: `tests/tickets/test_t58_drive.py` ... `test_t63_t65_study_outputs.py`. Decisions made while the user was
away are listed in the section "Decisions" above and in the report's method section.
