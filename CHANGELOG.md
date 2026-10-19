# Changelog

Changes to the code and the progress of the restructuring tickets. Newest first. Ticket details: the
[GitHub issues](https://github.com/kognexus/eMachine/issues?q=is%3Aissue), titled by ticket ID; architecture: `docs/architecture.md`.

## 2026-10-19 (T75: standard views of a topology export)

- `emachine.analysis.topology_export` also writes `machine_3d.vtu` (the section extruded to the stack
  length), `torque.csv`, `back_emf.csv`, `section_views.py` and `open_in_paraview.py`; `--refresh` adds them to
  an existing export without solving. `emachine/io/section_views.py` builds the five views (3D geometry,
  section mesh, EM field with flux lines, torque and ripple, back-EMF) as GUI tabs or pictures.
- T76: in the ParaView GUI every view gets its own tab (the tab is created before the view), the material views
  use a categorical colour map with a legend, and the charts plot over the electrical angle. The README shows
  the five views as example output.

## 2026-10-18 (cleanup for publication)

- The tickets moved from `tickets/` to the GitHub issues of the repository (one issue per ticket,
  titled by its ID; backlog tickets labelled `backlog`). Links in the docs point to the issues.
- Installation with pixi (`pyproject.toml`): `pixi install` sets up Python, NumPy, Gmsh and the
  compilers; `pixi run install-elmer` builds Elmer FEM 26.2.1 from source into the environment
  (`scripts/install_elmer.sh`). emachine is a package with the console command `emachine`.
- Elmer is found through `$ELMER_HOME`, the active environment, the `PATH`, or `.elmer/install`
  (`emachine.solvers.elmer.find_elmer_home`).
- Removed the compatibility layer of T39: the top-level scripts `tfm_*.py` and `check_mesh.py`, the
  `tfm` package and `archive/`. The ticket tests now call `emachine` directly; the winding and thermal
  tests use the functions the pipeline uses (`physics.winding.turns_for`, `pipeline.evaluate.temperatures`,
  `machines.tfm.checks`) instead of copies with the old signatures, and the characterization results
  are unchanged. The superseded `tfm_stator_v1.fs` and `tfm_rotor_v1.fs` are gone.
- Fixed: the plugin registry loaded the built-in plugins without a lock, so rotor positions solved in
  the thread pool could find an empty registry (`emachine solve` failed for every position but the
  first). The removed `tfm_pipeline.py` had hidden this by importing the geometry builder.
- Moved files: the example specifications (root `spec_*.json` and `specs/`) -> `examples/`, with
  `spec_example.json` -> `examples/tfm_single_phase.json` and `spec_three_phase.json` ->
  `examples/tfm_three_phase.json`; `motor*.json` -> `examples/params/`; the fidelity study ->
  `examples/mesh_fidelity/`; the validation cases -> `examples/validation/`; pictures -> `docs/images/`. `examples/README.md` gives the command for
  each example. Specs of the studies that left the repository (`rafm_ilm85*`, two `rafm_zhang2023`
  variants) were taken out. The gear-TFM study (`gear-tfm-150rpm/`, T70 to T74) and the
  multi-topology study (`multi-topology-analysis/`, T58 to T66) left the repository; they are kept with
  the other run records outside it. Their code (`emachine study`, the topology catalogue) stays.
- The view script copied into every ParaView export is now `paraview_views.py` (was
  `tfm_paraview_views.py`); `export --refresh` rewrites old exports.
- `tests/characterization/` is now `tests/regression/` (recorded results in `baseline/`): a standing
  regression check, re-recorded on purpose with `pixi run rebaseline`.
- An invalid specification stops the command with a one-line message instead of a traceback.
- Documentation: new README with the pipeline chart, `docs/usage.md` (inputs, options and
  outputs of an optimization), `docs/analysis.md` (machines, field model, known limits).
- Tests no longer read local result folders: the cache-key test uses the specs of the repository
  (and local `runs/` when present); the study-output tests use a small inline configuration.

## Restructuring into `emachine` (T32 to T41)

| Ticket | Title | Status |
|---|---|---|
| [T32](https://github.com/kognexus/eMachine/issues/32) | Architecture, interfaces and characterization tests | done |
| [T33](https://github.com/kognexus/eMachine/issues/33) | Machine-independent physics in `emachine/physics` | done |
| [T34](https://github.com/kognexus/eMachine/issues/34) | TFM as a machine plugin | done |
| [T35](https://github.com/kognexus/eMachine/issues/35) | Field solvers behind `FieldSolver` | done |
| [T36](https://github.com/kognexus/eMachine/issues/36) | Pipeline: stages, sweeps, load levels, run store | done |
| [T37](https://github.com/kognexus/eMachine/issues/37) | Optimization: interface, NSGA-II, random search | done |
| [T38](https://github.com/kognexus/eMachine/issues/38) | Analysis and I/O modules | done |
| [T39](https://github.com/kognexus/eMachine/issues/39) | Command line, compatibility, tests layout, README | done |
| [T40](https://github.com/kognexus/eMachine/issues/40) | Skeletons of the other machines | done |
| [T41](https://github.com/kognexus/eMachine/issues/41) | Radial-flux surface PMSM end to end | done |

## 2026-10-18 (gear TFM at 85 mm and 150 rpm, T70 to T74)

- Study folder `gear-tfm-150rpm/` (specs, scripts, runs, report). Result: about 74 % at 150 rpm (verified),
  1.07 Nm with spoke rotor and tooth tips; 90 % would need about a tenth of the default SMC iron loss.
- T70: objective `max_efficiency` and pick `highest_efficiency`. Cached records take the objective
  vector of the current specification.
- T71: `machine.rotor_magnet_slots` (two magnet pockets over the side walls, variable `magnet_overhang_mm`)
  and `machine.halbach_segments` (was fixed at 2).
- T72: `machine.rotor_skew_el_deg`, `machine.rotor_skew_steps`: step skew of the rotor inside each phase
  (`rotor.skew_steps`, `rotor.skew_deg` in the parameter files).
- T73: `machine.ring_tooth_tips`: tooth tips on the toothed ring (variables `ring_tip_overhang_mm`,
  `ring_tip_height_mm`; mesher `stator.ring_tip_overhang`, `stator.ring_tip_height`).
- All new options are off by default, and at their defaults they are left out of cache keys
  (`emachine/spec/names.py`, `LATER_OPTIONS`), so older specifications build and key the same machine.
  The golden data of the characterization cases `specs`, `designs` and `stand_in_evaluation` were
  captured again: only new keys, no value changed.
- Dual-rotor radial machine (DeepDrive concept), catalogue key `rfm_dual_rotor`: double-sided laminated stator
  (two slotted rings back to back, `section2d.radial.gaps` accepts touching stator rings) between an inner and
  an outer surface-magnet rotor. Fix in the section kit: the magnets of a second rotor overwrote those of the
  first (same names); they are now `magnet_r1_*`. Two samples at 1500 rpm in `gear-tfm-150rpm/dual_rotor/`.
  Value `halbach_segments` (0 = surface magnets, 2 to 4 = Halbach rotors, strong side towards the stator).
  ParaView files of the samples: `gear-tfm-150rpm/dual_rotor/export.py` -> `gear-tfm-150rpm/paraview/dual_rotor/`.
- Fix: the TFM spoke rotor failed in the field analysis ("centre_deg"). Its hub
  `rotor_housing_non_magnetic` contains "magnet" and was taken for a magnet.
- Not done: the Onshape features have none of the new options yet (the `onshape-fs` connection needs
  re-authorisation).

## 2026-10-18

- T58 to T66 (in progress): multi-topology study in the TQ RoboDrive ILM-E85x23 envelope (85/52 mm,
  30 mm active length, 48 V, 10.5 A rated, 42 A peak, rated point 1000 rpm), everything in
  `multi-topology-analysis/`:
  - T59/T60: `emachine/machines/section2d/`: a general 2D section kit. Radial machines as rings
    (inner, outer, dual stator; slotted stators with tips, notches and split teeth; rotors surface,
    Halbach, consequent pole, interior V, spoke, flux barriers with and without ferrite, salient,
    magnet ring), axial machines as periodic unrolled slices (single-sided, YASA, AFIR, coreless,
    SRM). Builder `section2d`, solver `elmer_sections` (Arkkio or Maxwell-stress torque in every air
    gap). The T41 machine drawn by the kit: torque within 0.1 % of the T41 mesher.
  - T61: `emachine/physics/drive.py` (Clarke and dq torque, turns from the bus voltage, AWG and
    strands for a fill of 0.5 to 0.7, skew, phase voltage waveforms, SRM flux map and dynamic model
    with chopping) and `emachine/pipeline/drive.py` (evaluation of a design on the drive).
  - T62: `docs/design_principles.md` and the literature notes of the Zotero collection
    Robotics/Actuators (`multi-topology-analysis/literature/`).
  - T63: `emachine/machines/catalogue/` (16 topologies) and `python -m emachine study`.
  - T64/T65: `topology_report.py` (report, interactive Pareto page, phase voltage figures),
    `topology_export.py` and `io/topology_views.py` (ParaView files and pictures),
    `topology_postprocess.py`.
  - The 2D case writer takes a remanence and permeability per magnet (ferrite in a PMaSynRM).

## 2026-10-18

- T57 done: a raxial machine in the envelope and drive of the TQ ILM85x23 (85 mm, 30 mm, 48 V,
  11.3 A), iron-cobalt SMC stator (estimated curve), optimized; report `runs/rafm_ilm85/report.md`.
  Turns and AWG wire chosen together at the fill factor (`winding.wire` = "awg").

## 2026-10-17

- T53 to T56 done (hybrid machines: the radial-axial "raxial" PMSM of Zhang et al. 2023):
  - T53: `rafm/pmsm` with a toroidal winding (`winding_layout.toroidal`), dimensions, checks, masses,
    thermal network; `specs/rafm_zhang2023*.json` (details the paper lacks fitted to its masses).
  - T54: Onshape Feature Studio "Hybrid machines" with the feature "Raxial machine"
    (`hybrid_design.fs`); volumes equal the Python model.
  - T55: quasi-3D field model `rafm.quasi3d` / `elmer_quasi3d` (radial section + periodic axial
    slices); against the paper: torque -6 %, EMF -9 %. Periodic boundaries in the 2D case writer.
  - T56: maps at our drive and at the paper's, ParaView export with the axial slices, report
    `runs/rafm_zhang2023/report.md`. Exact fast nearest-neighbour search in the loss model.
- The project venv was rebuilt on Python 3.13 (Homebrew removed 3.12); the old one is
  `.venv-py312-broken`.

- T48 to T52 done (design variables as lengths and arcs, `docs/parameters.md`):
  - T48: catalogue of the parameters of RFM, AFM and TFM: specification, design variable, derived,
    geometry constant; a test holds every machine to it (no `ratio`, a unit in every name).
  - T49: slotted stator by `slot_height_mm`, `slot_width_mm`, `yoke_height_mm`; the bore follows
    from the outer diameter, so the stator fills it. Fixed on the way: the slot area was that of a
    slot widening outwards while mesher and CAD draw parallel-sided slots (122 against 85 mm2 for
    the reference); now the drawn area (within 1 % of the mesh). RFM cache keys change on purpose.
  - T50: arcs in electrical degrees (`magnet_arc_el_deg`, TFM `tooth_arc_el_deg`), `magnet_length_mm`
    (interior), `barrier_width_mm`, `magnet_width_mm` (SynRM), SRM `rotor_pole_arc_deg`,
    `rotor_pole_height_mm` with Lawrenson's checks, TFM `claw_tip_height_mm`. Old designs, seeds and
    run files are converted when read (`spec/names.standard_values`); TFM cache keys and all
    characterization data unchanged.
  - T51: axial flux machine with its own dimensions: annulus (`inner_diameter_mm`), axial slots,
    yoke, rotor back iron from the axial length per arrangement, its thermal network.
  - T52: eMachine dialog in these fields (no ratio field left); compiles in Onshape.

## 2026-10-16

- T43 to T47 done (the naming standard and the Onshape feature):
  - T43: specs, registry and code use `flux_path`, `principle`, `rotor`, `stator`,
    `rotor_placement`, `arrangement`; `rfm/ipm` and `rfm/pmasynrm` became rotor layouts of
    `rfm/pmsm` and `rfm/synrm`. Old names are read by `spec/names.py`, which also writes specs
    back in them for the cache keys: results cached before the change are still found (28 of 29
    recorded keys equal; the 29th is the unsolvable `tfm/srm`). Spec files rewritten in the new
    names.
  - T44: one module per principle and per rotor layout (`machines/<flux_path>/<principle>.py`,
    `rotors/<layout>.py`, `RotorLayout`); slot star in `machines/winding_layout.py`.
  - T45: the machine matrix in `python -m emachine list` and `docs/machines.md`; backlog B16
    (AFM SynRM).
  - T46: `winding.span`, `layers`, `pitch_slots`, `slot_class`; single-layer windings and short
    pitching; FSCW / FSDW / ISDW labels with q and k_w1 in the reports. A single-layer 12s10p gives
    0.966 / 0.933 of the torque of the double layer per ampere-turn (field solution, within 2 %).
  - T47: Onshape feature "eMachine" (`emachine/cad/`, `python -m emachine featurescript`, `onshape
    --spec --design`): choose flux path, principle and rotor layout; TFM through the TFM feature
    code, radial flux machines (surface, interior, flux barrier, flux barrier with magnets, salient)
    built in Onshape with the volumes of the Gmsh section (within 1e-5). The studio still has to be
    pasted into the Onshape document (empty studio "eMachine" created there).
  - Full slow suite: 366 tests pass (1 skipped).
- Naming standard `docs/naming.md`: a machine is flux path (`tfm`, `rfm`, `afm`, `rafm`) x torque
  principle (`pmsm`, `synrm`, `srm`, `vernier`) x rotor layout (IPM and PMaSynRM become rotor
  layouts of PMSM and SynRM); winding = span x layers x pitch, with FSCW, FSDW, ISDW as labels
  from q = Q / (2 p m); old names stay readable. Tickets T43 (renaming, aliases), T44 (one module
  per principle), T45 (machine matrix), T46 (winding description, short pitching, single layer,
  slot class); backlog B14 (RAFM), B15 (PM vernier). No code changed yet.
- T42 done: `python -m emachine export` works for radial flux machines. The 2D solution (all
  phases, one electrical period, loaded and no load) is written as the same ParaView files as the
  TFM export, extruded to the stack length, with `phase` and `A_z` (flux lines) added; the view
  script shows a section from the top with flux lines and a mesh close-up at a slot opening.
  Reference export `runs/rfm_spm_12s10p/paraview` (14 s). Wedge cells ordered as VTK computes a
  positive volume (its class documentation says the opposite). Text labels of all views on a light
  box. B13 keeps CAD, published reference and lamination data. Full slow suite: 333 tests pass.
- T41 done: the radial flux surface PM machine `rfm/pmsm` runs end to end with the same commands
  (2D cross-section in Gmsh, Elmer MagnetoDynamics2D with all phases, slot-star winding); torque
  agrees with 3/2 p psi NI within 0.3 %; example spec `specs/rfm_spm_12s10p.json`. Fixed: losses of
  a field file holding all phases were counted once per phase (radial flux losses 3 times too
  high; TFM not affected). ParaView export stops with a clear message for radial machines.
  Backlog B13 (export, CAD, published reference, lamination data). Full slow suite: 323 tests pass.
- T39 done: `python -m emachine` commands, old scripts as wrappers, tests in `unit/`, `tickets/`,
  `characterization/`; README describes the new layout and the radial flux machine.
- T40 done: machines `rfm/{pmsm,ipm,synrm,pmasynrm,srm}`, `afm/{pmsm,srm}`, `tfm/srm` registered
  with options, variables, dimensions, checks, winding and thermal estimates; MTPA helper;
  backlog tickets B06 to B12 for their geometry.
- T38 done: `emachine/analysis` (map, field export, validation) and `emachine/io` (VTK, SVG,
  ParaView) on the interfaces; the whole slow suite passes.
- T37 done: optimizers as plugins (`nsga2`, `random`), chosen by `optimizer.algorithm`; seeding in
  the pipeline.
- T36 done: `emachine/pipeline` (sweep, design space, evaluation) works through the Machine,
  GeometryBuilder and FieldSolver interfaces; tested with a fake all-phase machine.
- T35 done: field solvers `elmer3d` and `analytic` (`emachine/solvers`), geometry builder
  `tfm.sector3d`; `tfm_pipeline.py` is a wrapper; the whole slow suite passes.
- T34 done: the TFM is the machine plugin `tfm/pmsm` (`emachine/machines/tfm`); the spec section
  `machine` gains `family` and `topology`; the mesher is split into one module per stator and
  rotor type; the FeatureScript files moved to `emachine/machines/tfm/cad/featurescript/`.
- T33 done: `emachine/physics` (winding, thermal network, torque, losses) and `emachine/spec`;
  the old `tfm` modules are adapters; layering test of the packages.
- T32 done: package `emachine` with `core/` (interfaces, data types, plugin registry), characterization
  tests with golden data recorded from the code before the restructuring, unit tests of `core`.
- Plan of the restructuring agreed with the user: package `emachine`, machines as plugins by flux
  path (TFM, RFM, AFM) and topology (PMSM, IPM, SynRM, PMaSynRM, SRM), optimizers and field
  solvers as plugins, pipeline separate; skeletons for all machines and one radial-flux surface PMSM
  working end to end; old scripts kept as wrappers; old specs and runs stay readable.
- `docs/architecture.md`, tickets T32 to T41, this changelog.
- Backup of the code before the restructuring: `archive/pre-refactor-2026-10-16.tar.gz`.
- T31: rotational stator loss, rotor eddy-current loss (cells, noise floor, skin effect), loaded-field
  core loss; validated on two published SMC machines (efficiency within 2 to 5 points).

## 2026-10-15

- T30: validation against two published SMC prototypes (`tfm_validate.py`).
- T29: whole motor and efficiency map as ParaView files; five views as GUI tabs; ParaView 6.2 fixes.
- T24 to T28: toothed-ring stator (Fig. 17), arched valleys, staggered teeth, Onshape fixes, the
  user's 48-pole outrunner analysed.
