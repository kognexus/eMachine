# Design principles of the topology catalogue (T62)

Where the variable ranges and the ripple methods of the multi-topology study come from. The papers are
items of the Zotero collection "Robotics / Actuators", cited by their item key; the extraction notes
(`srm.md`, `synrm_ipm.md`, `afpm_tfm.md`, `ripple_methods.md`) are kept with the study records, outside
this repository. [GK] marks textbook rules that are not in the library (Zhu & Howe 2000; Li &
Slemon 1988; Bianchi & Bolognani 2002).

The catalogue is `emachine/machines/catalogue/` (radial: `radial.py`, axial: `axial.py`); the
geometry is drawn by `emachine/machines/section2d/`. Variables are lengths, arcs and a few shares
(width of a tooth or a slot over its pitch, insulation ratio). Shares are used where an absolute
length would make most slot/pole combinations undrawable: the slot pitch changes threefold between 12
and 36 slots. Every design is reported in absolute dimensions.

## Common rules

| Rule | Value used | Source |
|---|---|---|
| Air gap | 0.3 to 1.0 mm, a variable | user; 0.25 to 0.4 mm is best for SRM and SynRM (srm.md, synrm_ipm.md) |
| Windings | fractional-slot concentrated (FSCW) or integer-slot with q = 1; no other distributed winding | user |
| FSCW slot/pole list | k_w1 >= 0.9, balanced, gcd(Q, 2p) >= 2 (no unbalanced magnetic pull), q = 1/4 to 1/2: 12/10, 12/14, 18/16, 18/20, 24/20 ... 36/42 | slot star (winding_layout); 548J96N8, BKHZKL4S |
| Copper fill | 0.5 to 0.7. The fewest strands in hand of AWG 12 to 32 within 0.04 of the best fill | user |
| Current density | rated <= 10 A/mm2 rms, peak (42 A) <= 40 A/mm2 rms | study choice |
| Turns | the most the 48 V bus allows at 10.5 A and 1000 rpm, with 3 % of the voltage kept for harmonics; fewer if the efficiency at that point would be below 80 % | user (drive, efficiency) |
| Cogging period | 360 deg / LCM(Q, 2p), mechanical; a higher LCM and a smaller gcd give less cogging | ripple_methods.md [GK] |

## Ripple methods

Design stage (modelled):

| Method | How it is modelled | Topologies | Source |
|---|---|---|---|
| Slot/pole choice | variable `combo` (the LCM changes with it) | all slotted | [GK], 6LWGB82R |
| Continuous skew, 0 to 1 cogging period | variable `skew_share`; every harmonic of torque and flux times sin(n theta/2)/(n theta/2), mean torque times the fundamental factor; verified by stepped slices for the finalists | PM, vernier, SynRM | [GK]; 7F5DNII2 (1.2 slot pitches: -68 % ripple, -2.3 % torque) |
| Magnet arc | variable `magnet_arc_share` 0.65 to 1.0 | PM, vernier, axial PM | [GK] (integer + 0.14 slot pitches), NN2RC8ZP |
| Halbach magnets | 2 to 4 segments per pole, magnetisation turning with the angle | `rfm_halbach_in`, `afm_coreless` | NN2RC8ZP (+12 % torque density) |
| Slot opening and tooth tips | `opening_share`, `tip_height_mm` | slotted | [GK] (b0/g; at g 0.3 mm skew and arc are the main levers) |
| Consequent poles | magnets on every second pole, iron pole arc a variable | `rfm_cpm_in` | BKHZKL4S (-38 % ripple, -22 % torque) |
| Flux-barrier count and insulation | `barriers` 1 to 4, `insulation` 0.25 to 0.6 | SynRM, PMaSynRM | 7F5DNII2, QZGGD4VM, H63Q9TRI, I4LZ4ACL (Vagati n_r = n_s +- 4; k_wq 0.4 to 0.5) |
| SRM pole arcs | stator arc share 0.35 to 0.55, rotor arc 1.0 to 1.4 times the stator arc, Lawrenson's feasibility triangle | SRM | BU46AX5U, GITV26PL (beta_r 0.5 to 2 deg above beta_s) |
| SRM firing angles | turn-on and turn-off angles and the chopping current optimized per design by the dynamic model | SRM | IB8ISNTV (firing angles alone: 120 -> 42 % ripple) |

Control stage (stated, not modelled): harmonic current injection of the 6th and 12th torque harmonics
(6LWGB82R: about 2 % of the peak torque spent; cogging needs its own model), learned angle-indexed
feed-forward (27ZMKSMF, LWLV73AU), torque-sharing functions for the SRM (Y339AF5J, HPV6LSU8: 5 to 15 %
at more than 20 % load). A rule from ripple_methods.md: keep passive cogging near 1 % of the rated
torque and leave the position-locked load ripple to the controller, if the current loop runs at 10
times the 12th-harmonic frequency at top speed (at 1000 rpm and 10 pole pairs: 2 kHz).

