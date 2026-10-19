# T74: Gear TFM at 85 mm and 150 rpm: concept screening, optimization runs, report

Status: done
Depends on: T70 to T73

## Why

Measure each concept of the user's list (T70) and the tooth tips (T73) on the gear TFM at 150 rpm,
then optimise the geometry for efficiency and torque, and say how close the 90 % target comes.

## Method

- Peak efficiency over load at one speed. Torque k J, copper loss c J², other losses P0 (iron and
  rotor eddy currents, nearly constant at light load):

  eta_best = 1 / (1 + 2 sqrt(P0) / (omega k_m)), reached where copper loss = P0, with the motor
  constant k_m = T / sqrt(P_cu).

  90 % needs omega k_m / sqrt(P0) >= 18; at 150 rpm (omega = 15.7 /s): k_m / sqrt(P0) >= 1.15.
- Screening (`scripts/screen.py`): every variant on the baseline geometry, one field solution at
  3 A/mm², fast mesh, 6 positions per half period. T22 found the fast mesh within 3 % for torque and
  losses. Ripple is not reliable at 6 positions.
- Optimization (`scripts/make_specs.py`, `run_chain.sh`): every geometry variable free, 12 to 24 pole
  pairs (at most 48 poles), current density 0.5 to 5 A/mm² with two load levels. Objectives
  `max_efficiency` and `max_torque`; population 12, 3 generations. Runs: spoke rotor, Halbach with
  tooth tips, Halbach (current concept, as the reference), spoke with tooth tips.
- Report (`scripts/report.py`): trade-off per run, peak efficiency of every geometry from its
  designs at several current densities, and the iron loss the 90 % target would need.

## Acceptance criteria

- [x] Every concept screened, or the reason why not.
- [x] Optimization runs finished; trade-off and best geometry per run.
- [x] Best designs verified on the medium mesh (12 positions per half period; amended from 24 to save time on the shared computer).
- [x] Report: highest efficiency at 150 rpm, its torque, the torque range above 90 % (none), and
      what limits the efficiency (`gear-tfm-150rpm/report/report.md`).

## Test cases

| ID | Test | Expected |
|---|---|---|
| T74-1 | `scripts/screen.py` on all variants | A record per variant (or a stated failure) |
| T74-2 | `scripts/report.py` on the runs | summary.json, geometries.csv, efficiency_torque.svg |

## Result

### Screening (2026-10-18, baseline geometry: 24 pole pairs, tooth arc 144 deg, legs 2 mm, slot 5 x 10 mm, yoke 5 mm, magnets 2 mm)

