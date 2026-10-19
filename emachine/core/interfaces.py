"""
Interfaces between the packages (docs/architecture.md). Each is the smallest set of methods its
users need. Implementations register in emachine.core.registry.
"""

from abc import ABC, abstractmethod


class Machine(ABC):
    """A flux path and torque principle, e.g. ("tfm", "pmsm") or ("rfm", "synrm"), with the rotor
    layouts it offers (docs/naming.md)."""

    flux_path = ""       # "tfm", "rfm", "afm", "rafm"
    principle = ""       # "pmsm", "synrm", "srm", "vernier"
    rotors = ()          # rotor layouts (spec key machine.rotor); the first is the default
    winding_spans = ("concentrated", "distributed")     # allowed winding.span; the first is the default
    solvable = True      # False when no rotor layout has a geometry yet

    @classmethod
    def key(cls):
        return f"{cls.flux_path}/{cls.principle}"

    @classmethod
    def rotor_status(cls, rotor):
        """(solvable, ticket) of one rotor layout: whether it has a geometry, and the ticket that
        builds it (or built it)."""
        return cls.solvable, getattr(cls, "ticket", "")

    @abstractmethod
    def options(self):
        """Defaults of this machine's options in the spec section `machine`."""

    def validate(self, spec):
        """Raises an error (emachine.spec.SpecError) when this machine's options are invalid."""

    @abstractmethod
    def variables(self, spec):
        """Optimization variables (list of core.types.Variable)."""

    @abstractmethod
    def derive(self, spec, values):
        """All dimensions of one design (dict)."""

    @abstractmethod
    def checks(self, spec, values):
        """Fast feasibility checks before any meshing (list of core.types.Check)."""

    @abstractmethod
    def geometry(self, spec, values, fidelity=None):
        """Parameters of the geometry (core.types.GeometryRequest)."""

    @abstractmethod
    def winding(self, spec, values):
        """Winding of one phase (core.types.Winding)."""

    @abstractmethod
    def thermal_network(self, spec, values):
        """Thermal network (core.types.ThermalNetwork)."""

    @abstractmethod
    def excitation(self, spec, values):
        """How the phases are solved (core.types.ExcitationPlan)."""

    def winding_description(self, spec, values):
        """Label (FSCW, FSDW, ISDW, ring), q, layers and winding factors of a design (dict), or None."""
        return None


class GeometryBuilder(ABC):
    """Builds and meshes the geometry of one kind ("tfm.sector3d", "rfm.section2d") at a rotor angle."""

    @abstractmethod
    def build(self, request, rotor_angle_deg, workdir):
        """Returns a core.types.Mesh."""


class FieldSolver(ABC):
    """Solves the field of a mesh for one excitation."""

    @abstractmethod
    def solve(self, mesh, excitation, workdir):
        """Returns a core.types.FieldSample."""


class LossModel(ABC):
    @abstractmethod
    def coefficients(self, materials, field_files):
        """Loss coefficients of one sweep (independent of speed)."""

    @abstractmethod
    def at(self, coefficients, frequency_Hz, materials):
        """(stator core loss, rotor loss) in W at an electrical frequency."""


class ThermalModel(ABC):
    @abstractmethod
    def temperatures(self, network, heat):
        """Node temperatures for heat inputs {node: W}."""


class Optimizer(ABC):
    """Searches the variables of a problem. `evaluate(list of vectors)` returns, per vector,
    (objective values, violation), objectives to be minimised."""

    @abstractmethod
    def run(self, problem, evaluate, budget, state_file=None, **options):
        """Returns the final state: population with x, f and violation."""
