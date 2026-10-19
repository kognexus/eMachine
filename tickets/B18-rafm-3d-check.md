# B18: 3D field check of the raxial machine

Status: backlog
Depends on: T55

## Why

T55 solves the raxial machine as a radial section plus axial slices, as the paper does for its
design. Ends of the radial magnets, the corners where coil sides meet, and the coupling through the
yoke are 3D effects.

## Scope

A 3D sector (gcd(slots, poles) = 4: a quarter, anti-periodic) meshed per rotor position (no sliding
surface: the rotor faces the stator on three sides), Elmer Whitney A-V; toroidal coils as an
equivalent magnetisation M_theta = g(r, z) / r within each coil's angular range. Compare no-load
EMF and rated torque with T55 at a few positions.
