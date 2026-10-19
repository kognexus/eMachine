"""
NSGA-II: multi-objective optimization with real and integer variables and constraints.

All objectives are minimised. Each design has one number for its total constraint violation
(0 = feasible). Designs are compared by constrained domination: a feasible design beats an
infeasible one, and of two infeasible designs the one with the smaller violation wins.

The optimizer state is plain JSON, saved after every generation, so a run can be resumed and
gives the same result as an uninterrupted run with the same seed.
"""

import json
import math
import os

import numpy as np

from emachine.core.interfaces import Optimizer
from emachine.core.registry import register

from .pareto import crowding_distance, dominates, key_of, non_dominated_sort, pareto_front  # noqa: F401

ETA_CROSSOVER = 15.0
ETA_MUTATION = 20.0
CROSSOVER_PROBABILITY = 0.9






def _repair(x, variables):
    out = []
    for value, var in zip(x, variables):
        if var["kind"] == "int":
            value = int(round(value))
        value = min(max(value, var["low"]), var["high"])
        out.append(int(value) if var["kind"] == "int" else float(value))
    return out


def random_design(variables, rng):
    return [int(rng.integers(v["low"], v["high"] + 1)) if v["kind"] == "int"
            else float(rng.uniform(v["low"], v["high"])) for v in variables]


def _bounds(var):
    # Integers are treated as reals on a range widened by half a step, then rounded.
    return (var["low"] - 0.499, var["high"] + 0.499) if var["kind"] == "int" else (var["low"], var["high"])


def _crossover(a, b, variables, rng):
    """Simulated binary crossover."""
    c1, c2 = list(a), list(b)
    if rng.random() > CROSSOVER_PROBABILITY:
        return c1, c2
    for i, var in enumerate(variables):
        low, high = _bounds(var)
        if high <= low or rng.random() > 0.5 or abs(a[i] - b[i]) < 1e-14:
            continue
        x1, x2 = min(a[i], b[i]), max(a[i], b[i])
        u = rng.random()
        beta = 1.0 + 2.0 * (x1 - low) / (x2 - x1)
        alpha = 2.0 - beta ** -(ETA_CROSSOVER + 1)
        bq = (u * alpha) ** (1 / (ETA_CROSSOVER + 1)) if u <= 1 / alpha else (1 / (2 - u * alpha)) ** (1 / (ETA_CROSSOVER + 1))
        y1 = 0.5 * (x1 + x2 - bq * (x2 - x1))
        beta = 1.0 + 2.0 * (high - x2) / (x2 - x1)
        alpha = 2.0 - beta ** -(ETA_CROSSOVER + 1)
        bq = (u * alpha) ** (1 / (ETA_CROSSOVER + 1)) if u <= 1 / alpha else (1 / (2 - u * alpha)) ** (1 / (ETA_CROSSOVER + 1))
        y2 = 0.5 * (x1 + x2 + bq * (x2 - x1))
        if rng.random() < 0.5:
            y1, y2 = y2, y1
        c1[i], c2[i] = y1, y2
    return c1, c2


def _mutate(x, variables, rng):
    """Polynomial mutation, on average one variable per design."""
    free = [i for i, v in enumerate(variables) if v["high"] > v["low"]]
    if not free:
        return list(x)
    rate = 1.0 / len(free)
    out = list(x)
    for i in free:
        if rng.random() > rate:
            continue
        low, high = _bounds(variables[i])
        span = high - low
        d1, d2 = (out[i] - low) / span, (high - out[i]) / span
        u = rng.random()
        power = 1 / (ETA_MUTATION + 1)
        if u < 0.5:
            dq = (2 * u + (1 - 2 * u) * (1 - d1) ** (ETA_MUTATION + 1)) ** power - 1
        else:
            dq = 1 - (2 * (1 - u) + 2 * (u - 0.5) * (1 - d2) ** (ETA_MUTATION + 1)) ** power
        out[i] = out[i] + dq * span
    return out


def _rank(population):
    """Sets 'rank' and 'crowding' on every individual."""
    for rank, front in enumerate(non_dominated_sort(population)):
        for i, distance in zip(front, crowding_distance(population, front)):
            population[i]["rank"] = rank
            population[i]["crowding"] = distance


def _better(a, b):
    if a["rank"] != b["rank"]:
        return a["rank"] < b["rank"]
    return a["crowding"] > b["crowding"]


def _survive(combined, size):
    survivors = []
    for front in non_dominated_sort(combined):
        if len(survivors) + len(front) <= size:
            survivors.extend(front)
            continue
        distance = crowding_distance(combined, front)
        if any(combined[i]["violation"] > 0 for i in front):
            order = sorted(range(len(front)), key=lambda k: combined[front[k]]["violation"])
        else:
            order = sorted(range(len(front)), key=lambda k: -distance[k])
        survivors.extend(front[k] for k in order[:size - len(survivors)])
        break
    return [combined[i] for i in survivors]


