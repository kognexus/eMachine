# T03: Design vector to motor parameters

Status: done
Depends on: T02

## Why

The optimizer works on a short list of numbers. The mesher needs a complete motor description.
This ticket defines the design variables and the mapping between the two, so that every design
automatically honours the macro inputs.

## Scope

`tfm/design.py`:

- `variables(spec)`: ordered list of design variables with name, type (real or integer) and
  bounds. Variables: `pole_pairs`, `tooth_span`, `leg_width_mm`, `slot_height_mm`,
  `yoke_height_mm`, `magnet_thickness_mm`, `rotor_iron_mm` (back iron or housing thickness),
  `current_density_A_mm2`, plus `bridge_height_mm` for the I-bridge stator and
  `magnet_arc_ratio` for the surface rotor.
- `to_parameters(spec, values)`: full parameter dictionary for the mesher and solver.
- Rules that tie the design to the macro inputs:
  - The stack length is shared by the phases: per-phase width =
    (stack - (phases - 1) * phase spacing) / phases.
  - Slot width = per-phase width - 2 * leg width.
  - Outrunner: outer diameter is the rotor outside. Inrunner: outer diameter is the stator outside.
  - The rotor has two magnet rows with alternate polarity, one under each leg.
  - The coil fills the slot left over after clearance and, for the I-bridge stator, the bridge.
- Iron-thickness limits become the bounds of the variables that are iron thicknesses.

Ampere-turns are the electromagnetic variable. The number of turns is chosen afterwards (T06),
because only the product of turns and current affects the field.

## Acceptance criteria

- [x] For any variable values inside the bounds, the generated machine has exactly the
      specified outer diameter and total stack length.
- [x] Integer variables are rounded and clipped to their bounds.
- [x] The parameter dictionary is accepted by the mesher without change.
- [x] `from_parameters` recovers the variable values from a generated dictionary (round trip).

## Test cases

| ID | Test | Expected |
|---|---|---|
| T03-1 | Outrunner, 80 mm, random designs (50 samples) | Rotor outer diameter = 80 mm for every sample |
| T03-2 | Inrunner, 120 mm, random designs (50 samples) | 2 * (air-gap radius + slot height + yoke) = 120 mm |
| T03-3 | Stack 23 mm, 1 phase | Slot width + 2 * leg width = 23 mm |
| T03-4 | Stack 75 mm, 3 phases, spacing 3 mm | Per-phase width = 23 mm |
| T03-5 | Round trip | `from_parameters(to_parameters(x)) == x` within 1e-9 |
| T03-6 | Variable bounds from limits | Leg and yoke bounds equal the iron-thickness limits |
| T03-7 (slow) | Three random feasible designs through the mesher geometry step | No error, sector volumes positive |

## Result

Completed 2026-10-13.

- `tfm/design.py`: `variables`, `clip`, `to_vector`, `to_values`, `derived`, `to_parameters`, `from_parameters`.
- Tests in `tests/test_t03_design.py`: T03-1 to T03-6 pass (50 random designs each for the two
  diameter rules), T03-7 passes with `TFM_SLOW=1` (three designs through the mesher geometry step).
- Extra tests: integer rounding and clipping, variable override and fixing, a stack too short for
  two legs and a slot, ampere-turns following current density.
- The flux-concentrating rotor adds a variable `magnet_height_mm`; there `magnet_thickness_mm` is
  the spoke width.
- The inrunner has no `rotor_iron_mm` variable: its rotor core fills the space between shaft and magnets.
- The mesher now ignores a `design` section, which stores the variable values inside the parameter file.
