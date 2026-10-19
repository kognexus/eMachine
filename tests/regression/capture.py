"""
Records the baseline results of the regression cases (baseline/<case>.json). Run it only after an
intended change of a model or of a dependency that changes results, and say so in CHANGELOG.md:

    pixi run rebaseline                                   # fast and slow cases (needs Elmer)
    python tests/regression/capture.py [case ...]         # chosen cases
    EMACHINE_SLOW=1 python tests/regression/capture.py    # fast and slow cases
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cases  # noqa: E402


def main(names):
    slow = os.environ.get("EMACHINE_SLOW") == "1" or os.environ.get("TFM_SLOW") == "1"
    selected = dict(cases.FAST, **(cases.SLOW if slow else {}))
    if names:
        selected = {n: f for n, f in {**cases.FAST, **cases.SLOW}.items() if n in names}
    os.makedirs(os.path.join(HERE, "baseline"), exist_ok=True)
    for name, function in selected.items():
        data = function()
        with open(os.path.join(HERE, "baseline", name + ".json"), "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        print("captured", name)


if __name__ == "__main__":
    main(sys.argv[1:])
