"""
Starting designs for an optimization, taken from earlier runs or design files.

A source is a run folder (its pareto.csv), a .csv table with one column per design variable, or
a .json file: a parameter file written by the optimizer, a dictionary of design variable values,
or a list of such dictionaries. Seeds are fitted to the current specification: clipped to the
current ranges, missing variables set to the middle of their range, and dropped when they fail
the geometry checks.
"""

import csv
import json
import os
import shutil

from emachine.spec.names import standard_values
from . import design_space as design
from . import evaluate


class SeedError(ValueError):
    """A seed source could not be read. The message names the file."""


def _from_csv(path):
    with open(path, newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _from_json(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("design"), dict):
        return [data["design"]]                     # parameter file of a pick
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list) and all(isinstance(d, dict) for d in data):
        return [d.get("design", d) if isinstance(d.get("design"), dict) else d for d in data]
    raise SeedError(f"{path}: expected a parameter file, a dictionary of design variables or a list of them.")


def _full_precision(rows, cache_dir):
    """
    Replaces the rounded values of a results table by the exact values of the cached records, so
    that the cache of the source run can be reused.
    """
    exact = {}
    for name in os.listdir(cache_dir):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(cache_dir, name)) as f:
                values = json.load(f)["values"]
        except (ValueError, KeyError, OSError):
            continue
        exact[tuple(sorted((k, f"{float(v):.6g}") for k, v in values.items()))] = values
    out = []
    for row in rows:
        for values in exact.values():
            if all(k in row and row[k] != "" and f"{float(row[k]):.6g}" == f"{float(v):.6g}" for k, v in values.items()):
                row = {**row, **values}
                break
        out.append(row)
    return out


def read_source(path):
    """Raw designs of one source: list of {column: value}. Values may still be strings."""
    if os.path.isdir(path):
        table = os.path.join(path, "pareto.csv")
        if not os.path.isfile(table):
            raise SeedError(f"{path}: no pareto.csv in this run folder.")
        rows = _from_csv(table)
        cache = os.path.join(path, "cache")
        return _full_precision(rows, cache) if os.path.isdir(cache) else rows
    if not os.path.isfile(path):
        raise SeedError(f"{path}: no such file or folder.")
    if path.lower().endswith(".csv"):
        return _from_csv(path)
    if path.lower().endswith(".json"):
        return _from_json(path)
    raise SeedError(f"{path}: a seed source is a run folder, a .csv file or a .json file.")


def _number_or_text(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def fit(spec, raw):
    """
    One raw design fitted to the specification.
    Returns (values, clipped names, filled names). Raises SeedError when no variable is usable.
    """
    values, clipped, filled = {}, [], []
    raw = standard_values(spec, {k: _number_or_text(v) for k, v in raw.items()})
    for var in design.variables(spec):
        name = var["name"]
        text = raw.get(name)
        if text is None or text == "":
            values[name] = (var["low"] + var["high"]) / 2
            filled.append(name)
            continue
        try:
            value = float(text)
        except (TypeError, ValueError):
            raise SeedError(f"Design variable '{name}' has the value {text!r}, which is not a number.")
        if value < var["low"] - 1e-9 or value > var["high"] + 1e-9:
            clipped.append(name)
        values[name] = value
    if len(filled) == len(values):
        raise SeedError("The source has none of the design variables of this machine.")
    return design.clip(spec, values), clipped, filled


def _spread(items, count):
    """`count` items spread evenly over the list, keeping both ends."""
    if len(items) <= count:
        return list(items)
    if count == 1:
        return [items[0]]
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]


def collect(spec, sources, max_seeds=None):
    """
    Seeds from all sources. Returns (seeds, summary); a seed is {"values", "source"}.
    The summary counts what was read, clipped, filled, dropped and kept for every source.
    """
    seeds, summary, seen = [], [], set()
    for path in sources:
        info = {"source": path, "read": 0, "clipped": 0, "filled": 0, "infeasible": 0, "duplicate": 0, "kept": 0}
        kept = []
        try:
            raws = read_source(path)
        except SeedError as error:          # a missing or unreadable source must not stop an unattended run
            info["error"] = str(error)
            summary.append(info)
            seeds.append([])
            continue
        for raw in raws:
            info["read"] += 1
            values, clipped, filled = fit(spec, raw)
            info["clipped"] += bool(clipped)
            info["filled"] += bool(filled)
            if not design.is_feasible(design.checks(spec, values)):
                info["infeasible"] += 1
                continue
            key = json.dumps(values, sort_keys=True)
            if key in seen:
                info["duplicate"] += 1
                continue
            seen.add(key)
            try:
                torque = float(raw.get("torque_Nm"))
            except (TypeError, ValueError):
                torque = None
            kept.append({"values": values, "source": path, "torque": torque})
        info["kept"] = len(kept)
        summary.append(info)
        seeds.append(kept)

    total = sum(len(k) for k in seeds)
    if max_seeds is not None and total > max_seeds:
        # Thin every source in proportion, spread along its torque order so the whole trade-off stays covered.
        out = []
        for kept, info in zip(seeds, summary):
            share = max(1, round(max_seeds * len(kept) / total)) if kept else 0
            if all(s["torque"] is not None for s in kept):
                kept = sorted(kept, key=lambda s: -s["torque"])
            kept = _spread(kept, share)
            info["kept"] = len(kept)
            out.append(kept)
        seeds = out
    flat = [{"values": s["values"], "source": s["source"]} for kept in seeds for s in kept]
    if max_seeds is not None:
        flat = flat[:max_seeds]
    return flat, summary


def copy_cached(spec, seeds, rundir, analyse=None):
    """
    Copies what a source run already knows about the seeds into the cache of this run: complete
    results when the specification is the same, and field solutions when only limits, speed or
    other data outside the field differ. Returns the number of seeds that need no field solution.
    """
    ready = 0
    for seed in seeds:
        record = evaluate.record_name(spec, seed["values"], analyse)
        field = os.path.join("fields", evaluate.field_key(spec, design.parameters(spec, seed["values"]), analyse) + ".json")
        found = False
        for name in (record, field):
            target = os.path.join(rundir, "cache", name)
            source = os.path.join(seed["source"], "cache", name) if os.path.isdir(seed["source"]) else None
            if not os.path.isfile(target) and source and os.path.isfile(source):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(source, target)
            found = found or os.path.isfile(target)
        ready += found
    return ready


def describe(summary):
    """One line per source for the log and the report."""
    lines = []
    for info in summary:
        if info.get("error"):
            lines.append(f"skipped: {info['error']}")
            continue
        parts = [f"{info['kept']} of {info['read']} designs used"]
        for key, text in (("clipped", "clipped to the current ranges"), ("filled", "completed with mid-range values"),
                          ("infeasible", "dropped by the geometry checks"), ("duplicate", "duplicates")):
            if info[key]:
                parts.append(f"{info[key]} {text}")
        lines.append(f"{info['source']}: " + ", ".join(parts))
    return lines
