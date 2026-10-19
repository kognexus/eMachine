"""The code reproduces the recorded baseline results (baseline/*.json; re-record with capture.py)."""

import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cases  # noqa: E402

SLOW = os.environ.get("EMACHINE_SLOW") == "1" or os.environ.get("TFM_SLOW") == "1"


def compare(expected, actual, path, rel):
    """List of differences between two plain data trees (numbers compared with a relative tolerance)."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        out = [f"{path}: missing key {k!r}" for k in expected if k not in actual]
        out += [f"{path}: new key {k!r}" for k in actual if k not in expected]
        for k in expected:
            if k in actual:
                out += compare(expected[k], actual[k], f"{path}.{k}", rel)
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: length {len(actual)} instead of {len(expected)}"]
        out = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += compare(e, a, f"{path}[{i}]", rel)
        return out
    if isinstance(expected, bool) or isinstance(actual, bool):
        return [] if expected == actual else [f"{path}: {actual!r} instead of {expected!r}"]
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if expected is None or actual is None:
            return [] if expected == actual else [f"{path}: {actual!r} instead of {expected!r}"]
        if math.isnan(expected) and math.isnan(actual):
            return []
        if math.isinf(expected) or math.isinf(actual):
            return [] if expected == actual else [f"{path}: {actual!r} instead of {expected!r}"]
        if abs(actual - expected) <= rel * max(abs(expected), abs(actual)) + 1e-12:
            return []
        return [f"{path}: {actual!r} instead of {expected!r}"]
    return [] if expected == actual else [f"{path}: {actual!r} instead of {expected!r}"]


class regressionTest(unittest.TestCase):
    def check(self, name, function):
        path = os.path.join(HERE, "baseline", name + ".json")
        if not os.path.isfile(path):
            self.skipTest(f"no baseline data for {name}: run capture.py")
        with open(path) as f:
            expected = json.load(f)
        actual = json.loads(json.dumps(function(), sort_keys=True))
        differences = compare(expected, actual, name, cases.TOLERANCE.get(name, 1e-9))
        self.assertEqual(differences[:20], [], f"{len(differences)} differences")


def _add(name, function, slow):
    def test(self):
        if slow and not SLOW:
            self.skipTest("slow regression case, set EMACHINE_SLOW=1")
        self.check(name, function)
    setattr(regressionTest, f"test_t32_3_{name}", test)


for _name, _function in cases.FAST.items():
    _add(_name, _function, False)
for _name, _function in cases.SLOW.items():
    _add(_name, _function, True)


if __name__ == "__main__":
    unittest.main()
