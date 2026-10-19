"""
Steady-state lumped thermal network: temperatures of named nodes for heat inputs, with the node
"ambient" fixed at the ambient temperature. The network of a machine comes from
Machine.thermal_network (emachine.core.types.ThermalNetwork).
"""

import math

import numpy as np

from emachine.core.interfaces import ThermalModel
from emachine.core.types import AMBIENT
RUNAWAY_C = 1000.0


def nodes_of(network, heat=None):
    names = []
    for na, nb, _ in network.conductances:
        for name in (na, nb):
            if name != AMBIENT and name not in names:
                names.append(name)
    for name in (heat or {}):
        if name not in names:
            names.append(name)
    return names


def solve(network, heat_W):
    """
    Temperatures of the network for heat inputs {node: W} (missing nodes: no heat).
    Returns ({node: temperature in C}, {node: heat flowing from it to ambient in W}).
    """
    nodes = nodes_of(network, heat_W)
    index = {name: i for i, name in enumerate(nodes)}
    a = np.zeros((len(nodes), len(nodes)))
    q = np.array([float(heat_W.get(name, 0.0)) for name in nodes])
    for na, nb, g in network.conductances:
        if g < 0:
            raise ValueError(f"Negative conductance between {na} and {nb}.")
        for this, other in ((na, nb), (nb, na)):
            if this == AMBIENT:
                continue
            i = index[this]
            a[i, i] += g
            if other != AMBIENT:
                a[i, index[other]] -= g
    rise = np.linalg.solve(a, q)
    ambient = network.ambient_C
    temps = {name: ambient + float(rise[i]) for name, i in index.items()}
    to_ambient = {name: 0.0 for name in nodes}
    for na, nb, g in network.conductances:
        if nb == AMBIENT:
            to_ambient[na] += g * (temps[na] - ambient)
        elif na == AMBIENT:
            to_ambient[nb] += g * (temps[nb] - ambient)
    return temps, to_ambient


def response(network, sources):
    """Temperature rise per watt: {node: (rise per W at each source node, in the order of `sources`)}.
    The network is linear, so any operating point follows from these numbers."""
    rises = []
    for source in sources:
        temps, _ = solve(network, {s: (1.0 if s == source else 0.0) for s in sources})
        rises.append({node: t - network.ambient_C for node, t in temps.items()})
    return {node: tuple(r[node] for r in rises) for node in rises[0]}


def coupled(network, copper_loss_at, heat_W, winding_node="winding", max_iterations=50, tolerance_K=0.01):
    """
    Temperatures with the copper loss evaluated at the winding temperature: `copper_loss_at(T)`
    gives the copper loss in W at winding temperature T; `heat_W` the other heat inputs. A thermal
    runaway is reported as not converged.
    """
    winding = network.ambient_C
    result = None
    for iteration in range(1, max_iterations + 1):
        copper = copper_loss_at(winding)
        temps, to_ambient = solve(network, dict(heat_W, **{winding_node: copper}))
        change = abs(temps[winding_node] - winding)
        winding = temps[winding_node]
        result = {"temperatures": temps, "winding_C": winding, "copper_loss_W": copper, "iterations": iteration,
                  "converged": change < tolerance_K, "heat_to_ambient_W": sum(to_ambient.values())}
        if result["converged"]:
            break
        if not math.isfinite(winding) or winding > RUNAWAY_C:
            result["converged"] = False
            break
    return result


class LumpedNetwork(ThermalModel):
    """ThermalModel of a lumped network."""

    def temperatures(self, network, heat):
        return solve(network, heat)[0]
