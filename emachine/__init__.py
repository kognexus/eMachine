"""
emachine: design, analysis and optimization of electrical machines.

Machines (flux path x principle x rotor layout, docs/naming.md), field solvers and optimizers are
plugins registered by name in emachine.core.registry; the pipeline connects them through the interfaces of emachine.core. See
docs/architecture.md.
"""

import importlib

from .core import registry as _registry

__version__ = "0.1.0"

# The built-in plugins (emachine.plugins) are imported at the first registry lookup.
_registry.set_autoload(lambda: importlib.import_module("emachine.plugins"))
