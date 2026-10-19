"""
Writes the Onshape Feature Studio emachine/cad/featurescript/emachine_design.fs: the "eMachine"
feature of emachine_main.fs, followed by the TFM stator and rotor code (tfm_stator.fs, tfm_rotor.fs
of machines/tfm/cad/featurescript) as plain functions, as for the UI32 studio. Paste the result into
a Feature Studio in Onshape; only the eMachine feature is exported.

Also writes hybrid_design.fs: the features of the hybrid machines (hybrid/*.fs, T54) with the shape
helpers of emachine_main.fs.

    emachine featurescript            # rewrite emachine_design.fs and hybrid_design.fs
    emachine featurescript --check    # exit 1 if the file is out of date
"""

import os
import sys

from emachine.machines.tfm.cad import ui32_build

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "featurescript")
MAIN = os.path.join(HERE, "emachine_main.fs")
TARGET = os.path.join(HERE, "emachine_design.fs")
#: hybrid machines (T54): their own studio, with the shape helpers of emachine_main.fs
HYBRID = (os.path.join(HERE, "hybrid", "raxial.fs"),)
HYBRID_TARGET = os.path.join(HERE, "hybrid_design.fs")
SHAPES_MARKER = "// ---------------------------------------------------------------- shapes"


def build():
    with open(MAIN) as f:
        main = f.read().rstrip("\n")
    stator = ui32_build.as_function(ui32_build.body_of("tfm_stator.fs"), "tfmStator", "TFM_STATOR_DEFAULTS",
                                    "The \"TFM stator\" feature")
    rotor = ui32_build.as_function(ui32_build.body_of("tfm_rotor.fs"), "tfmInrunnerRotor", "TFM_ROTOR_DEFAULTS",
                                   "The \"TFM rotor\" feature")
    for helper in ui32_build.SHARED_HELPERS:
        rotor = ui32_build.drop_function(rotor, helper)
    banner = ("\n\n// ================================================================ generated below\n"
              "// The TFM stator and rotor code, copied from machines/tfm/cad/featurescript by\n"
              "// \"emachine featurescript\". Edit tfm_stator.fs and tfm_rotor.fs, not this copy.\n")
    return main + banner + stator + "\n\n" + rotor.rstrip("\n") + "\n"


def build_hybrid():
    """The hybrid studio: each hybrid feature (hybrid/*.fs) and the shape helpers of emachine_main.fs."""
    with open(MAIN) as f:
        main = f.read()
    shapes = main[main.index(SHAPES_MARKER):].rstrip("\n")
    parts = []
    for i, path in enumerate(HYBRID):
        with open(path) as f:
            text = f.read().rstrip("\n")
        if i:                                   # one header per studio
            text = text[text.index("\n", text.index("import(")) + 1:]
        parts.append(text)
    banner = ("\n\n// ================================================================ generated below\n"
              "// The shape helpers of emachine_main.fs, copied by \"emachine featurescript\".\n\n")
    return "\n\n".join(parts) + banner + shapes + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    stale = 0
    for target, text in ((TARGET, build()), (HYBRID_TARGET, build_hybrid())):
        name = os.path.basename(target)
        current = open(target).read() if os.path.isfile(target) else ""
        if "--check" in argv:
            if text != current:
                print(f"{name} is out of date: run emachine featurescript", file=sys.stderr)
                stale = 1
            else:
                print(f"{name} is up to date")
            continue
        with open(target, "w") as f:
            f.write(text)
        print(f"wrote {target} ({len(text.splitlines())} lines)")
    return stale


if __name__ == "__main__":
    sys.exit(main())
