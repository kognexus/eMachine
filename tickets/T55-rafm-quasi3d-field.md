# T55: Field model of the raxial machine: radial section and axial slices (quasi-3D)

Status: done
Depends on: T53

## Why

The flux of the raxial machine closes in three gaps. The paper finds the radial and the axial
magnetic circuits nearly decoupled (Section 2.2: the PMs of one circuit hardly weaken the other;
the superposition of the separately acting PMs gives the EMF of both acting together) and designs
the machine by splitting it into radial and axial 2D parts (Section 2.3). A 3D sector with a
three-sided sliding gap does not fit the TFM's sliding-surface method; a 3D check is backlog B18.

## Scope

- Geometry kind `rafm.quasi3d`: per rotor position
  - radial section (Gmsh 2D, whole circle): outer rotor iron and radial magnets, stator teeth with
    tips, yoke ring, the outer sides of the toroidal coils in the radial slots and their inner
    (return) sides at the bore, extruded over the radial tooth length;
  - axial slices (Gmsh 2D, unrolled, periodic over the circumference) at n radii across the axial
    magnets: disc iron, axial magnets, gap, axial teeth with tips, coil end sides, half the yoke
    (symmetry plane z = 0: flux parallel), each slice of radial width dr at its radius.
- Solver `elmer_quasi3d`: the 2D Elmer solver on each part; torque = radial + 2 x sum of slices;
  flux linkage per phase likewise; core fields of all parts for the loss model.
- The paper's comparison: no-load EMF, rated torque, cogging, ripple, air-gap flux densities.

## Acceptance criteria

- [x] No-load EMF of the paper design (140 turns per coil, 120 rpm): 147 V rms per phase within 15 %.
- [x] Torque at 7.3 A rms, i_d = 0: 245.5 Nm within 15 %.
- [x] Radial and axial shares reported. (The superposition holds by construction in this model; a check needs B18.)
- [x] Peak gap flux densities near the paper's 1.85 T (radial) and 1.57 T (axial), within 20 %.
- [x] Cogging and ripple reported next to the paper's 9.19 Nm (3.79 %) and 6.18 %.

## Result

2026-10-17. Geometry `rafm.quasi3d` (`machines/rafm/section.py`, `builder.py`): per rotor position a
radial section (whole circle, about 52 000 triangles) and three axial slices at r = 125, 135, 145 mm
(10 mm each, about 35 000 triangles, periodic over the circumference). Solver `elmer_quasi3d`
(`solvers/elmer/quasi3d.py`): each part with the 2D solver; Arkkio torque in the radial gap, Maxwell
stress over the axial gap band for the slices, both discs by the mirror. The 2D case writer
(`section2d.write_case`) now takes magnets with a given magnetisation and boundaries "zero", "free"
or periodic. One position (four parts) meshes and solves in about 7 s; 48 positions in about 2 min.

Two bugs found on the way: the rotor offset first was 180 el. deg off (phase A's flux peaked
negative at position 0); the periodic boundary of the slices did not couple (Elmer: "Points not
found"; the translation runs from the target boundary onto this one). That second bug left a
-2.35 Nm mean in the cogging torque; after the fix the mean is 0.001 Nm. 12 positions per half period
alias the cogging (period 30 el. deg): cogging and ripple are taken from 48 positions.

The paper's design (Table 1 plus the reconstruction of T53), 140 turns per coil, 120 rpm:

| Quantity | This model | Paper |
|---|---|---|
| No-load EMF (fundamental, rms) | 134.0 V | 147 V (-8.8 %) |
| Torque at 7.3 A rms, i_d = 0 | 231.9 Nm | 245.5 Nm (-5.6 %) |
| Torque ripple (peak to peak / mean) | 8.8 % | 6.18 % |
| Cogging, peak to peak | 11.6 Nm | 9.19 Nm |
| Torque check: 3/2 p psi_1 NI | within 0.7 % | |

Torque shares at rated current (position 0, first reconstruction): radial section 39 %, axial
slices 61 %; the paper's Figure 10 gives the EMF of the axial part as 1.7 times that of the radial
part (model 1.55).

Sensitivity at no load: ideal iron +30 % flux, the SMC at mu_r 400 instead of 600 -3 %, remanence
1.32 T instead of 1.28 T +2 %. The teeth saturate (tooth bodies 1.75-1.8 T, tips over 2.2 T at the
95th percentile), the yokes do not (0.5 T on average): the unknown slot width matters most. The
first reconstruction (20 mm slots) gave 123 V and 213 Nm; 16 mm slots fit the masses of Table 2
better and give the values above.

Tests (`tests/unit/machines/test_rafm_field.py`): the request; slow: flux peak at position 0, no
mean cogging, torque against the flux, EMF and torque within 15 % of the paper.
