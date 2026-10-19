# T57: A raxial machine in the envelope and drive of the TQ ILM85x23 (85 mm, 48 V, 11.3 A)

Status: done
Depends on: T53 to T56

## Why

The user (2026-10-17): use 48 V and 15 A; reduce the machine to an 85 mm outer diameter, turns and
AWG adjusted to a fill factor of 0.6; then: compare with the TQ RoboDrive ILM85x23 frameless motor
kit and make dimensions, bus voltage and currents similar; the stack length may be 30 mm; the bore
may be smaller.

ILM85x23 (TQ extended datasheet Rev 2.01, star-serial): stator outer diameter 85 mm, stator length
36.9 mm, rotor inner diameter 52 mm, rotor length 25.1 mm, 620 g; 48 V DC link, rated current
11.3 A (phase current amplitude), rated torque 2.57 Nm, peak torque 8.31 Nm, kT 0.229 Nm/A,
no-load speed 1728 rpm at 48 V, 0.30 ohm and 930 uH terminal, copper loss 28.7 W at rated torque,
10 pole pairs, max. efficiency 92 %.

## Scope

- `specs/rafm_ilm85.json`: outer diameter 85 mm (the whole machine: the rotor ring is outside),
  total axial length 30 mm, bore 30 mm (the user allowed a smaller bore than the ILM's 52 mm),
  48 V, 11.3 A peak, 1728 rpm, air gaps 0.5 mm, 12 slots, pole pairs 4 to 12, fill factor 0.6.
- Stator: iron-cobalt SMC (user, 2026-10-17: "Use iron-cobalt based SMC for the stator which give
  3D path"). No published FeCo SMC data with saturation, permeability and motor-frequency losses
  was found; modelled as our Somaloy curve (mu_r 600, which gives 1.56 T at 10 kA/m, Somaloy 700HR
  5P: 1.57 T) with the saturation raised from 1.95 to 2.2 T (FeCo bulk 2.3 to 2.4 T): 1.71 T at
  10 kA/m; density 7.8 g/cm3; loss coefficients of Somaloy (assumed).
- Turns and wire gauge chosen together (`winding.wire` = "awg", `physics.winding.fit_awg`): the
  turns the bus allows, the thickest AWG that fits, the number of turns that fills 0.6 best.
- NSGA-II optimization; map of the chosen design at 11.3 A and at the ILM's peak current
  (8.31 / 0.229 = 36.3 A); ParaView export; Onshape values; report against the ILM85x23.

## Acceptance criteria

- [x] Designs within 85 mm x 30 mm, drivable at 48 V and 11.3 A.
- [x] Turns and AWG of the chosen design; copper fill not above 0.6.
- [x] Table against the ILM85x23: torque at 11.3 A, kT, no-load speed, peak torque at 36 A,
      copper loss at rated torque, efficiency, active mass.

## Result

2026-10-18. `runs/rafm_ilm85/report.md`. NSGA-II, 208 designs; pick of highest torque: 7 pole pairs,
46 turns of AWG 22 per coil (copper fill 0.59), 0.64 kg active. Against the ILM85x23: torque at
11.3 A 2.44 Nm (2.57), kT 0.216 Nm/A (0.229), peak 7.48 Nm at 36.3 A (8.31), but continuous torque
1.0 Nm (2.57) and copper loss at 11.3 A about 66 W at 20 C (28.7 W): the toroidal coil's passive
inner side and the small slot area at 85 mm. The rotor iron must be SMC too: a solid steel rotor
loses 73 W in eddy currents at 1728 rpm (efficiency 47 % against 85 %). Best efficiency 86 % (92 %).

Code: `winding.wire` = "awg" (turns and AWG chosen together; `physics.winding.wire_gauge`,
`fit_awg`), the wire in the optimization report and the map; cache keys of specs without it
unchanged. The analytic stand-in (`--dry-run`) does not know the raxial machine yet.
