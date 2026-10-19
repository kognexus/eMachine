# T71: Rotor magnet slots over the side walls, and Halbach segments per pole

Status: done (code and tests); measured effect in T74
Depends on: T27, T70

## Why

User's items 1 and 3 (T70): magnet slots against flux leakage; alternate or Halbach rotor.

With staggered teeth (T27) the rotor of each phase has one magnet row across the whole phase width
(9 mm), but the teeth stand only on the side walls (2 mm each). The 5 mm of magnet over the coil slot
faces no tooth. Its flux closes to the neighbouring pole in the gap and links no coil (zig-zag
leakage). The baseline field (T74) agrees: the tooth tips run at about 1.55 T, but only about 40 %
of that flux links the coil.

## Concepts

1. **Magnet slots (pockets)**, option `machine.rotor_magnet_slots`. The magnets sit in two pockets of
   the rotor, one over each side wall. Each pocket reaches `magnet_overhang_mm` over the coil slot,
   and a non-magnetic web separates the two. Both pockets have the same polarity, because the
   staggered walls already face opposite poles. If the overhang reaches half the slot, the web
   closes and the rotor is the single row again. Needs staggered teeth. Halbach or surface rotor.
2. **Halbach segments per pole**, option `machine.halbach_segments` (default 2, as before). With 4
   segments the magnetisation turns in steps of 45 degrees, which gives a stronger, more sinusoidal
   field on the stator side.
3. The "alternate" rotor of the user's list is the surface rotor (radially magnetised, alternating
   N/S on iron), `machine.rotor: "surface"`. The spoke rotor (`"spoke"`, magnets in slots between iron
   pole pieces) is the other existing magnet-in-slot rotor. Both are screened in T74.

Not done: stator-side magnets in the valleys between the gear teeth. A magnet fixed to the stator
gives a constant bias flux. The leakage it would have to block alternates with the rotor poles, so
it cannot oppose it in both half periods.

## Acceptance criteria

- [x] `halbach_segments` sets `rotor.segments_per_pole`; refused for other rotors; default unchanged.
- [x] `rotor_magnet_slots` gives two rows with the web as row gap, same polarity, and a variable
      `magnet_overhang_mm` that maps back from the parameters; one row when the web closes.
- [x] Refused without staggered teeth or with a spoke rotor.
- [x] An older specification gives the same parameters as before (no new keys).
- [x] Gmsh: pocket magnet volume scales with the axial length; 4 segments have 8 magnetisation
      directions and the same volume.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T71-1 | `halbach_segments` 2, 4, wrong rotor, 1 | 2, 4, error, error |
| T71-2 | Pockets with 1 mm overhang; overhang = half slot | rows 2, gap = slot - 2, same polarity; rows 1 |
| T71-3 | Pockets without staggered teeth; with spoke rotor | Error |
| T71-4 | `specs/user_tr48.json` | rows 1, no skew or tip keys, no new variable |
| T71-5 (slow) | Magnet volume, pockets of 2 + 1 mm against a 9 mm row | Ratio 6/9, twice the magnets |
| T71-6 (slow) | Halbach 4 against 2 segments | Twice the magnets, same volume, angles every 45 deg |

## Result

Tests: `tests/tickets/test_t71_rotor_magnet_slots.py`, all pass (T71-5 and T71-6 with `EMACHINE_SLOW=1`).
Sector meshes with pockets and with 4 segments pass `check-mesh`. Field results: T74.
