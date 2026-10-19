# T63: Topology catalogue and optimization runs in the ILM-E85x23 envelope

Status: done
Depends on: T58 to T62

## Scope

`python -m emachine study --config multi-topology-analysis/study.json`: one NSGA-II run per
topology (objectives rated torque, peak torque, ripple; constraints of T58), designs evaluated in
parallel processes; per topology the picks "optimal" (highest rated torque with ripple <= 25 % and
efficiency >= 80 %) and "highest torque" (efficiency >= 80 %, any ripple); finalists verified with
more rotor positions, cogging and step skew.

## Acceptance criteria

- [x] Every topology of the catalogue has a run (17 topologies; 46 to 140 designs each after the budgets were cut
      at 04:00 to finish overnight; the reason is noted below), or a reason.
- [x] Picks and finalist verification in `multi-topology-analysis/runs/<topology>/` (`picks.json`, `verify/`).

## Result

2026-10-18, runs in `multi-topology-analysis/runs/` (logs `study*.log`; superseded runs kept in `runs/_superseded/`
with the reason in their folder name). Budgets: 20 x 6 (first topology), then 16 x 5 and 10 to 14 x 4 (cut at
04:00 so the study finished overnight; convergence was reached by generation 3 in the first runs).

Problems found during the runs and fixed (each topology affected was run again):
- turns were not capped by the current density limit (all YASA designs violated it; AFIR, YASA rerun);
- parametrizations that made almost every design undrawable: dual-stator vernier yoke as a share of the wide
  vernier tooth (none drawable), interior-V apex depth independent of the bar thickness, spoke depth absolute,
  SRM pole arcs outside Lawrenson's triangle, wide-pole 6/4 and 6/8 SRMs (reruns);
- the phase sequence derived from the winding was inverted (magnet-free machines only); now the sequence of a
  magnet-free machine is found from the field (torque averaged over three positions cancels with the wrong one);
- axial rotor discs of solid steel lost up to 117 W in slot-harmonic eddy currents in the verification (36
  positions) that the 12-position optimization sweep did not resolve: the axial picks were verified again with
  tape-wound laminated discs (the solid-disc results are kept as `verify/*_solid_disc.json`);
- picks for topologies with no feasible design: the closest design ("closest").

Verified results: see `multi-topology-analysis/report/report.html` (table) and the findings there.
