# Design parameters of the machines

Which quantities describe a radial, axial or transverse flux machine, and which of them the user
gives (specification), the optimizer chooses (design variables), or the model works out (derived).
Agreed with the user on 2026-10-17 (ticket T48); tickets T49 to T52 make the code follow it.

## Rules

1. **The specification fixes the envelope and the requirements**: outer diameter, stack (axial)
   length, air gap, bore (shaft) diameter, phases, slots, rotor placement, the winding choices,
   limits and materials.
2. **Design variables are what a designer draws**: lengths in mm (yoke height, slot height and
   width, magnet thickness, ...), counts (pole pairs) and, where a part covers a share of a pole,
   its **arc in electrical degrees** (magnet arc 150 el. deg, TFM tooth arc 144 el. deg) or, for the
   switched reluctance machine, the pole arcs in mechanical degrees (beta_s, beta_r of the
   literature).
3. **No ratio of a derived room.** A variable never is a fraction of a length that itself depends on
   other variables (the former `bore_ratio`, `tooth_ratio`, `slot_depth_ratio`,
   `magnet_width_ratio`, `insulation_ratio`, `magnet_fill_ratio`, `rotor_pole_arc_ratio`): the same
   value meant a different part size in every design, and the dialog could not be read as a
   drawing. An arc in electrical degrees is not such a ratio: 120 el. deg is the same magnetic
   shape for every pole count (it removes the third harmonic of the magnet field).
4. **One closing dimension per direction is derived**, so the parts always fill the envelope:
   - RFM and TFM with an inner rotor: from the outer diameter inwards come yoke, slot, air gap,
     magnet; the rotor core between the magnets and the shaft is what is left.
   - Outer rotor (TFM): from the outer diameter inwards come rotor iron, magnet, air gap, the
     stator; the stator ends where its slot and yoke end, and must clear the bore.
   - AFM: along the axis the stator(s), air gaps and magnets are chosen; the rotor back iron is
     what is left of the axial length.
5. **Every derived dimension is checked** against the limits (minimum iron thickness, minimum slot
   width, ...); a check names the dimension, so the dialog and the optimizer say what to change.
6. Drawing details that do not change the magnetic design much stay constants of the geometry,
   listed at the end, until a ticket makes them options.

Names: `_mm` lengths, `_el_deg` electrical degrees, `_deg` mechanical degrees, `_A_mm2` current
density; no suffix: a count.

## Specification (all machines)

| Key | Unit | Meaning |
|---|---|---|
| `machine.flux_path`, `principle`, `rotor`, `stator`, `rotor_placement` | | the machine (docs/naming.md) |
| `machine.phases` | | number of phases |
| `machine.outer_diameter_mm` | mm | outer diameter of the active parts |
| `machine.stack_length_mm` | mm | RFM: lamination stack; TFM: all phases with their spacing; AFM: axial length of the discs (stators, gaps, magnets, rotor back iron) |
| `machine.air_gap_mm` | mm | mechanical air gap |
| `machine.bore_diameter_mm` | mm | shaft (inner rotor) or free bore inside an inner stator |
| `machine.slots` | | stator slots (RFM, AFM) |
| `machine.rotor_poles` | | rotor poles (SRM) |
| `machine.barriers` | | flux barriers per pole (SynRM) |
| `machine.arrangement` | | AFM: `single`, `double_rotor`, `double_stator` |
| `machine.phase_spacing_mm`, `pole_shift_el_deg` | mm, el. deg | TFM: axial gap between phases, shift of the phases |
| `winding.*` | | span, layers, pitch, slot class, conductor, coil clearance and margin |

## Radial flux machine (RFM), inner rotor

Stator: parallel-sided (rectangular) slots, open at the bore, as drawn by
`machines/rfm/section.py` and the eMachine feature.

| Quantity | Kind | Name | Unit | How |
|---|---|---|---|---|
| pole pairs | variable | `pole_pairs` | | not SRM |
| slot height (radial depth) | variable | `slot_height_mm` | mm | |
| slot width | variable | `slot_width_mm` | mm | constant over the slot height |
| stator yoke height | variable | `yoke_height_mm` | mm | |
| current density | variable | `current_density_A_mm2` | A/mm2 | |
| bore radius (stator, at the gap) | derived | | mm | outer radius - yoke - slot height |
| slot pitch at the bore | derived | | mm | 2 pi r_bore / slots |
| tooth width at the bore | derived, checked | | mm | slot pitch - slot width (the narrowest place of the tooth) |
| slot area | derived | | mm2 | slot width x slot height (less the arc at the bore) |
| rotor radius | derived | | mm | bore radius - air gap |
| rotor core (yoke) | derived, checked | | mm | rotor radius - magnets (or barriers, teeth) - shaft radius |

