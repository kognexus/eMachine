# T30: Validation against published TFM prototypes

Status: done
Depends on: T07, T09, T22, T24

## Why

The user (2026-10-15) asked whether the pipeline gives realistic results, and to pick two designs
from Table 2 of the review (Kaiser & Parspour, IEEE Access 2022) and simulate them under the
conditions the papers give. Of the Table 2 rows, only row 5 (Guo et al. 2006) has open-access
geometry, winding and measurements; the other rows rest on Shaker theses or paywalled papers
(literature search 2026-10-15). The user chose the claw-pole sibling of row 5 from the same group
(UTS SMC claw-pole motor, Table V of the row-5 paper, documented in 11 open papers) as the second
design.

## Work

1. `tfm_validate.py`: runs a case file through the field solver the way the papers measured:
   no-load sweep (flux per turn, back-EMF constant, cogging torque of one phase and of all phases),
   inductance with the magnets switched off, torque with sinusoidal current in phase with the induced
   voltage at the rated rms current, coil resistance from the mean turn length, no-load core loss
   from the field. Writes `results.json`, `waveforms.csv` and `report.md` (published against
   computed). Variants in the case file give sensitivity runs.
2. `validation/guo2006/case.json` (TFM, toothed ring with aligned teeth, two magnet rows) and
   `validation/guo_clawpole/case.json` (claw pole). Each value is tagged with its source; every
   assumption is listed under `notes.assumed`.
