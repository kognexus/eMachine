# T04: Geometric feasibility and limit checks

Status: done
Depends on: T03

## Why

Many random designs cannot be built: cores collide at the hub, the coil does not fit, an iron
section is too thin. These must be rejected in microseconds, before any meshing.

## Scope

`tfm/feasibility.py`: `check(spec, values)` returns a list of constraint results. Each has a
name, a value, a limit and a normalised violation (0 when satisfied). Checks:

- Iron thickness within limits: leg, yoke, core thickness along the motion direction, I-bridge
  height, rotor iron.
- Slot width and coil height large enough to hold a coil.
- Neighbouring stator cores do not overlap at the end away from the air gap.
- Inner stator: hub stays outside the bore diameter. Inrunner: rotor core stays outside the shaft.
- Magnets fit: positive rotor iron, spoke magnets narrower than the pole.
- Pole pairs within limits.

The total violation is the sum of the normalised violations, used by the optimizer to rank
infeasible designs.

## Acceptance criteria

- [x] A design is feasible exactly when every violation is zero.
- [x] The user's Onshape motor is reported infeasible because of the hub collision.
- [x] Each violation is continuous in the design variables, so the optimizer can move towards
      feasibility.
- [x] One check takes less than 1 ms.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T04-1 | Reference feasible design | No violations |
| T04-2 | Tooth span 0.8, 18 pole pairs, slot height 17 mm, radius 35 mm (the user's motor) | `core_overlap` violated |
| T04-3 | Leg width 1.5 mm with iron limits 2 to 10 mm | `iron_leg` violated |
| T04-4 | Leg width so large that the slot is narrower than the minimum | `slot_width` violated |
| T04-5 | Slot height larger than the radius allows | `bore_clearance` violated |
| T04-6 | Violation grows as the design moves further out of bounds | Monotonic |
| T04-7 | 10 000 checks | Under 10 s in total |

## Result

Completed 2026-10-13.

- `tfm/feasibility.py`: `check`, `violations`, `total_violation`, `is_feasible`.
- Tests in `tests/test_t04_feasibility.py`: T04-1 to T04-7 pass.
- One check takes about 9 microseconds (measured over 10 000 calls).
- T04-2 confirms the user's Onshape motor fails `core_overlap`: the cores are 4.89 mm thick with
  4.52 mm of room at the hub.
- Extra tests: iron limits applied to the core thickness at 4 and 32 pole pairs; inrunner cases
  (U-cores alone cannot touch at the pole faces, with I-bridges a span of 0.95 violates the gap);
  about 1 % or more of random designs are feasible, so the space is not empty.
- Added `limits.min_core_gap_mm` (default 0.5 mm) to the specification.
- The upper iron limit is not applied to the inrunner rotor core, which is a solid ring down to the shaft.