Rotor layouts:

| Layout | Variable | Unit | Meaning |
|---|---|---|---|
| `surface` | `magnet_thickness_mm` | mm | radial magnet thickness |
| | `magnet_arc_el_deg` | el. deg | arc of a magnet; 180 = full pole |
| `interior` | `magnet_thickness_mm` | mm | thickness of a bar |
| | `magnet_length_mm` | mm | length of each bar of the V |
| | `v_angle_deg` | deg | opening angle of the V; 180 = one flat bar |
| | `bridge_mm` | mm | iron between the magnets and the rotor surface |
| `flux_barrier` | `barrier_width_mm` | mm | radial width of each barrier (all the same) |
| | `rib_mm` | mm | iron rib at the rotor surface and at the shaft |
| `flux_barrier_pm` | the above and `magnet_width_mm` | mm | magnet in the middle of each barrier, width across the q axis |
| `salient` (SRM) | `rotor_pole_arc_deg` | deg | rotor pole arc beta_r |
| | `rotor_pole_height_mm` | mm | rotor pole (tooth) height |

SRM stator: the stator pole is the tooth; its arc beta_s at the bore is derived from the slot width
and checked with beta_r against the feasible region of Lawrenson: min(beta_s, beta_r) >= 360 / (m
N_r) (self-starting), beta_s + beta_r <= 360 / N_r (both poles fit in one rotor pole pitch).

## Axial flux machine (AFM)

The active annulus lies between the inner diameter (variable) and the outer diameter (spec). Slots
are rectangular (constant width), so the teeth widen outwards; the tooth is narrowest at the inner
diameter.

| Quantity | Kind | Name | Unit | How |
|---|---|---|---|---|
| pole pairs | variable | `pole_pairs` | | not SRM |
| inner diameter of the annulus | variable | `inner_diameter_mm` | mm | |
| slot height (axial depth) | variable | `slot_height_mm` | mm | |
| slot width | variable | `slot_width_mm` | mm | |
| stator yoke height (axial) | variable | `yoke_height_mm` | mm | double rotor: yoke between the two slotted faces |
| magnet thickness (axial) | variable | `magnet_thickness_mm` | mm | `surface` |
| magnet arc | variable | `magnet_arc_el_deg` | el. deg | `surface` |
| current density | variable | `current_density_A_mm2` | A/mm2 | |
| active radial length | derived | | mm | (outer - inner diameter) / 2: the "stack" of a turn |
| tooth width at the inner diameter | derived, checked | | mm | 2 pi r_i / slots - slot width |
| rotor back iron (axial) | derived, checked | | mm | what the stators, gaps and magnets leave of the axial length, per rotor disc |
| mean radius | derived | | mm | |

## Transverse flux machine (TFM)

| Quantity | Kind | Name | Unit | How |
|---|---|---|---|---|
| pole pairs | variable | `pole_pairs` | | |
| tooth (core) arc | variable | `tooth_arc_el_deg` | el. deg | circumferential width of a core, at the gap; 180 = full pole pitch (was `tooth_span` x 180) |
| leg width | variable | `leg_width_mm` | mm | axial width of a leg |
| slot height | variable | `slot_height_mm` | mm | coil window, radial |
| yoke height | variable | `yoke_height_mm` | mm | |
| magnet thickness | variable | `magnet_thickness_mm` | mm | spoke: tangential magnet width |
| magnet arc | variable | `magnet_arc_el_deg` | el. deg | surface and axial-ring rotors |
| spoke magnet height | variable | `magnet_height_mm` | mm | spoke rotor |
| rotor iron | variable | `rotor_iron_mm` | mm | outer rotor: housing behind the magnets |
| I-bridge height | variable | `bridge_height_mm` | mm | UI core |
| ring tooth height | variable | `ring_tooth_height_mm` | mm | toothed ring |
| tooth tip overhang, tip height | variables | `ring_tip_overhang_mm`, `ring_tip_height_mm` | mm | toothed ring with `machine.ring_tooth_tips` (T73): axial reach of each tooth tip over the coil slot, and its radial thickness; the coil sits below the tips |
| magnet pocket overhang | variable | `magnet_overhang_mm` | mm | `machine.rotor_magnet_slots` (T71): how far each of the two magnet pockets reaches from its side wall over the coil slot |
| claw root height, tip height, tip gap | variables | `claw_root_height_mm`, `claw_tip_height_mm`, `claw_tip_gap_mm` | mm | claw pole (the tip was 0.5 x root) |
| current density | variable | `current_density_A_mm2` | A/mm2 | |
| width of one phase | derived | | mm | (stack - (m-1) spacing) / m |
| slot width | derived, checked | | mm | phase width - 2 legs |
| stator air-gap radius, rotor radius | derived | | mm | rule 4 |
| rotor core (inner rotor) | derived, checked | | mm | rule 4 |
| coil height and width | derived, checked | | mm | slot less clearance, margin, I-bridge |

