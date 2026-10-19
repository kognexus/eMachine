"""B05: iron loss from the element flux density."""

import hashlib
import json
import os
import tempfile
import unittest

import numpy as np

from helpers import ROOT, slow

from emachine.machines.tfm import design  # noqa: F401
from emachine.pipeline import evaluate  # noqa: F401
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec

from emachine.pipeline import sweep
from emachine.solvers.elmer import results
from emachine.solvers.elmer.sector3d import ANALYSIS_DEFAULTS

SPEC = os.path.join(ROOT, "examples/tfm_single_phase.json")


class FieldChoiceTest(unittest.TestCase):
    def test_b05_1_element_field_is_preferred(self):
        vector, scalar = np.zeros((4, 3)), np.zeros(4)
        both = {"magnetic flux density": vector, "magnetic vector potential": vector,
                "magnetic flux density e": vector, "temperature": scalar}
        self.assertEqual(results.flux_density_name(both), "magnetic flux density e")
        self.assertEqual(results.flux_density_name({"magnetic flux density": vector}), "magnetic flux density")
        self.assertIsNone(results.flux_density_name({"temperature": scalar}))

    def test_b05_2_cache_key_has_a_model_version(self):
        spec = load_spec(SPEC)
        values = design.clip(spec, REFERENCE_DESIGN)
        relevant = {k: v for k, v in spec.items() if k not in ("optimizer", "variables", "objectives")}
        old = hashlib.sha1(json.dumps({"spec": relevant, "values": values}, sort_keys=True).encode()).hexdigest()[:20]
        self.assertNotEqual(evaluate.cache_key(spec, values), old)
        self.assertGreaterEqual(evaluate.MODEL_VERSION, 2)


@slow
class YokeFluxTest(unittest.TestCase):
    def test_b05_3_and_4_yoke_flux_and_loss(self):
        spec = load_spec(SPEC)
        values = design.clip(spec, REFERENCE_DESIGN)
        d = design.derived(spec, values)
        parameters = design.to_parameters(spec, values)
        analysis = dict(ANALYSIS_DEFAULTS)
        analysis.update(parameters["analysis"])
        analysis.update({"coil_turns": 1, "keep_fields": True})
        with tempfile.TemporaryDirectory() as tmp:
            row = sweep.solve_position(parameters, analysis, 0.0, tmp, current=0.0, core_field=True)
            saved = np.load(row["core_field_file"])
            points, tets, body, fields = results.read_fields(tmp)
            bodies, _ = results.read_names(tmp)
        per_core = abs(row["flux_linkage_Wb"]) / d["pole_pairs"]

        centroid, volume, b = saved["centroid"] * 1e3, saved["volume"], saved["b"]
        radius = np.hypot(centroid[:, 0], centroid[:, 1])
        margin = 0.3
        yoke = ((np.abs(centroid[:, 2]) < d["slot_width"] / 2 - margin)
                & (radius < d["stator_radius"] - d["slot_height"] - margin))
        self.assertGreater(yoke.sum(), 50)
        flux = abs(np.sum(volume[yoke] * b[yoke, 2])) / ((d["slot_width"] - 2 * margin) * 1e-3)
        ratio = flux / per_core
        self.assertGreater(ratio, 0.92)
        self.assertLess(ratio, 1.00)

        # The smoothed nodal field gives a lower flux density and a lower loss.
        core = [bodies[name] for name in bodies if "tfm_core" in name]
        sel = tets[np.isin(body, core)]
        material = spec["materials"]["stator_core"]

        def loss(name):
            magnitude = np.linalg.norm(fields[name][sel].mean(axis=1), axis=1)
            return float(np.sum(volume * (material["k_hysteresis"] * magnitude ** material["alpha"])))
        new, old = loss("magnetic flux density e"), loss("magnetic flux density")
        print(f"\nB05: yoke flux / coil flux per core = {ratio:.3f}; hysteresis loss new / old = {new / old:.3f}")
        self.assertGreater(new / old, 1.05)


if __name__ == "__main__":
    unittest.main()
