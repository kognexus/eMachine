"""
Random search: designs drawn uniformly from the variable ranges, `population` per generation; the
population kept is the best by constrained domination and crowding (as NSGA-II's survival). A
baseline for comparing optimizers, and the second implementation of the Optimizer interface.
"""

import json
import os

import numpy as np

from emachine.core.interfaces import Optimizer
from emachine.core.registry import register

from .nsga2 import _evaluate, _rank, _record, _survive, random_design


@register("optimizer", "random")
class RandomSearch(Optimizer):
    def run(self, problem, evaluate, budget, state_file=None, initial=None, on_generation=None, inject=None):
        variables = [v.as_dict() if hasattr(v, "as_dict") else dict(v) for v in problem.variables]
        size, generations = int(budget["population"]), int(budget["generations"])
        rng = np.random.default_rng(budget.get("seed", 1))
        state = {"generation": 0, "population": [], "archive": {}, "evaluations": 0, "history": []}
        designs = list(initial or [])
        while len(designs) < size:
            designs.append(random_design(variables, rng))
        state["population"] = _survive(_evaluate(designs, state, evaluate), size)
        _record(state)
        for _ in range(generations):
            batch = [random_design(variables, rng) for _ in range(size)]
            state["population"] = _survive(state["population"] + _evaluate(batch, state, evaluate), size)
            state["generation"] += 1
            _record(state)
            if on_generation:
                on_generation(state)
        _rank(state["population"])
        if state_file:
            with open(state_file + ".tmp", "w") as f:
                json.dump(state, f)
            os.replace(state_file + ".tmp", state_file)
        return state
