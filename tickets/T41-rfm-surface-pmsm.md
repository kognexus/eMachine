# T41: Radial-flux surface PMSM end to end

Status: done
Depends on: T35, T36, T40

## Why

One complete non-TFM machine proves the interfaces: geometry, solver, winding, losses, map and
optimization for a radial-flux surface PMSM.

## Work

1. `machines/rfm/pmsm.py` geometry: 2D cross-section of one pole-pair sector (slots, teeth, yoke,
   magnets, rotor yoke), Gmsh builder "rfm.section2d" with a sliding band.
2. Distributed and concentrated windings (slot matrix), all phases in one solution.
3. `solvers/elmer/section2d.py`: 2D magnetostatics (MagnetoDynamics2D), torque, flux per phase.
4. Validation against analytic air-gap field and back-EMF, and against a published or open
   reference machine.

## Acceptance criteria

- [x] Map and optimization run for an RFM PMSM spec
- [x] Back-EMF and torque within tolerance of the reference (analytic; published machine: B13)
- [x] No change to pipeline or optimizer code needed (pipeline generalized once: all-phase sweep, loss share)

## Test cases

| ID | Test | Expected |
|---|---|---|
| T41-1 | Slot matrix of 12-slot 10-pole and 36-slot 4-pole windings | Winding factors as tabulated |
| T41-2 (slow) | 2D mesh of the sector | Region areas, periodic match |
| T41-3 (slow) | No-load flux and torque | Torque = 3/2 p psi NI within 2 %; flux within 20 % of the analytic air-gap estimate; cogging < 5 % |
| T41-4 (slow) | Map of the reference machine | Runs; limits respected |

## Result

Reference machine `specs/rfm_spm_12s10p.json` (12 slots, 10 poles, 100 mm, 40 mm stack, 0.7 mm gap,
3 mm magnets, laminated rotor) with the design `specs/rfm_spm_12s10p_design.json`.

- Geometry `rfm.section2d` (`machines/rfm/section.py`, `builder.py`): the whole 2D cross-section,
  meshed again at every rotor position (no sliding band: simpler, about 1.5 s per mesh).
- Winding by slot star (`winding_layout.py`): winding factors 0.933 (12s10p) and 0.960 (36s4p).
- Solver `elmer2d` (`solvers/elmer/section2d.py`): MagnetoDynamics2D, all three phase currents in
  one solution, Arkkio torque, flux per phase from the coil sides, core field file for the losses.
- Results: no-load flux 1.76 mWb per turn; loaded torque 2.054 Nm against 3/2 p psi NI = 2.060 Nm
  (0.3 %); analytic air-gap estimate with Carter factor 2.05 mWb (FEM 17 % lower: open slots,
  leakage); cogging 0.02 Nm peak to peak (1 %).
- Map: 87.6 % at the design point (1500 rpm, 2.05 Nm), best 88.3 % at 1473 rpm and 2.9 Nm,
  standstill torque 3.1 Nm continuous and 6.2 Nm peak, no-load speed 1575 rpm. Optimization
  (8 x 2 generations, field solver) 1.5 min; dry run with the analytic stand-in, which now covers
  the surface PM machine.
- Bug found and fixed: the 2D field file holds all phases, but the loss model treated it as one
  phase (as the TFM sector) and the evaluation multiplied by the phase count, so the radial flux
  iron and rotor losses were 3 times too high. Field files now carry `phases`, and
  `physics.losses.iron_loss_coefficients` shares the loss out per phase (TFM unchanged:
  characterization tests pass).
- Tests: `tests/unit/machines/test_rfm_pmsm.py` (T41-2 to T41-4, slow), winding layout (T41-1),
  analytic stand-in and loss share (fast), RFM dry-run optimization (fast).
- Full slow suite after T41: 323 tests pass (1 skipped).
- Open, in B13: ParaView export and CAD of radial machines, comparison with a published machine,
  lamination steel data (the stator core uses the SMC default).