3. Mesher option `claw_full_discs`: two discs with L-shaped claws (continuous disc below the claw
   level, a rim tooth only under the disc's own claws, continuous yoke), as the SMC claw-pole
   stators are built. Without it the claw-pole core stays the O-frame of the Onshape feature.
4. Loss model: optional excess-loss term `k_anomalous (f B)^1.5`, for the published SOMALOY 500 fit
   (Guo, Zhu, Zhong, Wu, IEEE TMAG 39(5), 2003), used in both cases.

## Acceptance criteria

- [x] Two published machines modelled from their papers, assumptions listed.
- [x] Back-EMF, cogging, inductance, resistance, torque at rated current, core loss and efficiency
      compared with the published values.
- [x] Sensitivity to the unpublished dimensions.
- [x] Conclusions on what the pipeline predicts well and what it does not.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T30-1 | Fundamental and three-phase sum | Amplitude and phase exact; 2nd harmonic cancels, 6th adds |
| T30-2 | Resistance of the row-5 coil | Mean turn radius 29.75 mm, within 15 % of 0.305 ohm |
| T30-3 | Row-5 case file | Radial build 9.5 + 10 + 20.5 = 40, stack 31, magnets 9 mm, arc 12 deg |
| T30-4 | Comparison rows | Scale, error, missing keys left out |
| T30-5 | Excess-loss term | Adds k_a (f B)^1.5 |
| T30-6 | Claw-pole case file | Radial build 40 - 11 - 10 - 10 = 9, stack 31, claw gap 4.2 mm, resistance within 15 % |
| T30-7 (slow) | L-shaped claws | Disc iron under its own claw, none under the other disc's claw, continuous below the claws, claw head 2.65 mm from the other disc |

## Result

2026-10-15. 24 rotor positions per electrical period, about 120 000 elements per sector, about
17 minutes per case on 6 cores. Percentages are computed against published.

### Row 5: Guo et al. 2006, SMC TFM, 640 W at 1800 rpm

Tooth height above the side discs not published: 10 mm (base), 6 and 14 mm (variants).

| Quantity | Published | Kind | 6 mm | 10 mm | 14 mm |
|---|---|---|---|---|---|
| Back-EMF constant | 0.244 V s | measured | +7.1 % | +14.3 % | +15.0 % |
| No-load flux per turn, peak | 0.28 mWb | authors' FEA | +6.2 % | +13.2 % | +13.9 % |
| Cogging, three stacks | 0.32 N m | measured | -3.6 % | -1.1 % | -0.2 % |
| Cogging, one stack | 1.07 N m | authors' FEA | -51 % | -63 % | -64 % |
| Inductance | 6.53 mH | measured | +18.7 % | +13.4 % | +11.4 % |
| Resistance, 20 C | 0.305 ohm | measured | +7.4 % | +7.4 % | +7.4 % |
| Torque at 5.5 A | 4.03 N m | derived (3 k I) | +6.0 % | +12.8 % | +13.5 % |
| Stator core loss, no load | 29 W | authors' FEA | -50 % | -46 % | -45 % |
| Output torque | 3.4 N m | measured | +22 % | +30 % | +31 % |
| Efficiency | 80.6 % | measured | 93.1 % | 93.4 % | 93.4 % |

### Claw pole: Guo et al. 2003-2007, SMC claw-pole motor, 500 W at 1800 rpm

| Quantity | Published | Kind | Claws 10 mm (base) | Claws 7 mm |
|---|---|---|---|---|
| Back-EMF constant | 0.2552 V s | measured | -4.0 % | +12.4 % |
| No-load flux per turn, fundamental | 0.480 mWb | authors' FEA | -3.8 % | +12.6 % |
| Cogging, three stacks | 0.33 N m | measured | +39 % | +41 % |
| Cogging, one stack | 0.75 N m | authors' FEA | +73 % | +59 % |
| Inductance | 5.79 mH | measured | +39 % | +28 % |
| Resistance, room temperature | 0.225 ohm | measured | +2.4 % | +16 % |
| Torque at 4.1 A | 3.19 N m | authors' calculation | -12.4 % | +5.9 % |
| Core loss, no load | 60 W | measured | -49 % | -42 % |
| Output torque at rated point | 2.65 N m | measured | -1.9 % | +19 % |
| Efficiency | 81 % (with inverter) | measured | 90.5 % | 91.2 % |

Claw-pole geometry history (kept under `validation/guo_clawpole/variants/`): with the discs as full
rings up to the air gap, or with O-frames that put a leg on both discs at every pole, iron sat
2.65 mm from every claw tip; the inductance came out at 11.2 and 10.9 mH (about twice the
measurement) and the back-EMF 11 to 17 % high. The papers' figures show L-shaped claws on discs
with 10 rim teeth; with those the back-EMF is within 4 %.

### Conclusions

- Flux, back-EMF and torque: within 4 to 14 % of measurement once the geometry is right, and the
  error follows the unpublished dimensions (tooth height, claw thickness) as much as the solver.
  Field-solved torque and the torque from the back-EMF agree within 1 % for the TFM (energy
  balance); for the claw pole the loaded torque is 7 % below 3 k I (armature reaction and
  saturation at 4.1 A).
- Cogging of all three phases: within 4 % for the TFM; 21 to 39 % high for the claw pole, whose
  cogging depends on claw corners that are not published. Cogging of one phase differs much more
  (its 2nd harmonic, which cancels over three phases, depends on the tooth shape).
- Inductance: 11 to 19 % high for the TFM, 28 to 39 % high for the claw pole. The leakage paths
  between claws and teeth are sensitive to their exact shape.
- Resistance: within 2 to 7 % from the mean turn length.
- Losses are the clear weakness. The stator core loss model (alternating loss on the peak flux
  density of each element, no-load field) gives about half of the authors' loss with rotational
  fields, and leaves out rotor-yoke loss (solid mild steel: about 34 W of the 69 W measured on the
  TFM, per the authors' core-loss paper, IEEE TMAG 2014), loss from the six-step current harmonics (the TFM's core loss rose from 69 W at no load to
  112 W at rated load), inverter and stray loss. The computed efficiency is 10 to 13 points above
  the measured one in both machines, and the efficiency maps of the pipeline are optimistic by
  about as much. Output torque at 1800 rpm is too high by the same loss (TFM +22 to +31 %).
- Done in T31 (efficiency error now +2 to +5 points). Next steps were: rotational loss from the locus of B in each element (the B
  vectors of every position are already saved in `core_field.npz`), rotor-yoke loss (backlog B04),
  and load-dependent core loss (field of the loaded sweep instead of the no-load sweep).
- Not modelled in either case: coupling between the stacks (the TFM's measured inductance differs
  by 10 % between the middle and the outer stacks), the steel shaft, the six-step current shape.
