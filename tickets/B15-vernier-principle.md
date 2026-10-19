# B15: PM vernier machine (principle `vernier`)

Status: backlog
Depends on: T43, T44, T45, T46

## Why

The naming standard (`docs/naming.md`, 2026-10-16) adds the torque principle `vernier`: flux
modulation, where a winding of few poles drives a rotor of many magnet poles through the stator
teeth (magnetic gearing). It is a row of the machine matrix (T45) with no machine yet. The radial
flux version can reuse the 2D section of `rfm/pmsm`.

## Scope

1. `rfm/vernier`: rotor layouts `surface`, `spoke`, `halbach`; variables as `rfm/pmsm` plus the
   modulator (stator teeth or split teeth). Pole relation checked: Q_modulator = p_rotor + p_winding,
   gear ratio p_rotor / p_winding reported.
2. Geometry: the section builder of `rfm.section2d` with the winding pole pairs for the coils and
   the rotor pole pairs for the magnets; solver unchanged (all phases in one 2D solution).
3. Electrical model: the low power factor of vernier machines in the voltage limit and the map.
4. Later: `afm/vernier`, `tfm/vernier`.

## Acceptance criteria

- [ ] `rfm/vernier` solvable; the induced voltage has the frequency of the rotor poles times the
      speed and the winding pole number in space.
- [ ] Torque against a published PM vernier machine within 10 %.
- [ ] Power factor in the map and reports.
