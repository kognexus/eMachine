# B05: Iron loss from the element flux density

Status: done
Depends on: T09

## Why

Found while preparing the ParaView export (T18). Elmer writes two flux density fields: the
element field, which is the curl of the solution, and a nodal field smoothed over neighbouring
elements. The loss model (T09) and the saturation check read the smoothed field. In thin iron
parts with one or two elements across, smoothing mixes in the low values at the surface.

Measured on the reference design at the aligned position without current:

| Field | Flux through the yoke of one core / coil flux per core | Mean flux density in the core |
|---|---|---|
| smoothed nodal field (used so far) | 0.80 | 0.654 T |
| element field | 0.96 | 0.760 T |

The coil flux comes from the vector potential and was validated against torque in T07, so it is
the reference. About 4 % of the coil flux is leakage outside the core, so 0.96 is what a correct
field should give. The smoothed field loses a fifth of the flux. Iron loss rises with the power
1.75 to 2 of flux density, so earlier iron losses are about 25 % too low.

Not affected: torque (computed by the solver from the solution), coil flux, voltages, turns and
copper loss.

## Scope

- `tfm_pipeline.save_core_field` uses the element field.
- Cached results made with the old field must not be reused: the cache key gets a model version.
- The ParaView export (T18) shows the same field as the loss model uses.
- Earlier results are marked as affected in their tickets (T09, T11, B01).

## Acceptance criteria

- [x] The flux through the yoke computed from the saved core field equals the coil flux per core
      within 8 %.
- [x] Results cached before this change are not read.
- [x] Slow tests of T07, T09, T11 and B01 pass with the corrected field, or their criteria are
      amended in the open with the measured numbers.

## Test cases

| ID | Test | Expected |
|---|---|---|
| B05-1 | `flux_density_name` with both fields present, and with only the nodal field | Element field preferred; nodal field as fallback |
| B05-2 | Cache key of a design | Differs from the key without the model version |
| B05-3 (slow) | Reference design, aligned, no current: yoke flux from `core_field.npz` against coil flux per core | Ratio between 0.92 and 1.00 |
| B05-4 (slow) | Iron loss of the reference design, old field against new field | New loss is higher; ratio recorded in the result |

## Result

Completed 2026-10-13.

- `tfm_pipeline.flux_density_name` picks the element field; `save_core_field` and the ParaView
  export both use it.
- `tfm/evaluate.py`: `MODEL_VERSION = 2` is part of the cache key, so results cached before the
  change are not read. The map's stored field results carry the same version.
- Tests in `tests/test_b05_iron_loss_field.py`: B05-1 and B05-2 pass; B05-3 and B05-4 pass with
  `TFM_SLOW=1`.
- Measured in B05-3 and B05-4 (reference design, aligned, no current): yoke flux / coil flux per
  core = 0.959 with the element field (0.80 with the smoothed field); hysteresis loss new / old = 1.25.
- Reference design after the change (fast fidelity, 300 rpm): torque 0.868 Nm (unchanged), iron
  loss 1.16 W per phase (0.93 W before), total loss 5.40 W (5.17 W before), efficiency 83.5 %.
- The slow tests of T07, T09, T11 and B01 pass unchanged with the corrected field. No criterion
  had to be amended.
- Consequence for earlier runs: `runs/opt_example` and `runs/opt_example_saturation` hold the old
  iron losses. Their designs are still valid seeds; `runs/opt_seeded` re-evaluated all of them
  with the corrected field.
