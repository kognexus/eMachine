# T64: Interactive Pareto charts and the comparison report against the ILM-E85x23

Status: done
Depends on: T63

## Scope

- `multi-topology-analysis/report/pareto.html`: interactive (self-contained, no internet), one
  population per topology, hover and click for the design values, topology filter, axes choice.
- `multi-topology-analysis/report/report.md` and `report.html`: every topology introduced (sketch,
  principle, winding), the design principles applied, the comparison table against the ILM-E85x23,
  phase voltage figures, ParaView pictures, conclusions and open model questions.

## Acceptance criteria

- [x] pareto.html opens offline and shows every run (checked headless in Chrome; light and dark).
- [x] Table: rated torque, kT, peak torque, ripple, cogging, efficiency, losses, motor constant, torque at the
      ILM-E's copper loss, winding (turns, paths, strands x AWG, fill), current densities, line voltage, magnet
      and active mass, peak torque per mass, axial length, limits met in the verification; against the ILM-E85x23
      datasheet and the ILM-E model (T66).

## Result

2026-10-18. `emachine/analysis/topology_report.py`: `report/report.md`, `report.html`, `pareto.html` (self-contained,
one topology at a time, any two quantities as axes, Pareto front ringed, picks marked, hover and click),
figures per verified pick: section sketch, phase voltages / flux linkages / line voltage against the DC link /
currents (Motor-CAD style), back-EMF, torque and cogging; speed sensitivity table and chart; findings
(`report/findings.md`, written from the results). Charts follow the dataviz skill (categorical slots 1 to 3,
one axis per chart).
