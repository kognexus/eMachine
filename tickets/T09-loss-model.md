# T09: Loss model: copper and iron

Status: done
Depends on: T06, T07

## Why

Losses are an optimization objective and the heat source of the thermal model.

## Scope

`tfm/losses.py`:

- Copper loss per phase: RMS current squared times resistance at the winding temperature.
  Expressed in ampere-turns it does not depend on the number of turns.
- Iron loss in the stator core from the field solution:
  - The stator mesh differs slightly between rotor positions, so the core field of every
    position is resampled onto the element centroids of the first position (nearest centroid).
  - Peak flux density of each reference element over the electrical cycle (half-period samples
    cover the full cycle because the field reverses).
  - Loss density = k_h * f * B^alpha + k_e * f^2 * B^2 in W/kg, times density and volume,
    summed over the core and scaled from the sector to the ring.
  - Coefficients, exponent and density come from `materials.stator_core` in the specification.
- Totals for the machine: per-phase values times the number of phases.
- Not included, and stated in the output: rotor iron loss, magnet eddy-current loss, mechanical
  loss (see B04).

## Acceptance criteria

- [x] Copper loss matches I^2 R and is independent of the number of turns.
- [x] A uniform field of known amplitude gives the hand-calculated iron loss.
- [x] Iron loss follows the stated frequency dependence.
- [x] Resampling returns the field unchanged when both point sets are identical, and tolerates
      different point counts.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T09-1 | Copper loss, 200 ampere-turns peak, known coil | Equals rho * L_turn * (NI_rms)^2 / (area * fill) within 1e-9 |
| T09-2 | Synthetic core: 1000 elements of 1 mm3, B = 1 T * cos, 100 Hz, k_h = 0.09, alpha = 1.75, k_e = 2.5e-5, density 7450 | 9.25 W/kg times mass, within 1e-6 relative |
| T09-3 | Same at 200 Hz | Hysteresis part doubles, eddy part quadruples |
| T09-4 | Resample with identical point sets | Field identical |
| T09-5 | Resample 1000 random points onto a shifted copy (shift 1 % of spacing) | Each point maps to its own shifted twin |
| T09-6 (slow) | Iron loss of the reference design from a coarse analysis | Positive, finite, below 100 W at 300 rpm |

## Result

Completed 2026-10-13.

- `tfm/losses.py`: copper loss, nearest-centroid resampling, peak core field over the cycle, iron loss.
- Tests in `tests/test_t09_losses.py`: T09-1 to T09-5 pass, plus a test that the peak is taken over
  positions when element order differs between files.
- T09-6 is covered by the slow test T11-5: the reference design at 300 rpm (90 Hz) has 1.25 W of
  stator iron loss per phase, with a core mass of 0.174 kg.
- Finding: with the linear core material the field reaches 2.5 T in small corner regions of the
  reference design (5 % of the core volume is above 1.6 T, 1.2 % above 2.0 T). Real material
  saturates there, so iron loss and torque are somewhat overestimated. The loss result now also
  reports the flux density that 95 % of the core volume stays below, and a limit on it was added
  to the specification (`limits.max_core_flux_density_T`, default 1.8 T). Ticket B01 removes the cause.
- Loss coefficients are assumed values for a soft magnetic composite and must be replaced by the
  data of the real material.

### Correction, 2026-10-13 (ticket B05)

The iron losses and core flux densities above were computed from Elmer's smoothed nodal flux
density, which loses about a fifth of the flux in thin iron parts. Since B05 the element field
is used. Iron loss is about 25 % higher than stated above (reference design, saturating core:
0.93 W before, 1.16 W now). Torque, flux linkage, voltages, turns and copper loss are unchanged.
