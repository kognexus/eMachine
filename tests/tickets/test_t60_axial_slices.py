"""T60: axial machines as unrolled slices: a slice at a large radius against the radial section of the same machine."""

import math
import os
import tempfile
import unittest

from helpers import slow


def machines():
    from emachine.machines.catalogue.base import fscw_sides
    sides, _, _ = fscw_sides(36, 15, 2)
    r = 200.0
    common = {"stack_length": 10.0, "electrical_pole_pairs": 15, "rotor_eddy_width_mm": [1, 1, 1],
              "mesh": {"gap_cell": 0.4, "size_max": 3.0, "reach": 5.0}}
    radial = dict(common, kind="radial", bore_radius=180.0, parts=[
        {"role": "rotor", "type": "surface", "r_in": r - 0.5 - 14.5, "r_out": r - 0.5, "facing": "out", "poles": 30,
         "offset_deg": 0.0, "magnet_thickness": 3.0, "magnet_arc": 0.8},
        {"role": "stator", "type": "slotted", "r_in": r, "r_out": r + 18.0, "facing": "in", "slots": 36, "slot_depth": 10.0,
         "slot_width": 15.0, "tip_height": 0.0, "opening": 0.0, "sides": sides}])
    share = 15.0 / (2 * math.pi * r / 36)
    axial = dict(common, kind="axial", slices=[{"radius": r, "depth": 10.0}], layers=[
        {"role": "rotor", "type": "surface", "z0": 0.0, "z1": 14.5, "faces": "up", "poles": 30, "magnet_thickness": 3.0,
         "magnet_arc": 0.8},
        {"role": "stator", "z0": 15.0, "z1": 33.0, "faces": "down", "slots": 36, "slot_share": share, "slot_depth": 10.0,
         "tip_height": 0.0, "sides": sides}])
    return radial, axial


class SliceTest(unittest.TestCase):
    @slow
    def test_t60_2_slice_equals_large_radial_machine(self):
        import emachine.plugins  # noqa: F401
        from emachine.core import registry
        from emachine.core.types import Excitation, GeometryRequest
        radial, axial = machines()
        settings = {"magnet_remanence_T": 1.25, "magnet_mu_r": 1.05, "stator_core_mu_r": 4000.0, "rotor_iron_mu_r": 4000.0,
                    "keep_fields": False}
        builder = registry.create("geometry", "section2d")
        solver = registry.create("solver", "elmer_sections", settings=settings)
        best = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name, params in (("radial", radial), ("axial", axial)):
                folder = os.path.join(tmp, name)
                mesh = builder.build(GeometryRequest("section2d", params), 1.0, folder)
                torques = []
                for gamma in range(0, 360, 20):     # the current angle of the most torque, either way round
                    ni = tuple(600.0 * math.cos(math.radians(gamma - 120 * k)) for k in range(3))
                    torques.append(solver.solve(mesh, Excitation(rotor_angle_deg=1.0, ampere_turns=ni), folder).torque_Nm)
                best[name] = max(abs(t) for t in torques)
        self.assertGreater(best["radial"], 0.5)
        self.assertAlmostEqual(best["axial"], best["radial"], delta=0.05 * best["radial"])

if __name__ == "__main__":
    unittest.main()
