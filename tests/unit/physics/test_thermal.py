"""T33-3: thermal network solver on a given network."""

import unittest

from emachine.core.types import ThermalNetwork
from emachine.physics import thermal


class ThermalTest(unittest.TestCase):
    def setUp(self):
        self.network = ThermalNetwork(conductances=(("winding", "core", 2.0), ("core", "ambient", 1.0),
                                                    ("core", "rotor", 0.5), ("rotor", "ambient", 0.25)),
                                      ambient_C=20.0)

    def test_series_network(self):
        temps, flows = thermal.solve(self.network, {"winding": 2.0, "core": 0.0, "rotor": 0.0})
        # All heat leaves through core (1 W/K) and rotor (0.25 W/K via 0.5 W/K): 2 W in total.
        self.assertAlmostEqual(sum(flows.values()), 2.0)
        self.assertAlmostEqual(temps["winding"] - temps["core"], 1.0)

    def test_response_is_linear(self):
        rise = thermal.response(self.network, ("winding", "core", "rotor"))
        temps, _ = thermal.solve(self.network, {"winding": 3.0, "core": 1.0, "rotor": 0.5})
        for node in ("winding", "core", "rotor"):
            predicted = 20.0 + 3.0 * rise[node][0] + 1.0 * rise[node][1] + 0.5 * rise[node][2]
            self.assertAlmostEqual(temps[node], predicted)

    def test_coupled_copper_loss(self):
        # Copper loss rises with the winding temperature: 2 W at 20 C, + 0.4 % per K.
        result = thermal.coupled(self.network, lambda t: 2.0 * (1 + 0.004 * (t - 20.0)), {"core": 1.0})
        self.assertTrue(result["converged"])
        temps, _ = thermal.solve(self.network, {"winding": result["copper_loss_W"], "core": 1.0, "rotor": 0.0})
        self.assertAlmostEqual(result["winding_C"], temps["winding"], places=4)

    def test_negative_conductance(self):
        with self.assertRaises(ValueError):
            thermal.solve(ThermalNetwork(conductances=(("a", "ambient", -1.0),), ambient_C=20.0), {"a": 1.0})


if __name__ == "__main__":
    unittest.main()
