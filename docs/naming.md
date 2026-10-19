# Naming standard

The names used for machines, their parts and their windings: in specifications, in the code
(registry keys, modules, classes), in reports and in the documentation. Agreed with the user on
2026-10-16; the code follows it with tickets T43 to T46. Old names stay readable as aliases
(table at the end).

## A machine is three choices

| Axis | Spec key | Meaning | Values |
|---|---|---|---|
| 1 | `machine.flux_path` | direction in which the flux crosses the air gap | `tfm`, `rfm`, `afm`, `rafm` |
| 2 | `machine.principle` | how torque is produced | `pmsm`, `synrm`, `srm`, `vernier` |
| 3 | `machine.rotor` | rotor layout: where the magnets or the flux barriers are | per principle, below |

The registry key of a machine is `<flux_path>/<principle>`, for example `rfm/pmsm`. The rotor
layout is an option of that machine, checked against the layouts the machine offers. Flux path and
principle together form the **machine matrix** (`emachine list`, ticket T45; the
current state is in [machines.md](machines.md)). The Onshape feature "eMachine" offers the same
names in its dialog (T47). The design variables of each machine (lengths and arcs) are in
[parameters.md](parameters.md).

### Flux path

| Value | Name | The flux crosses the gap |
|---|---|---|
| `tfm` | transverse flux machine | radially, but its path closes in planes that contain the axis (ring coil, U or claw cores) |
| `rfm` | radial flux machine | radially, path in the cross-section |
| `afm` | axial flux machine | axially, between discs |
| `rafm` | radial-axial ("raxial") flux machine | through radial and axial gap faces of the same rotor (3D flux path) |

**Hybrid machines** collect the flux paths that combine gap directions or other exotic
topologies; `rafm` is the first (T53: the ARF-PMSM of Zhang et al. 2023, an SMC stator with
radial and axial teeth, a toroidal winding, magnets on an outer rotor ring and two rotor discs).
Their Onshape features live in their own studio, `hybrid_design.fs` (T54). `raxial` is read as
`rafm`.

### Torque principle

| Value | Name | Torque from | Magnets |
|---|---|---|---|
| `pmsm` | permanent magnet synchronous machine | alignment of magnet and stator field (plus reluctance torque with interior magnets) | yes |
| `synrm` | synchronous reluctance machine | rotor anisotropy (d and q inductance differ), sinusoidal currents | none, or assisting magnets in the barriers (PMaSynRM) |
| `srm` | switched reluctance machine | salient stator and rotor poles, phases switched one after the other | none |
| `vernier` | (PM) vernier machine | flux modulation: few stator poles drive many rotor poles, magnetic gearing | yes |

### Rotor layout

| Principle | `machine.rotor` | Common name |
|---|---|---|
| `pmsm`, `vernier` | `surface` | surface magnets (SPM) |
| | `inset` | inset magnets |
| | `interior` | interior magnets (IPM); magnet shape (bar, V, delta) is a further option |
| | `spoke` | spoke or flux-concentrating magnets |
| | `halbach` | Halbach array |
| | `axial_ring` | ring magnet magnetised along the axis between two toothed discs (TFM) |
| `synrm` | `flux_barrier` | SynRM |
| | `flux_barrier_pm` | PM-assisted SynRM (PMaSynRM) |
| `srm` | `salient` | toothed iron rotor |

Not every layout fits every flux path; each machine lists the layouts it supports.

## Stator

| Spec key | Values |
|---|---|
| `machine.stator` | TFM: `u_core`, `ui_core`, `c_core`, `e_core`, `z_core`, `claw_pole`, `toothed_ring`. RFM, AFM: `slotted` (later `slotless`). RAFM: `toroidal` (teeth on the outer cylinder and both end faces, coils around the yoke) |
| `machine.rotor_placement` | `inner` or `outer` (inner rotor or outer rotor) |
| `machine.arrangement` | AFM: `single` (one stator, one rotor), `double_rotor` (rotor-stator-rotor), `double_stator` (stator-rotor-stator) |
| `machine.slots` | number of stator slots (RFM, AFM) |

## Winding

The section `winding` describes the winding with three choices; the slot class follows from the
slot and pole numbers.

| Spec key | Values | Meaning |
|---|---|---|
| `winding.span` | `concentrated`, `distributed`, `ring`, `toroidal` | tooth coils (one slot pitch), overlapping coils (several slots), one ring coil around the axis (TFM), one coil around the yoke in every slot (RAFM; "annular" winding) |
| `winding.layers` | `1`, `2` | coil sides per slot |
| `winding.pitch_slots` | `null` or a number | coil span in slots; `null`: 1 for concentrated, full pitch for distributed. A smaller number is short pitching |
| `winding.slot_class` | `any`, `integral`, `fractional` | restricts the slot and pole numbers the optimizer may choose |

Slots per pole and phase: **q = Q / (2 p m)** (Q slots, p pole pairs, m phases). Integral slot:
q is a whole number; fractional slot: it is not.

| Label | Span | q | Example |
|---|---|---|---|
| **FSCW** | concentrated | fractional | 12 slots, 10 poles, q = 0.4 |
| **FSDW** | distributed | fractional | 18 slots, 4 poles, q = 1.5 |
| **ISDW** | distributed | whole | 36 slots, 6 poles, q = 2 |
| **ring** | ring | not defined | TFM, claw pole |
| **toroidal** | toroidal | Q / (2 p m) | RAFM, 24 slots, 20 poles: k_w1 = 0.966 |

Reports print the label with q, the layers and the fundamental winding factor.

## Short names in text

TFM, RFM, AFM, RAFM; PMSM, SPM, IPM, SynRM, PMaSynRM, SRM, PMVM (PM vernier machine); FSCW, FSDW,
ISDW. A design is described as `<FLUX PATH>-<PRINCIPLE> (<rotor>), <winding label>, <Q>s<2p>p`,
for example "RFM-PMSM (surface), FSCW, 12s10p".

## Code

- Modules: `emachine/machines/<flux_path>/<principle>.py`, one per principle (for example
  `machines/rfm/synrm.py`, `machines/tfm/pmsm.py`); rotor and stator layouts in
  `machines/<flux_path>/rotors/<layout>.py` and `stators/<layout>.py`.
- Classes: `<FluxPath><Principle>`, for example `RadialFluxPMSM`, `TransverseFluxSRM`.
- `Machine` attributes: `flux_path`, `principle`, `rotors` (supported layouts).

## Old names (still read)

| Old | New |
|---|---|
| `machine.family` | `machine.flux_path` |
| `machine.topology` | `machine.principle` |
| `rfm/ipm` | `rfm/pmsm` with `machine.rotor` = `interior` |
| `rfm/pmasynrm` | `rfm/synrm` with `machine.rotor` = `flux_barrier_pm` |
| `machine.configuration`: `inrunner`, `outrunner` | `machine.rotor_placement`: `inner`, `outer` |
| `machine.stator_type`: `u`, `ui`, `c`, `e`, `z`, `cp`, `tr` | `machine.stator`: `u_core`, `ui_core`, `c_core`, `e_core`, `z_core`, `claw_pole`, `toothed_ring` |
| `machine.rotor_type`: `flux_concentrating`, `axial` | `machine.rotor`: `spoke`, `axial_ring` (others unchanged) |
| `machine.winding`: `concentrated`, `distributed` | `winding.span` |
| `machine.sides`: 1, 2 | `machine.arrangement`: `single`, `double_rotor` |

A specification with old names loads as before, and the normalised spec saved with a run uses the
new names.
