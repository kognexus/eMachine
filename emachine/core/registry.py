"""
Plugin registry: machines, geometry builders, field solvers and optimizers register under a kind
and a name, and are created by name. The pipeline never names a concrete class.

    @register("solver", "elmer3d")
    class ElmerSector3D(FieldSolver): ...

    solver = create("solver", "elmer3d")
"""

import importlib
import threading

KINDS = ("machine", "geometry", "solver", "optimizer")

_plugins = {kind: {} for kind in KINDS}
_autoload = {"function": None, "started": False, "finished": False}
_autoload_lock = threading.RLock()


def set_autoload(function):
    """A function that imports the built-in plugins; called once, at the first lookup. Set by the
    emachine package, so that core itself names no plugin module."""
    with _autoload_lock:
        _autoload.update(function=function, started=False, finished=False)


def _ensure_loaded():
    """Runs the autoload once. Lookups from other threads (rotor positions are solved in a thread pool)
    wait until it has finished; a lookup made while the plugins are being imported returns at once."""
    if _autoload["finished"]:
        return
    with _autoload_lock:
        if _autoload["started"] or _autoload["function"] is None:
            return
        _autoload["started"] = True
        try:
            _autoload["function"]()
        finally:
            _autoload["finished"] = True


class RegistryError(KeyError):
    def __str__(self):
        return str(self.args[0]) if self.args else ""


def _kind(kind):
    if kind not in _plugins:
        raise RegistryError(f"Unknown plugin kind {kind!r}; kinds are {', '.join(KINDS)}.")
    return _plugins[kind]


def register(kind, name):
    """Class decorator: registers the class under (kind, name). A different class under a taken name is an error."""
    table = _kind(kind)

    def decorate(cls):
        known = table.get(name)
        if known is not None and known is not cls and \
                (known.__module__, known.__qualname__) != (cls.__module__, cls.__qualname__):
            raise RegistryError(f"{kind} {name!r} is already registered by {known.__module__}.{known.__qualname__}.")
        table[name] = cls
        return cls

    return decorate


def get(kind, name):
    _ensure_loaded()
    table = _kind(kind)
    if name not in table:
        known = ", ".join(sorted(table)) or "none"
        raise RegistryError(f"No {kind} named {name!r}. Registered: {known}.")
    return table[name]


def create(kind, name, **options):
    return get(kind, name)(**options)


def names(kind):
    _ensure_loaded()
    return sorted(_kind(kind))


def load(modules):
    """Imports plugin modules (their decorators register them). Module names are passed in, so core
    depends on no plugin package."""
    for module in modules:
        importlib.import_module(module)


def snapshot():
    _ensure_loaded()
    return {kind: dict(table) for kind, table in _plugins.items()}


def restore(saved):
    for kind in KINDS:
        _plugins[kind] = dict(saved.get(kind, {}))
