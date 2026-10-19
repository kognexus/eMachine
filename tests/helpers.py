"""Shared test helpers: paths, the slow-test marker, and the electrical and thermal model of a TFM
design composed as the pipeline composes it (emachine/pipeline/evaluate.py)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: The Onshape FeatureScript files (moved from the project root in T34)
FEATURESCRIPT = os.path.join(ROOT, "emachine", "machines", "tfm", "cad", "featurescript")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: Decorator for tests that need Gmsh or Elmer and take seconds to minutes.
SLOW = os.environ.get("EMACHINE_SLOW") == "1" or os.environ.get("TFM_SLOW") == "1"
slow = unittest.skipUnless(SLOW, "slow test, set EMACHINE_SLOW=1 (or TFM_SLOW=1) to run")


def machine_of(spec):
    from emachine.pipeline.design_space import machine_of
    return machine_of(spec)


def coil_winding(spec, coil_area_mm2, turn_length_mm, **changes):
    """The Winding of one phase coil of the given copper room, with conductor, fill and turns of the spec."""
    from emachine.core.types import Winding
    from emachine.spec import copper_fill
    w = spec["winding"]
    return Winding(**{"phases": spec["machine"]["phases"], "turns": w["turns"], "coil_area_mm2": coil_area_mm2,
                      "mean_turn_length_mm": turn_length_mm, "fill_factor": copper_fill(spec),
                      "conductor": w["conductor"], **changes})


def turns_of(spec, winding, flux_per_turn_half, electrical_frequency_Hz, ampere_turns_peak, temp_C):
    """The turns the pipeline chooses for a winding (emachine.physics.winding.turns_for)."""
    from emachine.physics.winding import turns_for
    return turns_for(winding, spec["materials"]["copper"], spec["limits"], flux_per_turn_half,
                     electrical_frequency_Hz, ampere_turns_peak, temp_C, spec["winding"]["strip_min_thickness_mm"])


def phase_resistance(spec, winding, turns, temp_C):
    from emachine.physics import winding as w
    return w.resistance(w.winding_resistance(spec["materials"]["copper"], winding, temp_C), turns)


def copper_loss(spec, winding, ampere_turns_rms, temp_C):
    """Copper loss of one phase in W; independent of the number of turns."""
    from emachine.physics import winding as w
    return w.copper_loss(w.winding_resistance(spec["materials"]["copper"], winding, temp_C), ampere_turns_rms)


def heat_balance(spec, values, copper_loss_W, iron_loss_W, rotor_loss_W=0.0):
    """(temperatures, heat flows) of the machine's thermal network for given losses of one phase."""
    from emachine.physics import thermal
    return thermal.solve(machine_of(spec).thermal_network(spec, values),
                         {"winding": copper_loss_W, "core": iron_loss_W, "rotor": rotor_loss_W})


def coupled(spec, values, iron_loss_W, rotor_loss_W=0.0, **iteration):
    """Temperatures with the copper loss at the winding temperature, as the pipeline evaluates them."""
    from emachine.machines.tfm import design
    from emachine.pipeline.evaluate import temperatures
    return temperatures(spec, machine_of(spec), values, design.derived(spec, values), iron_loss_W, rotor_loss_W,
                        **iteration)
