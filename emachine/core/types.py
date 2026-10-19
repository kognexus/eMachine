"""Plain data types shared by all packages. No physics beyond unit conversions."""

import math
from dataclasses import dataclass, field
from typing import Optional

VARIABLE_KINDS = ("real", "int")
AMBIENT = "ambient"                       # the fixed-temperature node of a thermal network
EXCITATION_MODES = ("single_phase_shifted", "all_phases")


@dataclass(frozen=True)
class Variable:
    """One optimization variable."""
    name: str
    low: float
    high: float
    kind: str = "real"
    unit: str = ""

    def __post_init__(self):
        if self.kind not in VARIABLE_KINDS:
            raise ValueError(f"Variable {self.name}: kind must be one of {VARIABLE_KINDS}, got {self.kind!r}.")
        if self.high < self.low:
            raise ValueError(f"Variable {self.name}: high {self.high} is below low {self.low}.")

    def clip(self, value):
        value = min(max(value, self.low), self.high)
        return int(round(value)) if self.kind == "int" else float(value)

    def as_dict(self):
        return {"name": self.name, "kind": self.kind, "low": self.low, "high": self.high}


@dataclass(frozen=True)
class Check:
    """
    A fast feasibility check: value against a limit. The violation is the distance beyond the
    limit divided by the scale (default: the larger of |limit| and 1), so an optimizer can rank
    infeasible designs and move towards feasibility.
    """
    name: str
    value: float
    limit: float
    sense: str                     # ">=" or "<="
    scale: Optional[float] = None

    @classmethod
    def at_least(cls, name, value, limit, scale=None):
        return cls(name, value, limit, ">=", scale)

    @classmethod
    def at_most(cls, name, value, limit, scale=None):
        return cls(name, value, limit, "<=", scale)

    @property
    def violation(self):
        scale = self.scale if self.scale else max(abs(self.limit), 1.0)
        gap = self.limit - self.value if self.sense == ">=" else self.value - self.limit
        return max(0.0, gap / scale)

    @property
    def ok(self):
        return self.violation == 0.0

    def as_dict(self):
        return {"name": self.name, "value": self.value, "limit": self.limit, "sense": self.sense,
                "violation": self.violation}


@dataclass(frozen=True)
class Winding:
    """What the electrical model needs to know about the winding of one phase."""
    phases: int
    turns: Optional[int]                  # None: chosen from the voltage limit
    coil_area_mm2: float                  # cross-section available to the conductors of one coil side
    mean_turn_length_mm: float
    fill_factor: float
    coils_per_phase: int = 1
    parallel_paths: int = 1
    conductor: str = "round_wire"         # "round_wire" or "strip" (stacked flat rings)
    coil_height_mm: float = 0.0           # coil cross-section: strip layers stack across the height
    coil_width_mm: float = 0.0            # (the width of a strip)
    wire: Optional[str] = None            # "awg": turns and wire gauge chosen together to fill the coil (T57)


@dataclass(frozen=True)
class OperatingPoint:
    """Speed and phase current; the current angle is measured from the induced voltage (0: in phase,
    as for surface PM machines; positive values advance the current, d-q control)."""
    speed_rpm: float
    current_peak_A: float
    current_angle_deg: float = 0.0

    def electrical_frequency_Hz(self, pole_pairs):
        return self.speed_rpm / 60.0 * pole_pairs


def phase_currents(current_peak_A, electrical_angle_deg, current_angle_deg=0.0, phases=3):
    """Instantaneous currents of a balanced system of `phases` phases."""
    theta = math.radians(electrical_angle_deg + current_angle_deg)
    step = 2 * math.pi / phases if phases > 2 else math.pi / 2
    return tuple(current_peak_A * math.cos(theta - k * step) for k in range(phases))


@dataclass(frozen=True)
class ExcitationPlan:
    """
    How a machine is solved over the rotor angle:
      single_phase_shifted  one phase is solved; the others are the same waveform shifted by
                            1/phases of the electrical period (phases magnetically independent, TFM)
      all_phases            all phases are excited together in one solution (RFM, AFM)
    """
    mode: str
    phases: int
    electrical_period_deg: float          # mechanical degrees of one electrical period
    positions: int = 12                   # rotor positions per half period

    def __post_init__(self):
        if self.mode not in EXCITATION_MODES:
            raise ValueError(f"Excitation mode must be one of {EXCITATION_MODES}, got {self.mode!r}.")


@dataclass(frozen=True)
class Excitation:
    """
    Rotor position and the ampere-turns of each solved coil at this position. A sinusoidal drive
    also gives its electrical angle (radians, from the aligned position) and its amplitude (peak
    ampere-turns), which analytic models use.
    """
    rotor_angle_deg: float
    ampere_turns: tuple = ()
    electrical_angle_rad: float = 0.0
    amplitude: float = 0.0


@dataclass(frozen=True)
class GeometryRequest:
    """What a geometry builder needs: its registered kind and the parameters of the geometry."""
    kind: str
    parameters: dict


@dataclass(frozen=True)
class Mesh:
    """A meshed geometry at one rotor angle: files and the description of its regions."""
    path: str
    regions: dict
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FieldSample:
    """Field solution at one rotor angle."""
    rotor_angle_deg: float
    torque_Nm: float
    flux_linkage_Wb: tuple                # per solved phase
    field_file: Optional[str] = None      # saved flux density of cores and rotor parts
    extras: dict = field(default_factory=dict)


@dataclass
class Sweep:
    samples: list
    plan: ExcitationPlan

    def angles(self):
        return [s.rotor_angle_deg for s in self.samples]

    def torque(self):
        return [s.torque_Nm for s in self.samples]

    def flux(self, phase=0):
        return [s.flux_linkage_Wb[phase] for s in self.samples]


@dataclass(frozen=True)
class ThermalNetwork:
    """Conductances in W/K between named nodes; the node "ambient" is fixed at the ambient temperature."""
    conductances: tuple                   # ((node a, node b, W/K), ...)
    ambient_C: float


@dataclass(frozen=True)
class Losses:
    copper_W: float = 0.0
    stator_core_W: float = 0.0
    rotor_W: float = 0.0
    mechanical_W: float = 0.0

    @property
    def total_W(self):
        return self.copper_W + self.stator_core_W + self.rotor_W + self.mechanical_W


@dataclass(frozen=True)
class Temperatures:
    winding_C: float
    core_C: float
    rotor_C: float


@dataclass
class Evaluation:
    """Objectives (named values), constraint violations (0 = met) and anything else worth keeping."""
    objectives: dict
    constraints: dict
    details: dict = field(default_factory=dict)

    @property
    def violation(self):
        return float(sum(max(0.0, v) for v in self.constraints.values()))

    @property
    def feasible(self):
        return self.violation <= 0.0


@dataclass(frozen=True)
class Objective:
    name: str
    sense: str = "min"                    # "min" or "max"


@dataclass(frozen=True)
class Problem:
    """What an optimizer sees: variables and objectives. Constraints come back as a violation."""
    variables: tuple
    objectives: tuple

    def senses(self):
        return [o.sense for o in self.objectives]
