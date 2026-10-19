"""
The built-in plugins. Importing a plugin module registers it (emachine.core.registry). A new
machine, solver or optimizer is added by writing its module and listing it here.
"""

import importlib

BUILTIN = (
    "emachine.machines.tfm.pmsm",
    "emachine.machines.tfm.srm",
    "emachine.machines.rfm.pmsm",
    "emachine.machines.rfm.synrm",
    "emachine.machines.rfm.srm",
    "emachine.machines.afm.pmsm",
    "emachine.machines.afm.srm",
    "emachine.machines.rafm.pmsm",
    "emachine.machines.tfm.geometry.builder",
    "emachine.machines.rfm.builder",
    "emachine.machines.rafm.builder",
    "emachine.machines.section2d.builder",
    "emachine.solvers.elmer.sector3d",
    "emachine.solvers.elmer.section2d",
    "emachine.solvers.elmer.quasi3d",
    "emachine.solvers.elmer.sections",
    "emachine.solvers.analytic",
    "emachine.optimization.nsga2",
    "emachine.optimization.random_search",
)

for _module in BUILTIN:
    importlib.import_module(_module)