## Per topology

### Radial surface PM, inner rotor (`rfm_spm_in`), Halbach (`rfm_halbach_in`), outer rotor (`rfm_spm_out`), consequent pole (`rfm_cpm_in`)

Stator: tooth body 0.3 to 0.75 of the slot pitch, yoke 0.45 to 1.3 times the tooth (FSCW: a tooth's
flux splits into both directions of the yoke), tips 0.3 to 1.5 mm, opening 0.15 to 0.6 of the slot
mouth (at least 0.8 mm: needle winding or segmented stator). Magnets 1.5 to 5 mm, NdFeB 1.25 T at the
working temperature. Gap radius between the bore + 5 mm and the outer radius - 5 mm (split ratio).

### Interior V (`rfm_ipm_v`)

Two bars per pole, V angle 110 to 180 deg (180: one flat bar), apex depth 0.15 to 0.8 of the rotor
depth, bar length 0.4 to 0.98 of the longest that fits (bisection against bridge, pole width and the
iron above the bore), bridge 0.4 to 1.0 mm, 1 mm centre post; pockets at the bar ends at most one
magnet thickness long. 8 to 22 poles. Source: YT3SF56W (Prius V proportions, bridge at its minimum).

### Spoke (`rfm_spoke`)

Tangentially magnetised magnets 1.2 to 5 mm wide and 3 to 12 mm deep, bridge 0 to 0.8 mm, 1 mm pocket
under each magnet; 14 poles and more (flux concentration needs many poles).

### SynRM (`rfm_synrm`) and PMaSynRM (`rfm_pmasynrm`)

Barriers are arcs around a centre on the q axis outside the rotor (the largest meets the surface at
right angles on the neighbouring d axes), 1 to 4 per pole, insulation ratio 0.25 to 0.6, ribs 0.3 to
0.8 mm, a 1.5 mm ring above the bore. Windings: q = 1 (12/4 to 36/12), 12/8, 18/12 and FSCW up to 14
poles. PMaSynRM: ferrite (0.42 T, mu_r 1.1) across the q axis in every barrier, 2 to 14 mm wide
(synrm_ipm.md: ferrite raises the power factor from 0.65 to 0.85-0.93 and the torque by 30 %, NdFeB
does not pay). FSCW is known to be poor for SynRM (4E8HKLAJ); it is offered because the user excluded
distributed windings, and the result shows the cost.

### Switched reluctance (`rfm_srm`, `afm_srm`)

6/4, 12/8, 6/8, 12/16, 18/12, 24/16 (radial; axial without 24/16): the rotor-pole count divides by the
stator poles per phase, and no phase shift is a multiple of the rotor pitch. Stator pole arc 0.35 to
0.55 of the stator pitch, rotor arc 1.0 to 1.4 times the stator arc, Lawrenson's triangle checked
(BU46AX5U). Rotor pole height 0.2 to 0.7 of the rotor depth. Asymmetric half bridge on the 48 V bus,
the same rms phase current as the PM machines (7.42 A) at the rated point, 42 A peak; soft current
chopping. Mutual coupling between phases is neglected (one phase is solved alone).

### Vernier (`rfm_vernier`, `rfm_ds_vernier`)

Split-tooth stator: Q winding slots, k modulators per tooth, winding pole pairs P_w (FSCW of the Q
slots), rotor pole pairs P_r = Q k - P_w; combinations 6/3/2 (P_r 16), 12/2/5 (19), 12/2/4 (20),
12/3/4 (32), 12/3/5 (31), 9/2/4 (14), 18/2/8 (28), 6/2/2 (10). Gap between modulators 0.3 to 0.6 of the
modulator pitch; pole pitch over gap at least 4 (afpm_tfm.md: the gain needs 8). The phase sequence
of the field turns against the rotor for P_r = N_s - P_w; the evaluation finds it from the no-load
flux. Dual-stator: a ring of radially magnetised magnets between an outer and an inner split-tooth
stator, both windings in series.

### Axial flux (`afm_ss`, `afm_yasa`, `afm_afir`, `afm_coreless`)

The active annulus is the bore radius plus one coil-side width (end turns) to the outer radius less
one coil-side width; with the 52 mm bore D_i/D_o is about 0.65 to 0.7 of the active annulus, at the
upper end of the 0.55 to 0.75 of built machines (afpm_tfm.md). Slot share 0.35 to 0.65 (constant
angle: trapezoidal teeth), tips and openings as radial machines, magnets 1.5 to 5 mm, rotor discs 1.5
to 8 mm. YASA: two rotors whose magnets are magnetised the same way (N-S), so the flux passes straight
through the yokeless teeth. AFIR: two stators and an ironless magnet ring. Coreless: coils without
iron between two Halbach discs (no cogging, no iron loss; afpm_tfm.md expects little torque). Stator
material SMC (Somaloy 700HR class); afpm_tfm.md notes that at a few hundred hertz laminations are as
good, which the report checks on the best axial design.
