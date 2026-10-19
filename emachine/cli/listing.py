"""
`emachine list`: the machine matrix (flux path x principle), the rotor layouts of every
registered machine, and the geometry builders, field solvers and optimizers.

    emachine list               matrix and layouts
    emachine list --flat        one machine per line
    emachine list --markdown    the matrix as Markdown (docs/machines.md)
"""

import argparse

from emachine.core import registry
from emachine.machines import matrix


def main(argv=None):
    ap = argparse.ArgumentParser(prog="emachine list", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flat", action="store_true", help="one machine per line instead of the matrix")
    ap.add_argument("--markdown", action="store_true", help="print the matrix as Markdown")
    args = ap.parse_args(argv)
    if args.markdown:
        print(matrix.markdown(), end="")
        return 0
    if not args.flat:
        print("Machine matrix (flux path x principle):")
        print(matrix.table())
        print()
    print("Machines (flux path/principle: rotor layouts, ticket of those not solvable yet):")
    for name in registry.names("machine"):
        machine = registry.get("machine", name)
        layouts = []
        for rotor in machine.rotors:
            solvable, ticket = machine.rotor_status(rotor)
            layouts.append(rotor + ("" if solvable else f" ({ticket})"))
        state = "solvable" if machine.solvable else "specified"
        print(f"  {name:<10} {state:<10} {', '.join(layouts)}")
    for kind, title in (("geometry", "Geometry builders"), ("solver", "Field solvers"), ("optimizer", "Optimizers")):
        print(f"{title}: {', '.join(registry.names(kind))}")
    return 0
