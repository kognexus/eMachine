"""T10: thermal model."""

import unittest

from helpers import copper_loss, coupled, heat_balance, machine_of

from emachine.machines.tfm import design
from emachine.core.types import ThermalNetwork
from emachine.physics import thermal
from emachine.machines.tfm.reference import REFERENCE_DESIGN
from emachine.spec import load_spec


class NetworkTest(unittest.TestCase):
    def test_t10_1_single_resistance(self):
        temps, flows = solve_network({"a": 10.0}, [("a", "ambient", 0.5)], 25.0)   # 2 K/W
        self.assertAlmostEqual(temps["a"], 45.0, places=12)
        self.assertAlmostEqual(flows["a"], 10.0, places=12)

    def test_t10_2_two_in_series(self):
        temps, flows = solve_network({"a": 10.0, "b": 0.0},
                                             [("a", "b", 1.0), ("b", "ambient", 0.5)], 25.0)   # 1 K/W then 2 K/W
        self.assertAlmostEqual(temps["a"], 55.0, places=12)
        self.assertAlmostEqual(temps["b"], 45.0, places=12)
        self.assertAlmostEqual(flows["b"], 10.0, places=12)

    def test_parallel_paths(self):
        temps, flows = solve_network({"a": 12.0}, [("a", "ambient", 1.0), ("ambient", "a", 2.0)], 20.0)
        self.assertAlmostEqual(temps["a"], 24.0, places=12)
        self.assertAlmostEqual(flows["a"], 12.0, places=12)


def solve_network(heat_W, conductances, ambient_C):
    return thermal.solve(ThermalNetwork(conductances=tuple(conductances), ambient_C=ambient_C), heat_W)


class MachineThermalTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec({})
        self.values = design.clip(self.spec, REFERENCE_DESIGN)
        self.d = design.derived(self.spec, self.values)

    def test_t10_3_energy_balance(self):
        for copper, iron, rotor in ((5.0, 2.0, 0.0), (0.0, 3.0, 1.0), (12.5, 0.0, 0.0)):
            temps, flows = heat_balance(self.spec, self.values, copper, iron, rotor)
            self.assertAlmostEqual(sum(flows.values()), copper + iron + rotor, delta=1e-9)
            self.assertTrue(all(t >= 25.0 - 1e-9 for t in temps.values()))

    def test_t10_4_more_loss_is_hotter(self):
        low, _ = heat_balance(self.spec, self.values, 5.0, 2.0)
        high, _ = heat_balance(self.spec, self.values, 10.0, 2.0)
        self.assertGreater(high["winding"], low["winding"])
        self.assertGreater(high["core"], low["core"])
        self.assertGreater(low["winding"], low["core"])          # heat flows from winding to core
        self.assertGreater(low["core"], low["rotor"])

    def test_t10_5_better_cooling_is_cooler(self):
        base, _ = heat_balance(self.spec, self.values, 5.0, 2.0)
        better = load_spec({"thermal": {"h_external_W_m2K": 50.0}})
        cooler, _ = heat_balance(better, self.values, 5.0, 2.0)
        for node in base:
            self.assertLess(cooler[node], base[node])

    def test_t10_6_coupled_iteration(self):
        result = coupled(self.spec, self.values, iron_loss_W=1.0)
        self.assertTrue(result["converged"])
        self.assertLess(result["iterations"], 20)
        winding = machine_of(self.spec).winding(self.spec, self.values)
        cold = copper_loss(self.spec, winding, self.d["ampere_turns_rms"], 20.0)
        self.assertGreater(result["copper_loss_W"], cold)
        self.assertGreater(result["winding_C"], result["core_C"])
        self.assertAlmostEqual(result["heat_to_ambient_W"], result["copper_loss_W"] + 1.0, delta=1e-6)

    def test_t10_7_runaway(self):
        hot = load_spec({"thermal": {"h_external_W_m2K": 1e-3, "h_mount_W_m2K": 1e-3},
                         "variables": {"current_density_A_mm2": [1.0, 60.0]},
                         "limits": {"max_current_density_A_mm2": 60.0}})
        values = design.clip(hot, dict(REFERENCE_DESIGN, current_density_A_mm2=60.0))
        result = coupled(hot, values, iron_loss_W=1.0)
        self.assertFalse(result["converged"])
        self.assertGreater(result["winding_C"], hot["limits"]["max_winding_temp_C"])

    def test_inrunner_network(self):
        spec = load_spec({"machine": {"configuration": "inrunner", "stator_type": "u", "rotor_type": "surface",
                                      "outer_diameter_mm": 120.0, "stack_length_mm": 40.0}})
        values = design.clip(spec, {"pole_pairs": 16, "tooth_span": 0.7, "leg_width_mm": 8.0, "slot_height_mm": 20.0,
                                    "yoke_height_mm": 8.0, "magnet_thickness_mm": 4.0, "current_density_A_mm2": 4.0,
                                    "magnet_arc_ratio": 0.85})
        temps, flows = heat_balance(spec, values, 8.0, 3.0)
        self.assertAlmostEqual(sum(flows.values()), 11.0, delta=1e-9)
        self.assertGreater(temps["winding"], temps["core"])


if __name__ == "__main__":
    unittest.main()
