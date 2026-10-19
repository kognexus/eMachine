# Architecture of `emachine`

`emachine` designs, analyses and optimizes electrical machines. Each machine is three choices
(`docs/naming.md`, T43):

- a **flux path**: `tfm` (transverse flux), `rfm` (radial flux), `afm` (axial flux) or `rafm`
  (radial-axial flux);
- a **torque principle**: `pmsm`, `synrm`, `srm` or `vernier`;
- a **rotor layout**: `surface`, `inset`, `interior`, `spoke`, `halbach`, `axial_ring`,
  `flux_barrier`, `flux_barrier_pm`, `salient`, as each machine offers them.

Agreed with the user on 2026-10-16 (tickets T32 to T41, naming T43 to T46). A machine class is
registered as `<flux_path>/<principle>`, lives in `machines/<flux_path>/<principle>.py`, and its
rotor layouts in `machines/<flux_path>/rotors/<layout>.py` (`RotorLayout`: variables, checks,
geometry).

## Packages

```
emachine/
  core/            interfaces and data types; no physics, no file access
  spec/            specification files: common sections, plus one section per machine
  machines/        machine architectures (plugins), one subpackage per flux path
    tfm/           transverse flux: stators/, rotors/, geometry, cad/ (Onshape)
    rfm/           radial flux
    afm/           axial flux
  physics/         machine-independent models: winding and electrical, losses, thermal network,
                   multiphase torque
  solvers/         field solvers (plugins): elmer/ (3D sector, 2D cross-section), analytic/
  pipeline/        orchestration: stages, rotor-angle sweeps, load levels, run folders, cache
  optimization/    optimizers (plugins): nsga2, random search; problem definition; seeding
  analysis/        efficiency map, field export, validation against published machines
  io/              VTK, SVG charts, ParaView files and views, reports
  cad/             the Onshape feature "eMachine" of every machine (FeatureScript, build, sheet)
  cli.py           emachine <command>
```

Dependencies point one way only (checked by `tests/unit/core/test_import_rule.py`):

| Package | May import |
|---|---|
| core | nothing |
| spec, physics, io, optimization | core |
| machines | core, physics, spec, io |
| solvers | core, physics, io |
| pipeline | core, physics, spec, machines, solvers, io |
| analysis | the above and pipeline |
| cad | core, spec, machines, pipeline |
| cli | everything |

Machines, solvers and optimizers never import each other: they meet in `pipeline` through the
interfaces of `core`.

## Interfaces (`emachine/core/interfaces.py`)

All interfaces are abstract base classes with the smallest set of methods their users need
(interface segregation). Implementations register themselves by name, so the pipeline never names
a concrete class (open for extension, closed for modification).

```python
class Machine(ABC):
    """One flux path and principle, e.g. ("tfm", "pmsm") or ("rfm", "synrm"), with its rotor layouts."""
    flux_path: str                   # "tfm", "rfm", "afm", "rafm"
    principle: str                   # "pmsm", "synrm", "srm", "vernier"
    rotors: tuple[str]               # rotor layouts, the default first
    def rotor_status(cls, rotor) -> (solvable, ticket): ...
    def options(self) -> dict: ...                         # defaults of its spec section
    def variables(self, spec) -> list[Variable]: ...       # optimization variables
    def derive(self, spec, values) -> Derived: ...         # all dimensions of one design
    def checks(self, spec, derived) -> list[Check]: ...    # fast feasibility, before meshing
    def geometry(self, spec, derived, fidelity) -> GeometryRequest: ...
    def winding(self, spec, derived) -> Winding: ...       # phases, turns, coil areas, lengths
    def thermal_network(self, spec, derived) -> ThermalNetwork: ...
    def excitation(self, spec, derived) -> ExcitationPlan: ...
        # how phases are solved: "one phase, others shifted" (TFM) or "all phases" (RFM, AFM)

class GeometryBuilder(ABC):          # one per geometry kind ("tfm.sector3d", "rfm.section2d")
    def build(self, request: GeometryRequest, rotor_angle_deg, workdir) -> Mesh: ...

class FieldSolver(ABC):              # "elmer3d", "elmer2d", "analytic"
    def solve(self, mesh: Mesh, excitation: Excitation, workdir) -> FieldSample: ...

class LossModel(ABC):
    def coefficients(self, materials, samples: Sweep) -> LossCoefficients: ...
    def at(self, coefficients, frequency_Hz, materials) -> Losses: ...

class ThermalModel(ABC):
    def temperatures(self, network, heat: Losses) -> Temperatures: ...

class Optimizer(ABC):                # "nsga2", "random"
    def run(self, problem: Problem, evaluate: Callable[[list[float]], Evaluation],
            budget: Budget, state=None) -> OptimizationResult: ...
```

Data types (`emachine/core/types.py`) are plain dataclasses: `Variable`, `Check`, `Derived`,
`Winding`, `OperatingPoint(speed_rpm, current_peak_A, current_angle_deg)`, `Excitation`,
`FieldSample(rotor_angle_deg, torque_Nm, flux_linkage_Wb per phase, field_file)`, `Sweep`,
`Losses`, `Temperatures`, `Evaluation(objectives, constraints, details)`, `Problem`.

The current angle generalizes today's "current in phase with the induced voltage" (angle 0) to
d-q control (IPM, SynRM: maximum torque per ampere).

## Registry (`emachine/core/registry.py`)

```python
@register("machine", "tfm/pmsm")
class TransverseFluxPMSM(Machine): ...

machine = create("machine", spec["machine"]["flux_path"] + "/" + spec["machine"]["principle"])
```

Kinds: `machine`, `geometry`, `solver`, `optimizer`. `emachine list` prints what is registered.

## Specification

Common sections stay as today (`limits`, `materials`, `winding`, `thermal`, `operating_point`,
`fidelity`, `objectives`, `optimizer` with a new `algorithm` key). `machine` names the flux path,
the principle and the rotor layout, and holds the options that machine declares. Old TFM
specification files (no `flux_path`) load as `tfm/pmsm` unchanged; old key names (`family`,
`topology`, `configuration`, `stator_type`, `rotor_type`, `sides`) are translated by
`emachine/spec/names.py`, which also writes a spec back in the old names for the cache keys, so
results cached before the standard are still found.

## Pipeline

```
design values -> Machine.derive -> Machine.checks -> GeometryBuilder.build (per rotor angle)
  -> FieldSolver.solve (per angle and excitation) -> Sweep -> torque, flux, voltage
  -> LossModel -> ThermalModel -> Evaluation (objectives, constraints)
```

Run folders, field caches and load levels are kept by the pipeline, keyed by the design and the
model version, as today.

## Tests

```
tests/unit/<package>/...        fast, one module each; written before the code (TDD)
tests/tickets/...               acceptance tests of each ticket; the slow ones need EMACHINE_SLOW=1
tests/regression/...            recorded numerical results (baseline/); every change must reproduce
                                them, or re-record them on purpose (`pixi run rebaseline`)
tests/helpers.py                paths, the slow-test marker, and the winding and thermal model of a
                                design composed as the pipeline composes it
```

## Compatibility

- Every command is `emachine <command>` (`python -m emachine <command>` works as well). The old
  top-level scripts (`tfm_optimize.py`, ...) and the `tfm` package were removed in the cleanup for
  publication; every test imports `emachine` directly.
- Specification files with old key names still load (`emachine/spec/names.py`), and old run folders
  (`runs/`) stay readable by `map`, `export` and `validate`.
