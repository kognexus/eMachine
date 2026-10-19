# B02: Parametric meshing of C, claw-pole, E and Z stators

Status: backlog
Depends on: T03

## Why

The Onshape feature builds six stator types. The parametric mesher, and therefore the
optimizer, builds only the U-core and the U-core with I-bridge.

## Scope

- Builders in the mesher for the four remaining types, matching the Onshape feature.
- Matching rotor arrangements: the C-core and Z-core need a rotor inside the core's own gap.
- Design variables, mapping and feasibility checks for each type.

## Acceptance criteria

- [ ] Each type reproduces the volume of the Onshape feature within 0.1 %.
- [ ] Each type passes the mesh checks (sliding surfaces, periodic planes) and an analysis run.

## Test cases

| ID | Test | Expected |
|---|---|---|
| B02-1 (slow) | Volume of each type against the Onshape values recorded earlier | Within 0.1 % |
| B02-2 (slow) | No-load analysis of each type | Converges; flux linkage antisymmetric over half a period |
