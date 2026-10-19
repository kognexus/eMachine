"""
The design space of a specification: the machine it names (flux path/principle) and that machine's
variables, dimensions, checks and geometry, under the function names the pipeline uses.
"""

from emachine.core import registry
from emachine.spec.names import standard_values


def machine_of(spec):
    m = spec["machine"]
    return registry.create("machine", f"{m['flux_path']}/{m['principle']}")


def variables(spec):
    """Ordered design variables: list of {name, kind ('int' or 'real'), low, high}."""
    return [v.as_dict() for v in machine_of(spec).variables(spec)]


def clip(spec, values):
    """Values rounded (integers) and clipped to their bounds, as a new dictionary."""
    values, out = standard_values(spec, values), {}
    for var in variables(spec):
        value = values[var["name"]]
        if var["kind"] == "int":
            value = int(round(value))
        out[var["name"]] = min(max(value, var["low"]), var["high"])
    return out


def to_vector(spec, values):
    return [values[v["name"]] for v in variables(spec)]


def to_values(spec, vector):
    return clip(spec, {v["name"]: x for v, x in zip(variables(spec), vector)})


def derived(spec, values):
    return machine_of(spec).derive(spec, values)


def geometry(spec, values, level=None):
    return machine_of(spec).geometry(spec, values, level)


def parameters(spec, values, level=None):
    return geometry(spec, values, level).parameters


def checks(spec, values):
    return machine_of(spec).checks(spec, values)


def violations(results):
    return [c for c in results if c.violation > 0]


def total_violation(results):
    return sum(c.violation for c in results)


def is_feasible(results):
    return total_violation(results) == 0
