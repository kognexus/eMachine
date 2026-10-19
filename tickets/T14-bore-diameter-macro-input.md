# T14: Bore diameter as a macro input

Status: done
Depends on: T02, T03, T04, T13

## Why

The machine has to fit between an outer diameter and a bore (the hole for a shaft, axle or
mounting). The user asked for the bore diameter to be a macro input next to outer diameter and
stack length.

## Scope

`machine.bore_diameter_mm` exists since T02 and is used by T03 and T04. This ticket makes it a
first-class macro input:

- Meaning, stated in one place: nothing solid may reach inside the bore diameter.
  - Outrunner (inner stator): the inner end of the stator cores stays at or outside the bore.
  - Inrunner (inner rotor): the bore is the shaft diameter; the rotor core fills the space from
    the shaft to the magnets and must keep the minimum iron thickness.
- Shown with the other macro inputs in the report.
- Result tables report the innermost solid diameter of every design, so the use of the bore
  can be checked.
- The upper bound of the slot-height variable takes the bore into account, so the optimizer does
  not waste samples on designs that cannot fit.

## Acceptance criteria

- [x] Changing the bore diameter changes which designs are feasible, for both configurations.
- [x] Every trade-off design of an optimization keeps its innermost solid diameter at or above the bore.
- [x] The report lists the bore diameter under the problem inputs.
- [x] The slot-height range shrinks when the bore grows.
- [x] A bore that leaves no room for a machine is rejected with a clear message.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T14-1 | Outrunner reference design with bore 20 mm, then 40 mm | Feasible, then `bore_clearance` violated |
| T14-2 | Inrunner design with shaft 30 mm, then 90 mm | Feasible, then `iron_rotor_min` violated; the rotor parameter `shaft_diameter` equals the bore |
| T14-3 | Slot-height upper bound for bore 10 mm and bore 50 mm (outrunner, 80 mm) | Smaller for the larger bore |
| T14-4 | Dry-run optimization with bore 30 mm | Every row of `pareto.csv` has inner diameter >= 30 mm; the report shows "Bore diameter" |
| T14-5 | Bore 78 mm in an 80 mm machine | `SpecError` saying there is no room between bore and outer diameter |

## Result

Completed 2026-10-13.

- The parameter existed since T02 (`machine.bore_diameter_mm`) and already constrained designs
  through T03 and T04. New in this ticket:
  - the report lists it with the other macro inputs;
  - `pareto.csv` and `all_designs.csv` have a column `inner_diameter_mm`, the innermost solid
    diameter of each design;
  - the upper bound of the slot-height variable now follows the room between bore and outer
    diameter: min(0.45 * outer radius, room - air gap - 1.5 mm magnet - 2 * minimum iron);
  - a bore that leaves less than 4 mm of slot height is rejected with a message.
- Tests in `tests/test_t14_bore.py`: T14-1 to T14-5 pass.
- For the default and the example specification the slot-height range is unchanged (18 mm), so
  earlier results and caches stay valid.
- Not modelled: the hub or carrier between the bore and the inner end of the stator cores of an
  outrunner. The bore is a keep-out diameter, not a part.
