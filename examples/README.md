# Examples

Ready-to-run inputs for `emachine`. Each specification is a complete problem: copy one, change the
envelope, limits or objectives, and run it. The inputs are explained in
[docs/usage.md](../docs/usage.md#3-inputs-the-specification-file).

Run the commands from the repository root inside the environment (`pixi shell`, or prefix each with
`pixi run`). Results go to `runs/`, which git ignores. Add `--dry-run` to any `optimize` command to
check the workflow in seconds without Elmer.

## Optimize an architecture

| Specification | Machine | Run time |
|---|---|---|
| `tfm_three_phase.json` | transverse flux PM outrunner, 80 mm, 3 phases in 29 mm, Halbach rotor, U-core with I-bridge, strip coil, ripple ≤ 20 % | 1–2 h |
| `tfm_single_phase.json` | the same machine with one phase and no ripple limit | 1–2 h |
| `rfm_spm_12s10p.json` | radial flux surface PM inrunner, 12 slots 10 poles, 100 mm × 40 mm, only the current density free | minutes |

```bash
emachine optimize --spec examples/tfm_three_phase.json --run runs/tfm3
emachine optimize --spec examples/rfm_spm_12s10p.json  --run runs/rfm
```

Then read `runs/<name>/report.md`, and post-process a pick:

```bash
emachine map     --run runs/tfm3                  # efficiency map of the best compromise
emachine export  --run runs/tfm3 --sectors 3      # ParaView files
emachine onshape --run runs/tfm3                  # values for the Onshape feature
```

## Compare stator types

`three_phase_u.json`, `three_phase_ui.json` and `three_phase_cp.json` are the same three-phase
outrunner with a U-core, a U-core with I-bridge and a claw-pole stator. Run each into its own folder
under one parent, then compare:

```bash
for s in u ui cp; do emachine optimize --spec examples/three_phase_$s.json --run runs/types/$s; done
emachine compare --runs runs/types --verify
```

The `_24` variants solve 24 rotor positions on a finer mesh: slower, with steadier ripple values.

## Analyse one existing machine

A specification whose variables are all fixed describes a single machine; the matching
`*_design.json` holds its design values.

| Specification + design | Machine |
|---|---|
| `user_tr48.json` + `user_tr48_design.json` | 48-pole toothed-ring TFM outrunner, 80 mm |
| `rfm_spm_12s10p.json` + `rfm_spm_12s10p_design.json` | the 12-slot 10-pole radial flux machine |
| `rafm_zhang2023.json` + `rafm_zhang2023_design.json` | radial-axial hybrid PMSM of Zhang, Liu and Wu (2023) |

```bash
emachine map    --spec examples/user_tr48.json --design examples/user_tr48_design.json --out runs/tr48/map
emachine export --spec examples/user_tr48.json --design examples/user_tr48_design.json \
    --out runs/tr48/paraview --map runs/tr48/map
emachine onshape --spec examples/rfm_spm_12s10p.json --design examples/rfm_spm_12s10p_design.json
```

## Low-level: mesh and solve a parameter file

`params/motor.json` and `params/motor_matched.json` give the TFM geometry directly, in the fields of
the Onshape features "TFM stator" and "TFM rotor" (no specification, no optimizer).

```bash
emachine mesh  --params examples/params/motor_matched.json --out runs/sector.msh --preview runs/sector.svg
emachine solve --params examples/params/motor_matched.json --run runs/solve --jobs 6
```

## Validation against published prototypes

Each folder of `validation/` describes a published machine and its measured results in `case.json`;
`emachine validate` solves no load, inductance and load and writes `report.md` (published against
computed values), `results.json` and `waveforms.csv` next to it. The recorded reports are included.

| Case | Machine |
|---|---|
| `validation/guo2006/` | SMC transverse flux motor, Guo et al. 2006 |
| `validation/guo_clawpole/` | SMC claw-pole motor of the same group |

```bash
emachine validate examples/validation/guo2006/case.json --jobs 6
emachine validate examples/validation/guo2006/case.json --variant tooth_6mm   # one sensitivity variant
```

The field solutions (`raw/`, ~50 MB per case) are not tracked; `--losses-only` recomputes the losses
from them once a full run has written them. Results and conclusions: ticket
[T30](https://github.com/kognexus/eMachine/issues/30).

## Scripting: the mesh fidelity study

[`mesh_fidelity/fidelity_study.py`](mesh_fidelity/fidelity_study.py) uses the Python API instead of
the command line. It solves the reference design at five air-gap cell sizes and writes
`fidelity_results.csv`, the evidence behind the default `fast` mesh level (cell factor 1.5): mean
torque within 1 % of the finest mesh at a third of its solve time. Test T08 checks the recorded table.

```bash
python examples/mesh_fidelity/fidelity_study.py     # about 5 minutes
```
