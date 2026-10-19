"""T33-2: the loss model behind core.interfaces.LossModel."""

import os
import sys
import tempfile
import unittest

from emachine.core import interfaces
from emachine.physics import losses

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                "regression"))
import cases  # noqa: E402


class LossModelTest(unittest.TestCase):
    def test_interface_and_values(self):
        from emachine.spec import load_spec
        spec = load_spec({"materials": {"rotor_iron": {"conductivity_S_m": 6e6}}})
        model = losses.CoreAndRotorLoss()
        self.assertIsInstance(model, interfaces.LossModel)
        with tempfile.TemporaryDirectory() as tmp:
            files = cases._synthetic_core_files(tmp)
            c = model.coefficients(spec["materials"], files)
            self.assertEqual(c, losses.iron_loss_coefficients(spec, files))
        stator, rotor = model.at(c, 300.0, spec["materials"])
        self.assertEqual((float(stator), float(rotor)),
                         tuple(float(v) for v in losses.loss_at(c, 300.0, spec["materials"])))

    def test_t41_field_of_all_phases_gives_loss_per_phase(self):
        """A field file of the whole machine (key `phases`, as the 2D solver writes) holds the loss of
        all phases; the coefficients are per phase, as for the one-phase TFM sector."""
        import numpy as np
        from emachine.spec import load_spec
        spec = load_spec({"materials": {"rotor_iron": {"conductivity_S_m": 6e6}}})
        with tempfile.TemporaryDirectory() as tmp:
            files = cases._synthetic_core_files(tmp)
            one = losses.iron_loss_coefficients(spec, files)
            for path in files:
                data = dict(np.load(path))
                np.savez(path, **data, phases=3)
            three = losses.iron_loss_coefficients(spec, files)
        for key in losses.COEFFICIENTS:
            self.assertAlmostEqual(three[key], one[key] / 3, delta=1e-12 * abs(one[key]))
        f = 300.0
        stator1, rotor1 = losses.loss_at(one, f, spec["materials"])
        stator3, rotor3 = losses.loss_at(three, f, spec["materials"])
        self.assertAlmostEqual(float(rotor3), float(rotor1) / 3, delta=1e-9 * float(rotor1))
        self.assertEqual(three["core_b_p95_T"], one["core_b_p95_T"])


if __name__ == "__main__":
    unittest.main()
