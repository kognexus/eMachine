"""T25: FeatureScript sources free of the warnings Onshape showed for the v2 features and the UI32 studio."""

import glob
import os
import re
import subprocess
import sys
import unittest

from helpers import FEATURESCRIPT, ROOT


def preconditions(source):
    """Text of every precondition block in a Feature Studio source."""
    lines = source.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        if line.strip() != "precondition":
            continue
        depth, block = 0, []
        for other in lines[i + 1:]:
            code = re.sub(r'"[^"]*"', '""', other.split("//")[0])
            depth += code.count("{") - code.count("}")
            block.append(code)
            if depth == 0 and "}" in code:
                break
        blocks.append("\n".join(block))
    return blocks


class FeatureScriptLintTest(unittest.TestCase):
    def sources(self):
        paths = sorted(glob.glob(os.path.join(FEATURESCRIPT, "*.fs")))
        self.assertTrue(paths)
        for path in paths:
            with open(path) as f:
                yield os.path.basename(path), f.read()

    def test_t25_1_preconditions_and_exports(self):
        for name, source in self.sources():
            with self.subTest(file=name):
                for block in preconditions(source):
                    for condition in re.findall(r"\bif\s*\((.*)\)", block):
                        # Onshape's precondition analysis rejects ordering comparisons ("Unexpected operator").
                        self.assertNotRegex(condition, r"[<>]", f"{name}: if ({condition})")
                for match in re.finditer(r"^(.*)\bconst (\w+) = defineFeature\(", source, flags=re.M):
                    self.assertEqual(match.group(1), "export ", f"{name}: feature {match.group(2)} is not exported")

    def test_t25_2_ui32_is_generated(self):
        result = subprocess.run([sys.executable, "-m", "emachine", "ui32", "--check"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
