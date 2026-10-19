# T46: Winding description: span, layers, pitch, slot class (FSCW, FSDW, ISDW)

Status: done
Depends on: T43

## Why

The user (2026-10-16) asked for FSCW and FSDW as winding types. Fractional or integral slot is not
a choice of its own: it follows from q = Q / (2 p m), while the coil span (concentrated,
distributed, ring) is chosen. Today `machine.winding` is only `concentrated` or `distributed`,
distributed coils are always full pitch, layouts are always double layer, and nothing names the
winding in the reports or lets the optimizer stay within one slot class.

## Scope

- Spec section `winding`: `span` (`concentrated`, `distributed`, `ring`), `layers` (1, 2),
  `pitch_slots` (`null` or a number: short pitching), `slot_class` (`any`, `integral`,
  `fractional`). `machine.winding` stays readable (T43 alias). TFM: `ring` only; SRM:
  `concentrated` only.
- `machines/rfm/winding_layout.py`: single-layer layouts (each slot one coil side; only for even
  coil counts per phase), coil pitch from `pitch_slots`; pitch, distribution and fundamental winding
  factor reported separately.
- Geometry check `slot_class`: designs whose q is of the other class are infeasible (the slot count
  is fixed per spec, the pole pairs are a variable, so the check removes pole numbers).
- Label FSCW, FSDW, ISDW or ring, with q, layers and k_w1, in `describe`, the optimization report,
  the map report and the ParaView summary.

## Acceptance criteria

- [x] Winding factors equal the textbook values (table below) within 0.001.
- [x] Single-layer and short-pitched layouts balanced (phase phasors 360/m apart, equal magnitude).
- [x] `slot_class` = `fractional` with 12 slots rejects 2 pole pairs (q = 1) and accepts 5 (q = 0.4).
- [x] The reference RFM (12s10p, double layer, concentrated) gives the same results as before (T41
      tests pass unchanged).
- [x] Labels in the reports.

## Test cases

| ID | Winding | Expected |
|---|---|---|
| T46-1 | 12 slots, 10 poles, concentrated, 2 layers | FSCW, q = 0.4, k_w1 = 0.933 |
| T46-2 | 36 slots, 6 poles, distributed, full pitch | ISDW, q = 2, k_d1 = 0.966, k_p1 = 1, k_w1 = 0.966 |
| T46-3 | Same, pitch 5 slots (5/6) | k_p1 = 0.966, k_w1 = 0.933 |
| T46-4 | 18 slots, 4 poles, distributed, pitch 4 | FSDW, q = 1.5, k_d1 = 0.960, k_p1 = 0.985, k_w1 = 0.945 |
| T46-5 | 12 slots, 10 poles, concentrated, 1 layer | FSCW, k_w1 = 0.966; every slot holds one coil side |
| T46-6 | `slot_class` check with 12 slots, pole pairs 2..7 | integral: 2 only (q = 1); fractional: 4, 5, 7 balanced, others rejected as before |
| T46-7 | Old spec with `machine.winding` | same layout as `winding.span` |
| T46-8 | `describe` of the reference RFM | "FSCW, q = 0.4, 2 layers, pitch 1 slot, k_w1 = 0.933" (pitch added while building) |

## Result

2026-10-16. Spec section `winding`: `span`, `layers`, `pitch_slots`, `slot_class` (old
`machine.winding` is read as `winding.span`; the cache view writes it back, so keys are unchanged).
`machines/winding_layout.py`: `layout(slots, p, phases, span, layers, pitch)`, single layer (half of
the coils, each slot one side, drawn in both halves with `share` 0.5, which the mesher, the 2D
solver, the analytic stand-in and the field export apply to current and flux), `pitch_factor`,
`distribution_factor` (double layer only: a single layer has no unique split), `label`,
`describe`, `text`. `SlottedMachine`: coils and coil area per layer count, turn length from the
pitch, the check `slot_class`, `winding_description`. `describe.winding_text` in the optimization
report (picks), `map.md` and the ParaView summary: "FSCW, q = 0.4, 2 layers, pitch 1 slot, k_w1 =
0.933" for the reference RFM, "ring winding" for a TFM.

Tests (`tests/unit/machines/test_winding_description.py`, 10, one slow): the factors of the table
within 0.001; single-layer layouts balanced with one side per slot; slot classes for 12 slots
(integral: 2 pole pairs; fractional: 4, 5, 7); old key; describe text; single-layer dimensions
(half the coils, twice the area and ampere-turns). Slow, field solution: the single-layer 12s10p
gives 0.966 / 0.933 of the torque of the double layer per ampere-turn of the phase, within 2 %.

Full slow suite after T43 to T47: 366 tests pass (1 skipped) in 1374 s.
