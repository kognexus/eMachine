# T10: Thermal model

Status: done
Depends on: T09

## Why

Losses heat the winding and the magnets. The design must stay below their temperature limits,
and copper resistance rises with temperature.

## Scope

`tfm/thermal.py`: a steady-state lumped thermal network.

- Generic solver: nodes with heat input, conductances between nodes and to ambient.
- Network for the machine, per phase: winding, stator core, rotor (magnets), ambient.
  - Winding to core: slot insulation plus half the winding thickness, over the coil surface that
    touches the core.
  - Core to rotor: convection across the air gap over the pole-face area.
  - Core to ambient: through the stator mounting surface (bore for an inner stator, outer
    surface for an outer stator).
  - Rotor to ambient: convection from the rotor outer surface (outrunner) or end faces
    (inrunner).
- Heat-transfer coefficients and insulation data come from the `thermal` section of the
  specification, with documented defaults.
- Coupling: copper loss depends on winding temperature. Iterate to a fixed point.
- Outputs: winding, core and magnet temperatures, and the copper loss at temperature.

This is a simplified model with assumed coefficients. A finite-element check is ticket B03.

## Acceptance criteria

- [x] The network solver reproduces hand results for one and two resistances.
- [x] Energy balance: heat leaving to ambient equals total heat input within 1e-9.
- [x] Temperatures rise monotonically with loss and fall with better cooling.
- [x] The temperature and copper-loss iteration converges, or reports that it does not.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T10-1 | One node, 10 W, 2 K/W to ambient at 25 C | 45 C |
| T10-2 | Two nodes in series, 10 W into the first, 1 K/W and 2 K/W | 55 C and 45 C |
| T10-3 | Machine network, any losses | Sum of flows to ambient equals total loss within 1e-9 |
| T10-4 | Double the copper loss | Winding temperature rise increases |
| T10-5 | Double the external heat-transfer coefficient | All temperatures decrease |
| T10-6 | Coupled iteration with 5 W copper loss at 20 C | Converges in under 20 iterations, loss at temperature > 5 W |
| T10-7 | Loss so high that the fixed point runs away | Reported as not converged, treated as a violated limit |

## Result

Completed 2026-10-13.

- `tfm/thermal.py`: `solve_network`, `machine_conductances`, `temperatures`, `coupled`.
- Tests in `tests/test_t10_thermal.py`: T10-1 to T10-7 pass, plus parallel paths and an inrunner network.
- Reference design at 5 A/mm2 and 300 rpm: winding 64.8 C, core 53.3 C, magnets 39.5 C at 25 C
  ambient, converged in 5 iterations.
- T10-7: with almost no cooling and 60 A/mm2 the iteration is reported as not converged and the
  winding temperature exceeds the limit.
- This is a simplified network with assumed coefficients. It models one phase; the middle phase
  of a three-phase stack will run hotter than predicted. Ticket B03 checks it by finite elements.
