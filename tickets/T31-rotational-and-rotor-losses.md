# T31: Rotational stator loss, rotor eddy-current loss, loaded-field core loss

Status: done
Depends on: T09, B05, T30
Closes: B04

## Why

T30 showed the loss model as the pipeline's clear weakness: against two published SMC prototypes
the computed efficiency was 10 to 13 points too high. The model took alternating loss on the peak
flux density of each stator element, from the no-load field; it left out rotational loss in the SMC,
loss in the rotor (solid mild-steel yoke: about half the measured core loss of the TFM) and the rise
of core loss under load. The user (2026-10-16) asked for these to be added.

## Model

Stator core, per element (following Guo et al., IEEE TMAG 2014, and Zhu & Ramsden 1998):

- B over one electrical period (half-period sweeps completed with B(t + T/2) = -B(t)).
- Every harmonic k is an ellipse; major axis Bmaj and axis ratio R from the cosine and sine vectors.
- Loss of harmonic k: R P_r(Bmaj, k f) + (1 - R)^2 P_a(Bmaj, k f), with
  P_a = k_h f B^alpha + k_e (f B)^2 + k_a (f B)^1.5 and
  P_r = P_hr(B) f + k_er (f B)^2 + k_ar (f B)^1.5 (rotational hysteresis per cycle from a1, a2, a3, Bs).
- Default material: SOMALOY 500 (Guo, Zhu, Zhong, Wu, IEEE TMAG 39(5), 2003): C_ha 0.1402, h 1.548,
  C_ea 1.233e-5, C_aa 3.645e-4; a1 6.814, a2 1.054, a3 1.445, Bs 2.134 T, C_er 2.303e-4, C_ar 0.

Rotor parts (rotor iron, rotor housing, magnets):

- The solver saves the flux density of the rotor parts in the rotor frame, cylindrical components.
- The rotor meshes differ between positions: element-to-element interpolation gave a flat noise
  floor of 0.016 to 0.023 T in every harmonic, which the k^2-weighted eddy formula turned into most
  of the loss (252 W instead of about 34 W on the TFM). The field is therefore averaged over cells of
  1.5 mm in the rotor frame (angular cells a whole fraction of a pole pitch, so that half-period
  sweeps complete exactly with b(x, t + T/2) = -b(x - pole pitch, t)), and the noise floor (median of
  the upper half of the harmonics) is estimated per cell; only harmonics with more than four times
  the floor's power count, less the floor (subtracting alone left the harmonics where the noise
  happens to be high, which dominated the k^2-weighted loss of thin parts such as a Halbach housing).