TFM SRM (B12): `rotor_tooth_arc_el_deg` (was `rotor_tooth_ratio`).

## Radial-axial ("raxial") machine (RAFM, hybrid; T53)

One rotor around and on both ends of a toroidally wound SMC stator. Radial chain from the outer
diameter inwards; axial chain from the total length (spec `stack_length_mm`) inwards, closed by
the stator core length.

| Quantity | Kind | Name | Unit | How |
|---|---|---|---|---|
| pole pairs | variable | `pole_pairs` | | |
| radial rotor iron | variable | `rotor_iron_mm` | mm | ring outside the radial magnets |
| radial magnet thickness, arc | variables | `magnet_thickness_mm`, `magnet_arc_el_deg` | mm, el. deg | |
| radial tooth height | variable | `radial_tooth_height_mm` | mm | from the yoke to the radial gap |
| radial tooth (and magnet) axial length | variable | `radial_tooth_length_mm` | mm | |
| yoke width | variable | `yoke_width_mm` | mm | radial; also the radial extent of the axial teeth and magnets |
| axial tooth height | variable | `axial_tooth_height_mm` | mm | from the yoke end face to the axial gap |
| disc iron | variable | `disc_iron_mm` | mm | rotor discs |
| axial magnet thickness, arc | variables | `axial_magnet_thickness_mm`, `axial_magnet_arc_el_deg` | mm, el. deg | |
| slot width | variable | `slot_width_mm` | mm | parallel-sided; the same for radial, axial and inner slots |
| slot opening, tooth tip height | variables | `slot_opening_mm`, `tooth_tip_height_mm` | mm | tips of the radial and the axial teeth |
| coil thickness | variable | `coil_thickness_mm` | mm | build of the toroidal coil around the yoke |
| current density | variable | `current_density_A_mm2` | A/mm2 | |
| stator radius | derived | | mm | outer radius - rotor iron - magnet - gap |
| yoke radii | derived | | mm | stator radius - radial tooth height; - yoke width |
| stator core length | derived, checked | | mm | total length - 2 (gap + axial magnet + disc iron) |
| yoke axial length | derived, checked | | mm | core length - 2 axial tooth heights |
| tooth widths | derived, checked | | mm | radial teeth at the yoke, axial teeth at the yoke's inner radius |
| coil fits | derived, checked | | mm | radial slot, axial slot and the room between bore and yoke |
| mean turn | derived | | mm | loop around the yoke section |

## Constants of the geometry (not design variables)

| Constant | Value | Where | Why not a variable |
|---|---|---|---|
| I-bridge taper | top 0.8 x slot width | `emachine/machines/tfm/design.py` BRIDGE_TOP_RATIO | shape of the chamfer of the I-bridge; little effect on the flux. Candidate for an option in mm |
| Halbach segments per pole | 2 | `emachine/machines/tfm/design.py` | a manufacturing choice; option when needed |
| slot opening, tooth tips | open slots | RFM, AFM | slot openings and tooth tips are backlog B17 (they need a new slot shape in the mesher and the CAD) |
| salient TFM SRM rotor | | B12 | not built |

## Old names (still read)

Designs and seeds saved with the old names are converted when they are read
(`emachine.spec.names.standard_values`):

| Old | New | Conversion |
|---|---|---|
| `tooth_span` (TFM) | `tooth_arc_el_deg` | x 180 |
| `magnet_arc_ratio` | `magnet_arc_el_deg` | x 180 |
| `yoke_mm` | `yoke_height_mm` | the stator now fills the outer diameter: yoke = outer radius - bore radius - slot height |
| `bore_ratio`, `slot_depth_ratio`, `tooth_ratio` | `slot_height_mm`, `slot_width_mm` | from the outer radius and the slots: same bore, slot and tooth as before |
| `claw_tip_height_mm` missing | `claw_tip_height_mm` | max(minimum iron, 0.5 x root), the former rule |
| `rotor_pole_arc_ratio` | `rotor_pole_arc_deg` | x 360 / rotor poles |
| `stator_pole_arc_ratio` | (derived) | dropped: the stator pole is the tooth |
| `magnet_width_ratio`, `insulation_ratio`, `magnet_fill_ratio` | `magnet_length_mm`, `barrier_width_mm`, `magnet_width_mm` | not converted (these rotors are drawn only, no run used them): a design with them stops with the new name |

A specification whose `variables` section bounds an old ratio that cannot be converted without the
other values stops with a message that names the new variable.
