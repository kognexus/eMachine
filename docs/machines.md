# Machine matrix

Flux path x torque principle (names: [naming.md](naming.md)). Written by `emachine list --markdown`; a test checks that it agrees with the code.

| | PMSM | SynRM | SRM | Vernier |
|---|---|---|---|---|
| **TFM** | solvable | not meaningful | specified (B12) | planned (B15) |
| **RFM** | solvable | specified (B07, B08) | specified (B09) | planned (B15) |
| **AFM** | specified (B10) | planned (B16) | specified (B11) | planned (B15) |
| **RAFM** | solvable | planned (B14) | planned (B14) | planned (B14) |

- **solvable**: at least one rotor layout has a geometry and is analysed with the field solver.
- **specified**: the machine is registered (variables, checks, winding, thermal estimates); the ticket builds its geometry.
- **planned**: nothing registered yet; the backlog ticket.
- **not meaningful**: the combination does not make a machine (reason below).

## Rotor layouts of the registered machines

| Machine | Rotor layout | Status |
|---|---|---|
| `tfm/pmsm` | `halbach` | solvable (T34) |
| `tfm/pmsm` | `surface` | solvable (T34) |
| `tfm/pmsm` | `spoke` | solvable (T34) |
| `tfm/pmsm` | `axial_ring` | solvable (T34) |
| `tfm/srm` | `salient` | specified (B12) |
| `rfm/pmsm` | `surface` | solvable (T41) |
| `rfm/pmsm` | `interior` | specified (B06) |
| `rfm/synrm` | `flux_barrier` | specified (B07) |
| `rfm/synrm` | `flux_barrier_pm` | specified (B08) |
| `rfm/srm` | `salient` | specified (B09) |
| `afm/pmsm` | `surface` | specified (B10) |
| `afm/srm` | `salient` | specified (B11) |
| `rafm/pmsm` | `surface` | solvable (T55) |

## Not meaningful

- `tfm/synrm`: each TFM phase is a ring coil with a pulsating field of its own; there is no rotating field for a d-q anisotropic rotor. The reluctance TFM is tfm/srm.
