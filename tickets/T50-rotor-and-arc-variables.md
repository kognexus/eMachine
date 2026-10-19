# T50: Rotor layouts and arcs without ratios; TFM tooth arc and claw tip

Status: done
Depends on: T48, T49

## Why

`docs/parameters.md`, rules 2 and 3.

## Scope

- Arcs in electrical degrees: `magnet_arc_el_deg` (RFM, AFM surface; TFM surface and axial ring),
  `tooth_arc_el_deg` (TFM, was `tooth_span`), `rotor_tooth_arc_el_deg` (TFM SRM).
- `interior`: `magnet_length_mm` (each bar of the V) instead of `magnet_width_ratio`.
- `flux_barrier`: `barrier_width_mm` instead of `insulation_ratio`, with a check that the iron
  between the barriers keeps the minimum iron thickness; `flux_barrier_pm`: `magnet_width_mm`
  instead of `magnet_fill_ratio`.
- SRM: `rotor_pole_arc_deg`, `rotor_pole_height_mm` (was a CAD constant of 4 mm); the stator pole
  arc is derived from the slot width; checks of Lawrenson's feasible region.
- TFM claw pole: `claw_tip_height_mm` (was max(minimum iron, 0.5 x root)).
- Old values converted (`standard_values`); TFM cache keys and field keys unchanged for designs
  written with the old names (`legacy_values` in the keys).

## Acceptance criteria

- [x] TFM: `tooth_arc_el_deg` = 180 x `tooth_span`, same parameters, same golden data
      (characterization, cache keys of the TFM specs unchanged).
- [x] Each RFM layout: middle design builds its parameters, checks name the new variables.
- [x] SRM checks, 8/6 machine (m = 4, N_r = 6): self-starting needs min(beta_s, beta_r) >= 360 /
      (4 x 6) = 15 deg, room between the rotor poles beta_s + beta_r <= 60 deg: 14/16 deg and 30/32
      deg infeasible, 20/22 deg feasible.
- [x] Old run files (`seeds.json`, design files with `tooth_span`) still read.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T50-1 | TFM design with `tooth_span` 0.725 | same `to_parameters` as `tooth_arc_el_deg` 130.5 |
| T50-2 | Cache key of the TFM specs | as in golden/cache_keys.json |
| T50-3 | Claw pole without `claw_tip_height_mm` | tip = max(minimum iron, 0.5 root) |
| T50-4 | SRM Lawrenson checks | as above |
| T50-5 | Barrier width too large for the barriers per pole | `barrier_iron` violated |

## Result

2026-10-17. Variables: `magnet_arc_el_deg` (RFM, AFM surface 108..180; TFM surface 108..180, axial
ring 72..180), TFM `tooth_arc_el_deg` (90..171), `claw_tip_height_mm`, `rotor_tooth_arc_el_deg` (TFM
SRM); `interior`: `magnet_length_mm` with the checks `magnet_width` (the V within its pole) and
`rotor_core`; `flux_barrier`: `barrier_width_mm` with `barrier_iron` (the pitch of the barrier
circles, as the CAD draws them, less the barrier >= minimum iron); `flux_barrier_pm`:
`magnet_width_mm`; `salient` (RFM, AFM): `rotor_pole_arc_deg`, `rotor_pole_height_mm` (was a CAD
constant), checks `stator_pole_arc`, `rotor_pole_arc` (>= one stroke 360 / (m N_r)), `pole_arcs`
(sum <= 360 / N_r), the stator pole arc derived from the slot width (`stator_pole_arc_deg`);
`stator_pole_arc_ratio` dropped.

Old names: `standard_values` is applied where designs come in (clip, derive, checks, geometry,
picks, seeds, `onshape`, `compare`); an old name given explicitly wins over a new one in the same
dictionary. Cache and field keys see TFM designs in the old names (`evaluate.keyed_values`), so
the 13 recorded TFM keys are equal whether the design is written in the old or the new names.
Characterization data compared in the recorded names (`cases.recorded_values`,
`recorded_variables`; the claw tip of the cp middle designs set by the old rule): unchanged.

Tests (`tests/unit/machines/test_dimensions.py`): T50-1, 3, 4, 5, interior, dropped ratios; the
cache-key test with both names.