- Eddy-current loss of harmonic k per m3: c pi^2 t^2 sigma (k f Bmaj_k)^2 / 6 (thin plate of the
  part's thickness t: radial thickness of the rotor core, magnet width or axial length) times the
  skin-effect factor of a plate F(t / delta_k), with delta_k from the incremental permeability of
  the B-H model at the mean steady flux density of the part. No fitted correction (c = 1).
- Kept as a spectrum per part (sum of cell volume x Bmaj_k^2), so the loss follows at any speed.
- Defaults: mild steel 6.0e6 S/m, NdFeB 6.7e5 S/m, housing not conductive unless given.

Loaded field: the efficiency map already solved each load level; the field export and the
validation now take the core loss of the rated point from the loaded sweep.

Thermal: rotor loss heats the rotor (magnet) node; the map, evaluation and export include it.

## Acceptance criteria

- [x] Stator loss per harmonic ellipse with rotational data; alternating-only when a material has none.
- [x] Rotor iron, housing and magnet eddy-current losses, reported separately, in the totals and the
      thermal network.
- [x] Map, evaluation, field export and validation use the new model; cached results invalidated.
- [x] Validation against the two T30 prototypes repeated.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T31-1 | Ellipse axes of harmonics, also tilted in 3D | Exact |
| T31-2 | Rotational hysteresis | 0 at B = 0; 1.5 to 2.2 times the alternating hysteresis at 1 T; falls towards saturation |
| T31-3 | Element loss, alternating and circular | Formulas exact; circle without rotational data = alternating on Bmaj |
| T31-5 | Half-period completion of the stator field | Equal to the full sweep |
| T31-6 | Rotor series over half and full period, cells, spectra, thin-plate loss | Equal; magnets with a constant field lose nothing |
| T31-7 | Skin factor and incremental permeability | 1 at low xi, 3 / xi at high xi, monotonic; Froehlich and measured curve |
| T31-8 | Noise floor | Fundamental kept within 5 %, floor removed |
| T31-9 | Coefficients and loss_at | Consistent; old cached levels work; no conductivity, no rotor loss |
| T31-10 | Specification | rotational null allowed, conductivities validated |
| T31-11 | Thermal | Rotor loss heats the magnets more per W than stator iron loss |
| T31-12 | Eddy widths of the rotor parts | Core thickness and magnet width |

## Result

2026-10-16. Validation (`tfm_validate.py --losses-only` on the saved fields of T30; 24 positions per
period). Percentages against published.

| Quantity | Published | T30 model | T31 model |
|---|---|---|---|
| TFM: stator core, no load | 29 W (authors' FEA) | 15.6 W (-46 %) | 21.0 W (-28 %) |
| TFM: rotor, no load | 34.3 W (authors' calculation) | not modelled | 24.8 W (-28 %) |
| TFM: total, no load | 68.2 W (measured) | 15.6 W | 45.8 W (-33 %) |
| TFM: stator core, rated | 56.5 W (authors' FEA) | not modelled | 34.6 W (-39 %) |
| TFM: rotor, rated | 63.8 W (authors' calculation) | not modelled | 59.9 W (-6 %): yoke 53.5, magnets 6.3 |
| TFM: total, rated | 112 W (measured) | 15.6 W | 94.5 W (-16 %) |
| TFM: efficiency | 80.6 % (measured) | 93.4 % | 84.6 % |
| Claw pole: total, no load | 60 W (measured) | 30.9 W | 43.9 W (-27 %); rotor 3.5 W ("negligible" in the papers) |
| Claw pole: stator core, full load | 81.8 W (authors' FEA) | not modelled | 66.3 W (-19 %) |
| Claw pole: efficiency | 81 % (measured, with inverter) | 90.5 % | 83.1 % |
| Claw pole: output torque, rated | 2.65 N m (measured) | 2.60 N m | 2.39 N m (-10 %) |

The efficiency error fell from +10 to +13 points to +2 to +5 points (the measured TFM value
excludes the inverter; the claw-pole value includes it). The stator loss stays 20 to 40 % below the
authors' FEA with their rotational model; the rotor loss without any fitted factor lands within
6 to 28 % of the authors' fitted calculation.

Still not modelled: mechanical and inverter loss, current harmonics of the six-step drive, end
effects of the rotor eddy currents, eddy currents in the field solution itself.

### The user's machine (T28) with the new loss model

`runs/user_tr48/map` and `runs/user_tr48/paraview` re-run 2026-10-16 (the T30 model's results are kept
in `runs/user_tr48/before_t31/`):

| Quantity | T30 model | T31 model |
|---|---|---|
| Highest efficiency | 91.2 % at 3965 rpm, 0.75 N m | 86.4 % at 3524 rpm, 1.02 N m |
| Highest continuous output | 223 W at 3613 rpm | 124 W at 2027 rpm |
| Continuous operation | up to about 4400 rpm | up to about 3000 rpm: above it the stator core loss alone exceeds the temperature limits of the (assumed) thermal network |
| Torque, speed and current limits | unchanged | unchanged |

Stator core loss of the three phases: 6.7 W at 1000 rpm, 15.7 W at 2000 rpm, 32.6 W at 3436 rpm,
48.2 W at 4500 rpm (13 A). Magnets: 0.2 to 3.4 W. The Halbach rotor has no iron; its housing is
taken as non-conductive. Were it aluminium (3.5e7 S/m), it would add 2.3 / 8.7 / 24 / 39 W at the
same speeds (estimate from the saved spectra).

Slow tests T09, T17, T18, T29 pass; all fast tests pass.
