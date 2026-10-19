# Machines, field model and known limits

Background for [usage.md](usage.md): which machines can be analysed, how the field analysis works
and where the model stops. Names of machines follow [naming.md](naming.md); design variables are in
[parameters.md](parameters.md).

## What can be analysed

`emachine list` prints the machine matrix ([machines.md](machines.md)). Solvable today:

| Machine | Field model | Status |
|---|---|---|
| `tfm/pmsm` transverse flux PM | 3D periodic sector of one phase (Gmsh + Elmer) | complete: Onshape CAD, losses, thermal, efficiency map, ParaView, validated against two published prototypes |
| `rfm/pmsm` radial flux surface PM, inner rotor | 2D cross-section with all phases (Gmsh + Elmer MagnetoDynamics2D) | optimization, map, ParaView, CAD; checked against theory |
| `rafm/pmsm` radial-axial hybrid (Zhang et al. 2023) | quasi-3D: one radial section and three axial slices per position | map, ParaView, CAD |

The other machines (interior PM, SynRM, SRM, axial flux, vernier) are known to the system with
their variables, checks and estimates. Their geometry is added ticket by ticket (backlog B06 to
B16 in the [issues labelled backlog](https://github.com/kognexus/eMachine/issues?q=is%3Aissue+label%3Abacklog)).

### Transverse flux machine (TFM)

- Stators: U-core, U-core with I-bridge, claw pole, and toothed ring (`toothed_ring`: one
  continuous U-ring with teeth on both walls, with the options `ring_arched_valleys`,
  `ring_staggered_teeth`, `ring_tooth_tips`). C-, E- and Z-cores are built as geometry only
  (`emachine mesh --params p.json --stator-only --out s.step`); see ticket T22.
- Rotors: surface magnets, Halbach array (`halbach_segments` per pole), spoke (flux
  concentrating, optionally `rotor_magnet_slots`), axial ring. Step skew with
  `rotor_skew_el_deg` and `rotor_skew_steps`.
- One phase pulsates between about zero and twice its mean, a ripple of about 200 % before
  cogging. A ripple limit of 20 % therefore needs `machine.phases = 3`. The three phases sit side
  by side along the axis, shifted by 120 electrical degrees, `phase_spacing_mm` apart.
- `pole_shift_el_deg` offsets every second stator core. It is a fixed input, not a search
  variable, and doubles the model size.
- The coil is a flat copper strip winding (`winding.conductor: "strip"`): a few turns, with a
  resistance of milliohms.

### Radial flux surface PM machine (RFM)

- Each rotor position is a 2D mesh of the whole cross-section, with all three phase currents at
  once. Torque comes from the air-gap field (Arkkio) and flux per phase from the coil sides. One
  design takes about 5 s at 12 positions.
- The winding is laid out by the slot star (`emachine/machines/winding_layout.py`) from
  `winding.span`, `layers`, `pitch_slots`, `slot_class`. Reports name it FSCW, FSDW or ISDW with q
  and the winding factor. Slot/pole combinations without a balanced winding are rejected by a
  geometry check.
- Losses: copper, stator core (give the coefficients of the lamination grade; the default is SMC),
  and eddy currents in magnets and rotor core (`materials.rotor_iron.eddy_width_mm` = 0.35 for a
  laminated rotor).
- Checked against theory (T41): torque = 3/2 p ψ N I within 0.5 %. No-load flux is 17 % below the
  analytic air-gap estimate (open slots, leakage). Cogging is about 1 % of rated torque.

### Radial-axial hybrid PMSM (RAFM)

The ARF-PMSM of Zhang, Liu and Wu (Electronics 2023, 12, 2867). An SMC ring yoke carries teeth
that face an outer rotor ring radially and two rotor discs axially. 24 toroidal coils around the
yoke act on all three gaps, with 20 poles. The radial and axial circuits are taken as independent,
as the paper finds. A 3D check is backlog B18. The paper does not give every dimension:
`examples/rafm_zhang2023.json` fills them in from its figures and masses (T53).

```bash
emachine map    --spec examples/rafm_zhang2023.json --design examples/rafm_zhang2023_design.json --out runs/rafm/map
emachine export --spec examples/rafm_zhang2023.json --design examples/rafm_zhang2023_design.json --out runs/rafm/paraview
```

### Multi-topology study

`emachine study --config <study.json>` optimizes every topology of the catalogue
(`emachine/machines/catalogue/`: radial surface PM inner/outer/Halbach/consequent pole, interior V,
spoke, SynRM, PMaSynRM, SRM, vernier, axial single-sided, YASA, AFIR, coreless Halbach, dual-stator
SRM) on the same drive and envelope, then verifies the picks. Evaluation on the drive is done by
`emachine/pipeline/drive.py`: the winding follows from the bus voltage at rated speed; the current
angle is chosen for most torque; SRM uses a flux map and a dynamic model. The report is written by
`python -m emachine.analysis.topology_postprocess --config <study.json>`. Ranges and ripple methods
are in [design_principles.md](design_principles.md).

## How the TFM field analysis works

1. **Geometry.** The mesher rebuilds stator and rotor from the parameters, with the rotor turned
   to the requested angle, and keeps one periodic sector.
2. **Two domains.** Everything inside the middle of the air gap is one domain and everything
   outside is the other. Each has its own copy of the cylindrical sliding surface, and both
   copies carry the same structured grid.
3. **Join.** ElmerGrid converts the mesh to metres and merges the coincident sliding nodes, so
   rotor and stator become one conforming mesh for that rotor position.
4. **Periodic sides.** The two cut planes carry matching meshes and are tied together.
5. **Sources.** Each magnet gets a uniform magnetisation from its centre angle and type. The coil
   current is applied as an equivalent magnetisation, which gives the same field.
6. **Solve.** Elmer's 3D magnetostatic solver runs once per position, with Newton iteration when
   a material has a B-H curve.
7. **Results.** Torque on the rotor comes from nodal forces, coil flux linkage from the vector
   potential in the coil, and the stator-core flux density from the element field. The smoothed
   nodal field loses a fifth of the flux in thin parts (B05).

Low-level commands for one parameter file (the format of `examples/params/*.json` and of the
`designs/*.json` of a run):

```bash
emachine mesh  --params examples/params/motor_matched.json --out sector.msh --gui     # or --preview p.svg
emachine check-mesh sector.msh
emachine solve --params examples/params/motor_matched.json --run runs/my_run --jobs 6 # results.csv per rotor angle
```

## Saving field solutions

| Mechanism | Setting | What it does |
|---|---|---|
| Two stages | `fidelity.staged` (on) | Every second rotor position is solved first. A design already outside the limits by more than `fidelity.early_stop_margin` (10 %) is not refined; the first-stage ripple is a lower bound, so it cannot become feasible. Refined designs get exactly the result of a full sweep |
| Field cache | always on | `<run>/cache/fields`, keyed by geometry, mesh, materials and ampere-turns. Changing a limit, the speed, the thermal data or the objectives reuses every field solution |
| Load levels | `fidelity.load_levels` (off; 2 to 5) | A geometry is solved at a few current densities and the others are interpolated. The optimizer gets `optimizer.current_steps` further designs per geometry for free |

## Validation

`examples/validation/guo2006` (SMC TFM, Guo et al. 2006) and `examples/validation/guo_clawpole` (SMC claw-pole
motor of the same group) describe published machines and their measured results.
`emachine validate <case.json>` solves the no-load, inductance and load cases and writes
`report.md` comparing published and computed values. Results and conclusions are in ticket T30.

## Known limits

- Saturation is modelled with a two-parameter B-H curve built from `mu_r` and `saturation_T`,
  unless a measured `bh_curve` is given. `saturation_T: null` gives a linear material.
- Each rotor position is meshed separately, so small torques such as cogging carry mesh noise,
  and ripple values depend on the mesh level.
- Magnetostatic only: no eddy currents in the field solution. Rotor eddy-current loss is a
  thin-plate estimate without skin effect, and the rotor housing has no conductivity unless one
  is given.
- TFM phases are treated as magnetically independent.
- Thermal coefficients are assumed defaults. Stator loss data are those of SOMALOY 500 (published
  fit); replace them with data for the grade used.
- Shafts and end caps are left out of the mesh.
- The efficiency map assumes current in phase with the induced voltage (no field weakening) and
  leaves out mechanical and inverter losses.
- Not yet analysed: C, E and Z stators (B02), interior magnets, reluctance and axial flux
  machines (B06 to B12). There is no finite-element thermal check (B03).
- The ParaView views are tested with ParaView 6.2. Older versions back to 5.9 are handled but not
  tested.
