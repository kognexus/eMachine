# T68: Spoke rotor on a non-magnetic hub, fewer poles, magnetisation shown

Status: done
Depends on: T59, T63

## Why

The user (2026-10-18): the spoke design does not look like a spoke design. The magnets do alternate (tangential,
checked), but the optimized design has 38 poles with 3.4 mm magnets and 1 to 2 mm iron poles, and the iron poles
are joined by a continuous iron ring below the magnets, which short-circuits magnet flux. A spoke rotor sits on a
non-magnetic hub.

## Scope

- Rotor layout `spoke`: the ring below the magnets non-magnetic (hub of stainless steel or aluminium; iron poles
  held by dovetails); the magnets reach down to the hub.
- Pole counts 14 to 24 (iron poles at least as wide as the magnets at the gap is not forced, but the range allows it).
- Pictures: magnets coloured by the direction of magnetisation (sketch) and arrows in ParaView.
- Optimization and verification again.

## Acceptance criteria

- [x] Sketch and ParaView picture show alternating tangential magnets with iron poles between them, on a hub
      (materials view: magnets coloured by the direction of magnetisation, code 7 for the other direction).
- [x] New run verified; result compared with the first spoke run.

## Result

2026-10-18. Layout `spoke` with `hub_radius`: the ring below the magnets is non-magnetic; poles 14 to 24; spoke depth
a share of the room above a 2 mm hub ring. 16 x 5 designs. Verified: 3.25 Nm at 10.5 A and 1000 rpm, 10.1 Nm at
42 A, ripple 2.4 %, efficiency 88.4 % (first run: 3.48 Nm, 13.0 Nm, 78.5 %, failing the efficiency limit; its iron
ring short-circuited part of the magnet flux and its 38 poles left 1 to 2 mm iron poles). The 52 mm bore limits
the spokes to about 4 mm.
