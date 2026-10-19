# T18: ParaView export of a design

Status: in progress
Depends on: T07, T09, B01

## Why

The user wants to inspect the optimized design in ParaView: the magnetic field as a vector map,
torque across rotor angles, and whatever else is needed to judge a motor.

## Scope

`tfm_paraview.py` solves one design over a full electrical period, keeps the fields and writes a
folder that ParaView opens directly.

Field files (time series, one step per rotor position; the rotor turns from step to step):

- `machine.pvd`: the solid parts only (stator cores, coil, magnets, rotor iron). Opening it shows
  the motor without any filter.
- `air.pvd`: the air regions, for field lines and slices through the gap.
- `airgap.pvd`: the cylinder in the middle of the air gap, with the radial flux density.

Data on the field files:

| Name | On | Meaning |
|---|---|---|
| `B` | points | flux density vector in T (the vector map: Glyph filter) |
| `B_magnitude` | points | its magnitude |
| `A` | points | vector potential in Wb/m |
| `B_radial`, `B_tangential`, `B_axial` | points | cylindrical components |
| `region` | cells | number of the part, listed in `regions.csv` |
| `material` | cells | 1 air, 2 copper, 3 magnet, 4 stator core, 5 rotor iron, 6 rotor housing |
| `side` | cells | 0 stator, 1 rotor |
| `B_cell` | cells | flux density vector of the element |
| `mu_r` | cells | relative permeability at the working point (saturation map) |
| `saturation` | cells | polarisation / saturation polarisation, 0 to 1 |
| `magnetization` | cells | magnet magnetisation vector in A/m (checks the magnet pattern) |
| `B_along_magnetization` | cells | magnet working point in T (demagnetisation check) |
| `current_density` | cells | coil current density vector in A/mm2 |
| `force_density`... | | not written: see "Not included" |

Step data (the same for all points of a step, so it can be shown as text or plotted over time):
`rotor_angle_deg`, `electrical_angle_deg`, `phase_current_A`, `torque_Nm`, `flux_linkage_Wb`.

Other files:

- `core_loss.vtu`: stator core with the peak flux density over the cycle and the loss density.
- `full_ring.vtu`: the solid parts of the whole ring at the position of highest torque.
- `waveforms.csv`: per rotor position: angles, current, phase torque, machine torque, cogging
  torque, flux linkage, induced voltage, terminal voltage, air-gap flux density under a leg.
- `harmonics.csv`: harmonics of machine torque, cogging torque and induced voltage.
- `airgap_profile.csv`: radial flux density around the gap at the middle of each leg, first step.
- `waveforms.svg`: the same curves as a picture, for a look without ParaView.
- `summary.md`: key numbers, the demagnetisation and saturation checks, how to open the files.
- `open_in_paraview.py`: optional script that builds the standard views.

Options: `--sectors N` repeats the sector N times in the time series, `--fidelity`, `--positions`,
`--skip-no-load` (no cogging torque and no no-load curves).

Not included: force density on the teeth (the solver writes nodal forces of the air mesh, which
are not a physical force density), end effects outside one phase, and eddy currents.

## Acceptance criteria

- [ ] Every `.vtu` file is valid VTK XML: point, cell and array counts agree with the headers.
- [ ] `.pvd` files list one existing file per rotor position with a rising time value.
- [ ] `machine.pvd` contains no air; `air.pvd` contains only air.
- [ ] The torque in `waveforms.csv` equals the torque of an evaluation of the same design.
- [ ] Magnetisation vectors have the magnitude Br / (mu0 * mu_r) and, for a Halbach rotor,
      alternate between radial and tangential from segment to segment.
- [ ] `mu_r` equals the initial permeability where the core is unloaded and falls where the flux
      density is high; with linear materials it is constant.
- [ ] Repeating the sector N times multiplies cells and volume by N and rotates the vectors.
- [ ] The mean of the radial air-gap flux density around the gap is zero within 2 % of its peak.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T18-1 | Write and read back a small mesh with point and cell data | Identical points, cells and data |
| T18-2 | Repeat a sector 4 times at 90 degrees | 4x cells, 4x volume; a radial vector stays radial in every copy |
| T18-3 | `mu_r` and `saturation` from a B-H table at B = 0, 1.0 and 2.5 T | Initial permeability at 0; falling with B; saturation between 0 and 1 |
| T18-4 | Harmonic table of a known waveform | Amplitudes and orders recovered |
| T18-5 | `.pvd` writer | One entry per step, files relative, time rising |
| T18-6 (slow) | Export of the reference design, fast fidelity, 6 positions per half period | All files exist and are valid; no air in `machine.pvd`; counts agree |
| T18-7 (slow) | Same export | Torque column equals `em.analyse` torque for the same positions within 0.5 % |
| T18-8 (slow) | Same export | Magnetisation magnitude = Br / (mu0 * mu_r) within 0.1 %; neighbouring Halbach segments are perpendicular within 1 degree |
| T18-9 (slow) | Same export | Mean radial air-gap flux density < 2 % of its peak; `core_loss.vtu` total loss equals the loss model within 1 % |
| T18-10 (slow) | Same export with linear materials | `mu_r` in the stator core is constant |

## Result

Code and tests completed 2026-10-13. The export of the optimized design is recorded below when
the optimization has finished.

- `tfm/vtkio.py` writes and reads `.vtu` and `.pvd` files as plain text in the layout Elmer
  uses; `tfm/fieldexport.py` runs the sweeps and derives the per-element quantities;
  `tfm_paraview.py` is the command.
- Tests in `tests/test_t18_paraview.py`: T18-1 to T18-5 pass; T18-6 to T18-10 pass with `TFM_SLOW=1`.
- Reference design (single phase, 6 positions per half period, fast fidelity), from the test run:
  torque equal to `em.analyse` within 0.5 %; magnetisation 985 245 A/m = Br / (mu0 * mu_r);
  the four Halbach directions present; mean radial air-gap flux density 0.0003 T against a peak
  of 1.05 T; core loss file total equal to the loss model within 1 %; with linear materials
  `mu_r` = 500 everywhere in the core.
- Size: 89 MB for 12 steps of one sector with air at fast fidelity (54 000 elements per sector).
- Changed while building:
  - "neighbouring Halbach segments are perpendicular" became "in the frame of each magnet the
    magnetisation is radial or tangential, and all four directions occur", which is what can be
    read from the file;
  - the flux density written is the element field (see ticket B05), the same as the loss model uses;
  - `region` numbers are those of step 0. Magnets crossing the sector boundary are renumbered in
    other steps, so `material` is the array to select by over time.
- **Not verified:** ParaView is not installed on this machine. The files were checked by reading
  them back and comparing counts and values, not by opening them in ParaView.
  `open_in_paraview.py` has not been run.
- For three phases the files show one phase (one sector of one ring). The waveform table holds
  the phase torque and the machine torque of all three phases.

EXPORT_RESULT
