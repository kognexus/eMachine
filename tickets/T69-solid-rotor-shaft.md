# T69: SynRM, PMaSynRM and interior PM with a 12 mm shaft

Status: done
Depends on: T63

## Why

The user (2026-10-18): the flux barriers of the SynRM and PMaSynRM are cut in the middle by the 52 mm bore; for
these and for the interior PM machine the shaft may be reduced to 12 mm diameter.

## Scope

- Per-topology bore in the study configuration (`bore_overrides`): 12 mm for `rfm_synrm`, `rfm_pmasynrm`,
  `rfm_ipm_v`; the stator and the outer diameter unchanged. The air-gap radius range follows the bore.
- Optimization and verification again; the report states the bore of these three.

## Acceptance criteria

- [x] Sketches show whole flux barriers and V magnets in a solid rotor down to the 12 mm shaft.
- [x] New runs verified and compared with the 52 mm-bore runs.

## Result

2026-10-18. `bore_overrides` in study.json (12 mm for rfm_synrm, rfm_pmasynrm, rfm_ipm_v; `topology_study.envelope_for`);
the gap radius range keeps at least 0.45 of the outer radius. Interior V: apex depth up to 0.45 of the rotor radius;
q = 1 (12/4, 18/6, 24/8) and 12/8, 18/12 windings added.

| Topology | 52 mm bore: rated / peak torque, efficiency | 12 mm shaft |
|---|---|---|
| SynRM (closest: no design reaches 80 %) | 0.23 / 1.06 Nm, 27 % | 0.46 / 1.83 Nm, 46 % |
| PMaSynRM (ferrite) | 0.27 / 1.37 Nm, 82 % | 0.32 / 1.47 Nm, 86 % |
| Interior V | 1.33 / 5.17 Nm, 81 % | 1.50 / 3.98 Nm, 81 % |

Whole barriers double the SynRM's torque, but the magnet-free machines stay far below the PM machines on this
drive: their torque grows with the square of the ampere-turns and 10.5 A at 10 A/mm2 gives too few. For the interior
V, few poles leave room for long bars, but hand-checked 24/8 designs give only 0.2 to 0.3 Nm (four pole pairs; q = 1
end turns cost copper under the 80 % efficiency limit).

Incident: while restarting the slice check a too broad `pkill` stopped the worker processes of these runs; they
resumed from their saved generations (`state.json`), one generation each was repeated.
