# T67: Axial machines: 3D view as discs, and convergence in the number of slices

Status: done
Depends on: T60, T65

## Why

The user (2026-10-18): the axial flux machines look like strips, not pancakes; how much of the analysis can be
believed? The quasi-3D model solves cylinder cuts (slices) at 2 (optimization) or 3 (verification) radii; the
ParaView export drew those cuts as thin cylinder bands. Only one check existed (a slice equals the radial model
of the same machine at a large radius, T60-2); the number of slices was never tested.

## Scope

- Export: every slice extruded over its radial band (wedge cells between r - dr/2 and r + dr/2), so the machine
  appears as stacked discs with sector teeth and magnets; a view with a quarter cut away.
- The axial picks solved again with 5 slices (and the 3 of the verification): rated and peak torque, EMF,
  losses; the change is reported.

## Acceptance criteria

- [x] ParaView pictures of every axial pick as discs (`paraview/afm_*/views/materials_discs.png`, `rated_discs.png`).
- [x] Rated and peak torque with 5 slices against 3 slices, every axial pick; the report states the difference.

## Result

2026-10-18. `topology_export.write_discs` (wedge cells over each slice's radial band), views with half cut away,
facing the cut. `python -m emachine.analysis.topology_study --slice-check ...` (results `runs/slice_convergence.json`,
`verify/*_5slices.json`). A bug was found on the way: `gauss_slices` knew only 1 to 3 points and silently used 3
for 5; now numpy's Gauss-Legendre points for any n.

| Pick | 3 slices: rated / peak torque (Nm), efficiency | 5 slices |
|---|---|---|
| afm_afir | 3.130 / 11.87, 83.7 % | 3.131 / 11.87, 83.7 % |
| afm_yasa | 2.761 / 10.85, 84.4 % | 2.760 / 10.84, 84.3 % |
| afm_ss | 2.761 / 7.56, 82.1 % | 2.761 / 7.57, 82.1 % |
| afm_coreless | 0.495 / 1.98, 86.8 % | 0.495 / 1.98, 86.8 % |
| afm_srm (closest) | 0.109 / 0.89, 37.2 % | 0.106 / 0.89, 37.1 % |

The 3-point Gauss integration over the radius has converged. The pictures also explain why the axial machines do
not win here: with 52 mm inside and 85 mm outside the active ring is about 12 mm wide and 30 mm long.
