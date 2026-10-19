# Tickets: emachine (formerly the multi-objective TFM optimization system)

Goal: from a few macro inputs (inrunner or outrunner, stator type, total outer diameter, total
stack length, one or three phases) and user-set limits, find designs that maximise torque,
minimise losses and minimise torque ripple, using electromagnetic, loss and thermal analysis.

File and command names in the tickets are those of the time of writing; the cleanup of
2026-10-18 (CHANGELOG) renamed some of them, e.g. `tfm_optimize.py` is now `emachine optimize`.

Status values: `todo`, `in progress`, `done`, `backlog` (specified, not scheduled).

| ID | Title | Depends on | Status |
|---|---|---|---|
| [T01](T01-project-layout-and-tests.md) | Project layout and test harness | none | done |
| [T02](T02-design-specification.md) | Design specification file | T01 | done |
| [T03](T03-design-to-parameters.md) | Design vector to motor parameters | T02 | done |
| [T04](T04-feasibility-checks.md) | Geometric feasibility and limit checks | T03 | done |
| [T05](T05-torque-metrics.md) | Torque metrics for one and three phases | T01 | done |
| [T06](T06-electrical-model.md) | Winding and electrical model | T02 | done |
| [T07](T07-em-analysis-api.md) | Electromagnetic analysis API | T03 | done |
| [T08](T08-fidelity-study.md) | Mesh fidelity study for optimization | T07 | done |
| [T09](T09-loss-model.md) | Loss model: copper and iron | T06, T07 | done |
| [T10](T10-thermal-model.md) | Thermal model | T09 | done |
| [T11](T11-design-evaluation.md) | Design evaluation: objectives and constraints | T04 to T10 | done |
| [T12](T12-nsga2-optimizer.md) | Multi-objective optimizer (NSGA-II) | T01 | done |
| [T13](T13-optimization-cli-and-report.md) | Optimization command and report | T11, T12 | done |
| [T14](T14-bore-diameter-macro-input.md) | Bore diameter as a macro input | T02, T03, T04, T13 | done |
| [T15](T15-seeded-optimization.md) | Seeded optimization | T12, T13 | done |
| [T16](T16-onshape-parameter-sheet.md) | Parameter sheet for the Onshape model | T03, T13 | done |
| [T17](T17-efficiency-map.md) | Torque, speed and efficiency map | T06, T07, T09, T10, B01 | done |
| [T18](T18-paraview-export.md) | ParaView export of a design | T07, T09, B01 | done |
| [T19](T19-torque-ripple-limit.md) | Torque ripple limit, and a field cache independent of the limits | T05, T11, T13 | done |
| [T20](T20-staged-rotor-positions.md) | Rotor positions in two stages | T07, T11, T19 | done |
| [T21](T21-load-level-reuse.md) | Reuse of field solutions across current density | T17, T20 | done |
| [T22](T22-paper-geometry-and-stator-comparison.md) | Geometry options of the review paper, and a comparison of stator types | T19 to T21, B02 | done |
| [T23](T23-strip-ring-coil.md) | Coil of stacked flat copper rings (strip winding) | T11, T17 | done |
| [T24](T24-toothed-ring-stator.md) | Toothed-ring stator of Fig. 17, inner and outer stator | T22 | done |
| [T25](T25-onshape-feature-warnings.md) | Onshape warnings in the v2 features and the UI32 studio | T22, T24 | done |
| [T26](T26-arched-valleys.md) | Arched valleys between the teeth of the toothed ring | T24, T25 | done |
| [T27](T27-staggered-teeth.md) | Staggered teeth on the toothed ring | T24, T26 | done |
| [T28](T28-user-machine-analysis.md) | Full analysis and ParaView views of the user's 48-pole toothed-ring outrunner | T17, T18, T23, T24, T26, T27 | done |
| [T29](T29-paraview-motor-and-map-files.md) | Whole motor and efficiency map as files ParaView opens | T17, T18, T28 | done |
| [T30](T30-validation-against-prototypes.md) | Validation against two published SMC prototypes (TFM and claw pole) | T07, T09, T22, T24 | done |
| [T31](T31-rotational-and-rotor-losses.md) | Rotational stator loss, rotor eddy-current loss, loaded-field core loss | T09, B05, T30 | done |
| [T32](T32-architecture-and-interfaces.md) | Architecture, interfaces and characterization tests | T31 | done |
| [T33](T33-physics-module.md) | Machine-independent physics in `emachine/physics` | T32 | done |
| [T34](T34-tfm-machine-plugin.md) | TFM as a machine plugin in `emachine/machines/tfm` | T33 | done |
| [T35](T35-field-solvers.md) | Field solvers behind `FieldSolver` | T34 | done |
| [T36](T36-pipeline-module.md) | Pipeline: stages, sweeps, load levels, run store | T35 | done |
| [T37](T37-optimization-module.md) | Optimization: interface, NSGA-II, random search | T36 | done |
| [T38](T38-analysis-and-io.md) | Analysis and I/O modules | T36 | done |
| [T39](T39-cli-compatibility-docs.md) | Command line, compatibility, tests layout, README | T37, T38 | done |
| [T40](T40-topology-skeletons.md) | Skeletons of the other machines | T34, T36 | done |
| [T41](T41-rfm-surface-pmsm.md) | Radial-flux surface PMSM end to end | T35, T36, T40 | done |
| [T42](T42-rfm-paraview-export.md) | ParaView export of a radial-flux machine (2D section) | T18, T29, T41 | done |
| [T43](T43-naming-and-machine-identity.md) | Naming standard and machine identity (flux path, principle, rotor layout) | T42 | done |
| [T44](T44-module-per-principle.md) | One module per principle, rotor and stator layouts as modules | T43 | done |
| [T45](T45-machine-matrix.md) | The machine matrix (flux path x principle) in `list` and the docs | T43, T44 | done |
| [T46](T46-winding-description.md) | Winding description: span, layers, pitch, slot class (FSCW, FSDW, ISDW) | T43 | done |
| [T47](T47-emachine-featurescript.md) | Onshape feature "eMachine": flux path, principle, rotor layout to choose | T43 to T46 | done (paste pending) |
| [T48](T48-parameter-catalogue.md) | Parameter catalogue: what describes an RFM, AFM and TFM, no arbitrary ratios | T43 to T47 | done |
| [T49](T49-slotted-stator-absolute.md) | Slotted stator in absolute dimensions: slot height, slot width, yoke height | T48 | done |
| [T50](T50-rotor-and-arc-variables.md) | Rotor layouts and arcs without ratios; TFM tooth arc and claw tip | T48, T49 | done |
| [T51](T51-afm-dimensions.md) | Axial flux machine dimensions: annulus, axial stack, arrangement | T48, T49 | done |
| [T52](T52-emachine-dialog-dimensions.md) | eMachine dialog and sheet in the dimensions of the catalogue | T49 to T51 | done |
| [T53](T53-rafm-hybrid-machine.md) | Hybrid machines: the radial-axial ("raxial") PMSM with a toroidal winding | T43 to T52 | done |
| [T54](T54-raxial-featurescript.md) | Onshape feature "Raxial machine" (hybrid studio) | T53 | done |
| [T55](T55-rafm-quasi3d-field.md) | Field model of the raxial machine: radial section and axial slices | T53 | done |
| [T56](T56-rafm-analysis-at-our-limits.md) | Full analysis of the paper's raxial machine at our bus and current | T53 to T55 | done |
| [T57](T57-rafm-85mm.md) | A raxial machine in the envelope and drive of the TQ ILM85x23 | T53 to T56 | done |
| [T58](T58-multi-topology-study-frame.md) | Multi-topology study in the ILM-E85x23 envelope: frame, reference, drive-based evaluation | T41, T46, T53 to T57 | done |
| [T59](T59-section-kit-radial.md) | General 2D section kit for radial machines (inner, outer, dual stator), all rotor layouts | T41, T49, T58 | done |
| [T60](T60-axial-flux-slices.md) | Axial flux machines as quasi-3D slices: single-sided, YASA, dual stator, coreless, SRM | T55, T58 | done |
| [T61](T61-excitation-and-waveforms.md) | Excitation per principle (dq/MTPA, SRM flux maps), phase voltage analysis, skew | T58 to T60 | done |
| [T62](T62-design-principles.md) | Design principles from the literature: parameter ranges and ripple methods | T58 | done |
| [T63](T63-topology-optimization-runs.md) | Topology catalogue and optimization runs in the ILM-E85x23 envelope | T58 to T62 | done |
| [T64](T64-comparison-report.md) | Interactive Pareto charts and the comparison report against the ILM-E85x23 | T63 | done |
| [T65](T65-topology-paraview.md) | ParaView export and views of the optimal and highest-torque designs | T63 | done |
| [T66](T66-ilm-reference-model.md) | Reference model of the ILM-E85x23 under the same rules | T58, T59 | done |
| [T67](T67-axial-3d-view-and-slice-convergence.md) | Axial machines: 3D view as discs, convergence in the number of slices | T60, T65 | done |
| [T68](T68-spoke-rotor-hub.md) | Spoke rotor on a non-magnetic hub, fewer poles, magnetisation shown | T59, T63 | done |
| [T69](T69-solid-rotor-shaft.md) | SynRM, PMaSynRM and interior PM with a 12 mm shaft | T63 | done |
| [T70](T70-gear-tfm-efficiency-study.md) | Gear TFM at 85 mm and 150 rpm: study frame and objective `max_efficiency` | T24 to T28 | done |
| [T71](T71-rotor-magnet-slots-and-halbach-segments.md) | Rotor magnet slots over the side walls; Halbach segments per pole | T27, T70 | done |
| [T72](T72-rotor-step-skew.md) | Step skew of the rotor magnets inside each phase | T70 | done |
| [T73](T73-toothed-ring-tooth-tips.md) | Tooth tips on the toothed ring, reaching over the coil slot | T24, T26, T27 | done |
| [T74](T74-gear-tfm-screening-and-optimization.md) | Gear TFM: concept screening, optimization runs and report | T70 to T73 | done |
| [B01](B01-saturation.md) | Saturation: nonlinear B-H curves | T07 | done |
| [B02](B02-more-stator-types.md) | Parametric meshing of C, claw-pole, E and Z stators | T03 | backlog |
| [B03](B03-thermal-fea.md) | Thermal finite-element check in Elmer | T10 | backlog |
| [B04](B04-rotor-and-magnet-losses.md) | Rotor iron and magnet eddy-current losses | T09 | done (T31) |
| [B05](B05-iron-loss-field.md) | Iron loss from the element flux density | T09 | done |
| [B06](B06-rfm-ipm.md) | Radial-flux interior PM machine: geometry and solution | T40, T41 | backlog |
| [B07](B07-rfm-synrm.md) | Radial-flux synchronous reluctance machine: geometry and solution | T40, T41 | backlog |
| [B08](B08-rfm-pmasynrm.md) | Radial-flux PM-assisted SynRM: geometry and solution | T40, T41 | backlog |
| [B09](B09-rfm-srm.md) | Radial-flux switched reluctance machine: geometry, solution and excitation | T40, T41 | backlog |
| [B10](B10-afm-pmsm.md) | Axial-flux PM machine: geometry and solution | T40, T41 | backlog |
| [B11](B11-afm-srm.md) | Axial-flux switched reluctance machine | T40, T41 | backlog |
| [B12](B12-tfm-srm.md) | Transverse-flux reluctance machine | T40, T41 | backlog |
| [B13](B13-rfm-export-and-validation.md) | Radial-flux PMSM: CAD, published reference, lamination data (ParaView export done in T42) | T41 | backlog |
| [B14](B14-rafm-flux-path.md) | Radial-axial flux machine (RAFM): flux path, skeleton, geometry | T43 to T45 | done (T53 to T56; 3D check: B18) |
| [B15](B15-vernier-principle.md) | PM vernier machine (principle `vernier`), radial flux first | T43 to T46 | backlog |
| [B16](B16-afm-synrm.md) | Axial flux synchronous reluctance machine | T45, B10 | backlog |
| [B17](B17-slot-openings-and-tooth-tips.md) | Slot openings, tooth tips and parallel-tooth slots | T49 | backlog |
| [B18](B18-rafm-3d-check.md) | 3D field check of the raxial machine | T55 | backlog |

## Conventions

- Names of machines, layouts and windings follow `docs/naming.md`.
- Code lives in the `emachine/` package (layout: `docs/architecture.md`); the old `tfm/` modules
  and `tfm_*.py` scripts are compatibility wrappers. Tests live in `tests/`: `unit/` by package,
  `tickets/` by ticket (`test_t27_staggered_teeth.py`), `characterization/`. Run them with
  `.venv/bin/python -m unittest discover tests`.
- Tests that need Gmsh, Elmer or ParaView are slow. They are skipped unless `EMACHINE_SLOW=1`
  (or `TFM_SLOW=1`) is set.
- Every ticket lists acceptance criteria and test cases. A ticket is `done` only when all its
  test cases pass, and its "Result" section records what was run and what came out. Progress of
  the restructuring is also kept in `CHANGELOG.md`.
- Only the Python standard library, NumPy and Gmsh are used, so nothing else needs installing.
