#!/usr/bin/env python3
"""
Writes tfm_ui32_design.fs: the "TFM UI32 machine" feature followed by the code of tfm_stator.fs and
tfm_rotor.fs.

The stator and rotor features are copied as plain functions, not as features. Onshape flags a
feature defined with defineFeature that is not exported ("Nonconforming feature function: Missing
export"), and exporting the copies would list "TFM stator" and "TFM rotor" twice in the document.
Each function fills the fields it is not given from the defaults of its feature, as calling the
feature would.

    emachine ui32            # rewrite tfm_ui32_design.fs
    emachine ui32 --check    # exit 1 if the file is out of date
"""

import os
import re
import sys

from . import FEATURESCRIPT_DIR as HERE
TARGET = os.path.join(HERE, "tfm_ui32_design.fs")
STATOR_MARK = "/**\n * TFM stator\n"
# Helpers the rotor shares with the stator under the same name and with the same code.
SHARED_HELPERS = ("tfmSolids", "tfmRing")


def closing(lines, start):
    """Index of the line that closes the brace opened on or after lines[start]."""
    depth, opened = 0, False
    for i in range(start, len(lines)):
        code = re.sub(r'"[^"]*"', '""', lines[i].split("//")[0])
        depth += code.count("{") - code.count("}")
        opened = opened or "{" in code
        if opened and depth == 0:
            return i
    raise ValueError(f"no closing brace after line {start + 1}")


def as_function(source, name, defaults_name, title):
    """The feature `name` of a Feature Studio source, rewritten as a function with a defaults map."""
    lines = source.splitlines()
    head = next(i for i, l in enumerate(lines) if re.match(rf"export const {name} = defineFeature\(", l))
    annotation = max(i for i in range(head) if lines[i].startswith('annotation { "Feature Type Name"'))
    pre_end = closing(lines, head + 2)                     # the precondition block
    body_start = pre_end + 1
    split = next(i for i in range(body_start, len(lines)) if lines[i] == "    }, {")
    end = next(i for i in range(split, len(lines)) if lines[i] == "        });")
    body = [l[4:] if l.startswith("    ") else l for l in lines[body_start + 1:split]]   # inside the body's braces
    defaults = ["{"] + lines[split + 1:end] + ["        };"]
    function = ([f"/** {title}, as a function: fields not given take the defaults of the feature. */",
                 f"function {name}(context is Context, id is Id, given is map)",
                 "{",
                 f"    const definition = mergeMaps({defaults_name}, given);"]
                + body + ["}", "", f"const {defaults_name} = " + defaults[0]] + defaults[1:])
    return "\n".join(lines[:annotation] + function + lines[end + 1:])


def drop_function(source, name):
    """Removes a top-level function and the doc comment directly above it."""
    lines = source.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(f"function {name}("))
    end = closing(lines, start)
    first = start
    if lines[first - 1].strip().endswith("*/"):
        while not lines[first - 1].lstrip().startswith("/**"):
            first -= 1
        first -= 1
    while end + 1 < len(lines) and not lines[end + 1].strip():
        end += 1
    return "\n".join(lines[:first] + lines[end + 1:])


def body_of(path):
    """A Feature Studio without its version header and import."""
    with open(os.path.join(HERE, path)) as f:
        lines = f.read().splitlines()
    return "\n".join(lines[3:])


def build():
    with open(TARGET) as f:
        current = f.read()
    machine = current[:current.index(STATOR_MARK)]
    stator = as_function(body_of("tfm_stator.fs"), "tfmStator", "TFM_STATOR_DEFAULTS", "The \"TFM stator\" feature")
    rotor = as_function(body_of("tfm_rotor.fs"), "tfmInrunnerRotor", "TFM_ROTOR_DEFAULTS", "The \"TFM rotor\" feature")
    for helper in SHARED_HELPERS:
        rotor = drop_function(rotor, helper)
    return machine + stator + "\n\n" + rotor.rstrip("\n") + "\n"


def main():
    text = build()
    with open(TARGET) as f:
        current = f.read()
    if "--check" in sys.argv[1:]:
        if text != current:
            sys.exit("tfm_ui32_design.fs is out of date: run `emachine ui32`")
        print("tfm_ui32_design.fs is up to date")
        return
    with open(TARGET, "w") as f:
        f.write(text)
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
