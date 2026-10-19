# B17: Slot openings, tooth tips and parallel-tooth slots (RFM, AFM)

Status: backlog
Depends on: T49

## Why

The slotted stators have open, parallel-sided slots (T49). Semi-closed slots (slot opening
`slot_opening_mm`, tooth tip height `tooth_tip_height_mm`) lower cogging and the Carter factor;
parallel teeth (trapezoidal slots, `machine.slot_shape` = `parallel_tooth` with `tooth_width_mm`)
keep the tooth flux density even and are usual for distributed windings.

## Scope

Option `machine.slot_shape` (`parallel_slot`, `parallel_tooth`) and the variables above, in the
mesher, the CAD feature and `derive`.
