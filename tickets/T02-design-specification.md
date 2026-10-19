# T02: Design specification file

Status: done
Depends on: T01

## Why

The user states the problem once, in one file: the macro inputs, the limits, the operating
point, the material data and what to optimise. Everything else reads from it.

## Scope

`tfm/spec.py` loads and validates a JSON specification with these sections:

- `machine`: `configuration` (inrunner or outrunner), `stator_type` (u or ui), `rotor_type`
  (surface, halbach, flux_concentrating), `outer_diameter_mm`, `stack_length_mm` (all phases
  together), `phases` (1 or 3), `phase_spacing_mm`, `air_gap_mm`, `bore_diameter_mm`.
- `operating_point`: `speed_rpm`, `ambient_C`.
- `limits`: `iron_thickness_mm` [min, max], `pole_pairs` [min, max], `bus_voltage_V` [min, max],
  `max_current_A`, `max_winding_temp_C`, `max_magnet_temp_C`, `max_current_density_A_mm2`.
- `variables`: optional override of any design-variable range, or a single value to fix it.
- `materials`, `winding`, `thermal`: physical data with documented defaults.
- `objectives`: any of `max_torque`, `min_losses`, `min_ripple`.
- `optimizer`, `fidelity`: run settings.

Missing values fall back to defaults. Unknown keys and invalid values are rejected with a
message that names the key.

Interpretation recorded here: the bus-voltage range means the drive can supply any voltage in
that range, so a design is acceptable when the voltage it needs is at most the upper bound.
The lower bound is reported but does not reject a design. `max_current_A` is the peak phase
current.

## Acceptance criteria

- [x] `load_spec(path)` returns a fully populated specification with defaults applied.
- [x] Unknown sections or keys raise `SpecError` naming the offending key.
- [x] Out-of-range values raise `SpecError` (for example phases = 2, min above max).
- [x] An example file `spec_example.json` covers the user's case: outrunner, U-core with
      I-bridge, 80 mm outer diameter, 23 mm stack, iron 2 to 10 mm, pole pairs 4 to 32,
      bus 12 to 48 V, current cut-off 15 A.
- [x] Every limit in the user's request is a parameter in the file, not a constant in code.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T02-1 | Load `spec_example.json` | No error; limits equal the values above |
| T02-2 | Empty specification `{}` | Loads with defaults for every section |
| T02-3 | Unknown key `machine.colour` | `SpecError` mentioning `machine.colour` |
| T02-4 | `phases = 2` | `SpecError` |
| T02-5 | `limits.pole_pairs = [10, 4]` | `SpecError` (min above max) |
| T02-6 | Override `variables.tooth_span = [0.6, 0.8]` and `variables.magnet_thickness_mm = 3` | Range replaced; fixed variable has equal bounds |
| T02-7 | `stator_type = "c"` | `SpecError` saying the type is not supported yet (see B02) |

## Result

Completed 2026-10-13.

- `tfm/spec.py` with `DEFAULTS`, `load_spec` and `SpecError`; example file `spec_example.json`.
- Tests in `tests/test_t02_spec.py`: T02-1 to T02-7 pass, plus two extra tests (nine further invalid
  values are rejected; a nested material override keeps the other defaults).
- Added while implementing: `winding.coil_margin_mm`, the distance of the coil from the pole-face
  plane or from the top of the I-bridge.
- The example uses a 0.5 mm air gap. The Onshape model has 0.3 mm. This is one line in the file.
