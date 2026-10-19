"""
Constrained domination and Pareto fronts, shared by the optimizers. An individual is a dict with
x (design vector), f (objectives, all minimised) and violation (0 = feasible). A feasible design
beats an infeasible one, and of two infeasible designs the one with the smaller violation wins.
"""

import math


def key_of(x):
    """Identity of a design, used to avoid evaluating duplicates."""
    return ",".join(f"{v:.10g}" for v in x)


def dominates(a, b):
    """Constrained domination of individual a over individual b."""
    va, vb = a["violation"], b["violation"]
    if va > 0 or vb > 0:
        return va < vb
    fa, fb = a["f"], b["f"]
    return all(x <= y for x, y in zip(fa, fb)) and any(x < y for x, y in zip(fa, fb))


def non_dominated_sort(population):
    """List of fronts, each a list of indices into `population`. Front 0 is the best."""
    n = len(population)
    dominated_by = [[] for _ in range(n)]
    counts = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if dominates(population[i], population[j]):
                dominated_by[i].append(j)
                counts[j] += 1
            elif dominates(population[j], population[i]):
                dominated_by[j].append(i)
                counts[i] += 1
    fronts = [[i for i in range(n) if counts[i] == 0]]
    while fronts[-1]:
        nxt = []
        for i in fronts[-1]:
            for j in dominated_by[i]:
                counts[j] -= 1
                if counts[j] == 0:
                    nxt.append(j)
        fronts.append(nxt)
    return fronts[:-1]


def crowding_distance(population, front):
    """Crowding distance of each member of a front (same order as `front`)."""
    size = len(front)
    if size <= 2:
        return [math.inf] * size
    if any(population[i]["violation"] > 0 for i in front):
        return [0.0] * size             # infeasible designs are ranked by violation alone
    distance = [0.0] * size
    for m in range(len(population[front[0]]["f"])):
        values = [population[i]["f"][m] for i in front]
        order = sorted(range(size), key=lambda k: values[k])
        distance[order[0]] = distance[order[-1]] = math.inf
        span = values[order[-1]] - values[order[0]]
        if not math.isfinite(span) or span <= 0:
            continue
        for a in range(1, size - 1):
            distance[order[a]] += (values[order[a + 1]] - values[order[a - 1]]) / span
    return distance


def pareto_front(population):
    """Feasible, non-dominated individuals of a population, without duplicates."""
    feasible = [p for p in population if p["violation"] == 0]
    if not feasible:
        return []
    front = [feasible[i] for i in non_dominated_sort(feasible)[0]]
    unique = {}
    for p in front:
        unique.setdefault(key_of(p["x"]), p)
    return list(unique.values())