def _evaluate(designs, state, evaluate_batch):
    """Individuals for `designs`, evaluating only those not yet in the archive."""
    archive = state["archive"]
    new, seen = [], set()
    for x in designs:
        k = key_of(x)
        if k not in archive and k not in seen:
            seen.add(k)
            new.append(x)
    if new:
        for x, (f, violation) in zip(new, evaluate_batch(new)):
            archive[key_of(x)] = {"x": list(x), "f": [float(v) for v in f], "violation": float(violation)}
        state["evaluations"] += len(new)
    out = [dict(archive[key_of(x)]) for x in designs]
    # An evaluator may hand back further designs it got for free (other current densities of a
    # geometry it had to solve anyway). They compete for survival like the designs asked for.
    take_extra = getattr(evaluate_batch, "take_extra", None)
    if take_extra:
        for x, f, violation in take_extra():
            k = key_of(x)
            if k not in archive:
                archive[k] = {"x": list(x), "f": [float(v) for v in f], "violation": float(violation)}
                state["free_designs"] = state.get("free_designs", 0) + 1
                out.append(dict(archive[k]))
    return out


def _save(state, rng, state_file):
    if not state_file:
        return
    state["rng"] = rng.bit_generator.state
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, state_file)



def optimize(variables, evaluate_batch, population=16, generations=10, seed=1, state_file=None,
             initial=None, on_generation=None, inject=None):
    """
    Runs NSGA-II and returns the state: generation, population, archive (every evaluated design),
    evaluations and history.

    variables       list of {name, kind ('real' or 'int'), low, high}
    evaluate_batch  function(list of designs) -> list of (objectives, total violation)
    initial         optional list of starting designs, used for a new run. Fewer than the population
                    are padded with random designs. More than the population are all evaluated and
                    the population is chosen from them by the survival rule.
    inject          optional list of designs added to the population of a resumed run
    state_file      JSON file for saving and resuming
    on_generation   optional function(state) called after every generation
    """
    rng = np.random.default_rng(seed)
    state = None
    if state_file and os.path.isfile(state_file):
        with open(state_file) as f:
            state = json.load(f)
        rng.bit_generator.state = state["rng"]
    if state is None:
        state = {"generation": 0, "population": [], "archive": {}, "evaluations": 0, "history": []}
        designs = [_repair(x, variables) for x in (initial or [])]
        while len(designs) < population:
            designs.append(random_design(variables, rng))
        state["population"] = _evaluate(designs, state, evaluate_batch)
        if len(state["population"]) > population:
            state["population"] = _survive(state["population"], population)
        _record(state)
        _save(state, rng, state_file)
        if on_generation:
            on_generation(state)

    elif inject:
        added = _evaluate([_repair(x, variables) for x in inject], state, evaluate_batch)
        known = {key_of(p["x"]) for p in state["population"]}
        added = [p for p in added if key_of(p["x"]) not in known]
        state["population"] = _survive(state["population"] + added, len(state["population"]))
        state["history"][-1].update({"feasible": sum(p["violation"] == 0 for p in state["population"]),
                                     "evaluations": state["evaluations"],
                                     "front_size": len(pareto_front(state["population"]))})
        _save(state, rng, state_file)

    while state["generation"] < generations:
        parents = state["population"]
        _rank(parents)
        children = []
        while len(children) < population:
            picks = []
            for _ in range(2):
                a, b = (parents[int(i)] for i in rng.integers(0, len(parents), 2))
                picks.append(a if _better(a, b) else b)
            c1, c2 = _crossover(picks[0]["x"], picks[1]["x"], variables, rng)
            children.append(_repair(_mutate(c1, variables, rng), variables))
            children.append(_repair(_mutate(c2, variables, rng), variables))
        offspring = _evaluate(children[:population], state, evaluate_batch)
        state["population"] = _survive(parents + offspring, population)
        state["generation"] += 1
        _record(state)
        _save(state, rng, state_file)
        if on_generation:
            on_generation(state)
    _rank(state["population"])
    return state


def _record(state):
    population = state["population"]
    state["history"].append({
        "generation": state["generation"],
        "evaluations": state["evaluations"],
        "feasible": sum(p["violation"] == 0 for p in population),
        "best_violation": min(p["violation"] for p in population),
        "front_size": len(pareto_front(population)),
    })


@register("optimizer", "nsga2")
class NSGA2(Optimizer):
    """NSGA-II behind the Optimizer interface. budget: {"population", "generations", "seed"}."""

    def run(self, problem, evaluate, budget, state_file=None, initial=None, on_generation=None, inject=None):
        variables = [v.as_dict() if hasattr(v, "as_dict") else dict(v) for v in problem.variables]
        return optimize(variables, evaluate, budget["population"], budget["generations"], budget.get("seed", 1),
                        state_file, initial=initial, on_generation=on_generation, inject=inject)
