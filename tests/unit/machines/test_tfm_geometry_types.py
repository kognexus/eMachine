"""T34-2: stator and rotor types of the TFM geometry, one module each, extendable by registration."""

import unittest

import gmsh

from emachine.machines.tfm.geometry import DEFAULTS, build_rotor, build_stator, occ
from emachine.machines.tfm.geometry import rotors, stators


class TypesTest(unittest.TestCase):
    def test_registered_types(self):
        self.assertEqual(sorted(stators.STATORS), ["c", "cp", "e", "tr", "u", "ui", "z"])
        self.assertEqual(sorted(rotors.ROTORS), ["axial", "flux_concentrating", "halbach", "surface"])
        self.assertEqual({k for k, v in stators.STATORS.items() if v.analysable}, {"u", "ui", "cp", "tr"})

    def test_unknown_types(self):
        with self.assertRaises(SystemExit):
            build_stator(dict(DEFAULTS["stator"], core_type="x"))
        with self.assertRaises(SystemExit):
            build_rotor(dict(DEFAULTS["rotor"], type="x"), 0.0)

    def test_new_stator_type_needs_only_its_class(self):
        class PlainRing(stators.StatorType):
            """A plain ring without teeth: enough to show the extension point."""
            code = "plain"

            def build(self, f, sp):
                walls = sorted((f.radial(0.0), f.radial(f.height)))
                return [(3, stators.ring(*walls, -f.half_w, f.half_w))]

        stators.STATORS["plain"] = PlainRing()
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        try:
            parts, names, info = build_stator(dict(DEFAULTS["stator"], core_type="plain", include_coil=False))
            occ.synchronize()
            self.assertEqual(names, ["tfm_core"])
            self.assertEqual(info["core_type"], "plain")
            self.assertGreater(occ.getMass(3, parts[0][1]), 0.0)
        finally:
            gmsh.finalize()
            del stators.STATORS["plain"]


if __name__ == "__main__":
    unittest.main()