| Variant | Torque at 3 A/mm², Nm | k_m, Nm/√W | Iron W | Rotor W | Peak eta | at Nm | B p95, T | Ripple (6 pos.) |
|---|---|---|---|---|---|---|---|---|
| baseline (user's machine at 85 mm, Halbach 2 segments) | 0.404 | 0.281 | 0.79 | 0.00 | 71.2 % | 0.251 | 1.26 | 7 % |
| thin yoke 2 mm (slot unchanged) | 0.377 | 0.263 | 0.79 | 0.00 | 69.8 % | 0.235 | 1.50 | 3 % |
| Halbach 4 segments (T71) | 0.397 | 0.277 | 0.84 | 0.00 | 70.3 % | 0.254 | 1.35 | 3 % |
| magnet pockets, 1 mm overhang (T71) | 0.329 | 0.230 | 0.67 | 0.00 | 68.7 % | 0.189 | 1.08 | 5 % |
| surface rotor, alternate N/S (item 3) | 0.476 | 0.331 | 0.94 | 0.25 | 70.4 % | 0.361 | 1.24 | 5 % |
| spoke rotor, magnets in slots (item 1) | 0.623 | 0.446 | 1.18 | 0.26 | **74.5 %** | 0.534 | 1.57 | 31 % |
| tooth tips 3.5 x 1.5 mm (T73) | 0.629 | 0.491 | 2.17 | 0.01 | 72.3 % | 0.723 | 1.67 | 8 % |
| tips + Halbach 4 | 0.635 | 0.495 | 2.16 | 0.00 | 72.6 % | 0.728 | 1.71 | 7 % |
| spoke + tips | 0.627 | 0.505 | 2.14 | 0.25 | 72.0 % | 0.779 | 1.68 | 6 % |
| rotor step skew 20 deg el, 2 steps (T72) | 0.370 | 0.258 | 0.79 | 0.00 | 69.4 % | 0.230 | 1.27 | 4 % |

Findings:

1. The baseline field: the yoke runs at 0.17 T on average (63 % of the iron, 12 % of its loss), and
   the tooth tips at about 1.55 T. Only about 40 % of the tooth flux links the coil: tooth-to-pole
   leakage at the narrow (4.9 mm) pole pitch, and the magnet over the slot.
2. Tips and the spoke rotor raise torque by 55 %. The iron loss rises faster, though: hysteresis
   goes as B^1.55, so sqrt(P0) grows as B^0.78 while k_m grows as B. The peak efficiency gains only
   1 to 3 points, but at 2 to 3 times the torque.
3. Magnet pockets save a third of the magnet, but lose 19 % of the torque. The magnet over the slot
   feeds the teeth through fringing.
4. More Halbach segments do not help at this pole pitch (segments 1.2 mm wide).
5. Skew lowers torque by 8 % and does not raise efficiency, as expected (T72).
6. 90 % is far: the baseline has k_m / sqrt(P0) = 0.31 against the 1.15 needed, the spoke rotor 0.37.

First runs of the tips and spoke variants failed and were fixed (T73: stray trimming cylinder;
spoke: hub taken for a magnet, CHANGELOG).

### Iron-cobalt SMC (user, 2026-10-18)

Assumed material (no data sheet): saturation polarisation 2.2 T instead of 1.9 T, the same permeability
and loss per kg at the same flux density as the default SMC (`scripts/make_specs.py`, `FE_CO_SMC`).
The two optimization runs first started for it were stopped. Re-solving the screened designs answers
the question in minutes (`runs/screen_feco.log`):

| Design | Material | Torque 3 A/mm² | Peak eta at 150 rpm | at Nm | Torque 10 A/mm² |
|---|---|---|---|---|---|
| spoke | Fe SMC | 0.623 Nm | 74.5 % | 0.53 | 1.93 Nm |
| spoke | Fe-Co SMC | 0.664 Nm (+7 %) | 74.7 % | 0.60 | 2.08 Nm (+7 %) |
| tooth tips | Fe SMC | 0.629 Nm | 72.3 % | 0.72 | 1.99 Nm |
| tooth tips | Fe-Co SMC | 0.689 Nm (+10 %) | 73.1 % | 0.83 | 2.19 Nm (+10 %) |

(The peak efficiencies printed for the 10 A/mm² solutions in the log extrapolate from a saturated point
and are not used.) Fe-Co gives 7 to 10 % more torque, but its iron loss rises with the flux, so the
peak efficiency moves by less than one point.

### Optimization runs (fast mesh, 6 positions, population 12, 3 generations; cut from 5 on the shared computer)

| Run | Feasible designs | Best efficiency | at torque | Iron loss factor needed for 90 % |
|---|---|---|---|---|
| opt_halbach | 237 | 74.3 % | 0.31 Nm | 0.08 |
| opt_tips | 207 | 74.6 % | 0.81 Nm | 0.10 |
| opt_spoke | 183 | 76.7 % | 0.49 Nm | 0.12 |
| opt_spoke_tips | 210 | 74.9 % | 1.10 Nm | 0.11 |

Verification (`scripts/verify.py`, medium mesh, 12 positions, own current density):
opt_spoke 0.415 Nm, 74.0 % (fast mesh 0.489 Nm, 76.7 %); opt_spoke_tips 1.065 Nm, 73.9 % (fast 1.099 Nm,
74.9 %). The fast mesh overstates the spoke rotor by 15 %.

Conclusion: 90 % at 150 rpm is out of reach in this envelope with the default SMC loss data. The best is
about 74 %, at 1.07 Nm with the spoke rotor and tooth tips. Report: `gear-tfm-150rpm/report/report.md`.
T74-1 and T74-2 pass (scripts ran; report files written).
