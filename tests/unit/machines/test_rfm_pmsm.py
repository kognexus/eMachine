"""T41: the radial-flux surface PMSM end to end (12-slot 10-pole reference machine of examples/)."""

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, slow

SPEC = os.path.join(ROOT, "examples", "rfm_spm_12s10p.json")
DESIGN = os.path.join(ROOT, "examples", "rfm_spm_12s10p_design.json")


def reference():
    from emachine.core import registry
    from emachine.spec import load_spec
    spec = load_spec(SPEC)
    with open(DESIGN) as f:
        values = json.load(f)
    machine = registry.create("machine", "rfm/pmsm")
    return spec, values, machine, machine.derive(spec, values), machine.geometry(spec, values)


@slow
class SectionMeshTest(unittest.TestCase):
    def test_t41_2_region_areas(self):
        from emachine.core import registry
        spec, values, machine, d, request = reference()
        p = request.parameters["rfm"]
        with tempfile.TemporaryDirectory() as tmp:
            regions = registry.create("geometry", "rfm.section2d").build(request, 7.0, tmp).regions
        area = lambda prefix: sum(r["area_mm2"] for n, r in regions.items() if n.startswith(prefix))
        # the regions tile the whole disc
        self.assertAlmostEqual(area(""), math.pi * p["outer_radius"] ** 2, delta=1e-6 * p["outer_radius"] ** 2)
        # parallel-sided slots: the arcs at bore and bottom change the area by well under 1 %
        self.assertAlmostEqual(area("coil_") / (p["slots"] * p["slot_width"] * p["slot_depth"]), 1.0, delta=0.01)
        self.assertEqual(len([n for n in regions if n.startswith("coil_")]), 2 * p["slots"])
        rr = p["bore_radius"] - p["air_gap"]
        hm, poles = p["magnet_thickness"], 2 * p["pole_pairs"]
        magnet = math.pi * (rr ** 2 - (rr - hm) ** 2) * p["magnet_arc_ratio"] / poles
        for j in range(poles):
            self.assertAlmostEqual(regions[f"magnet_{j}"]["area_mm2"], magnet, delta=1e-6 * magnet)
        self.assertAlmostEqual(area("gap_"), math.pi * (p["bore_radius"] ** 2 - rr ** 2), delta=1e-6 * rr ** 2)


@slow
class FluxAndTorqueTest(unittest.TestCase):
    """No-load flux against the analytic air-gap field; loaded torque against the flux; cogging."""

    @classmethod
    def setUpClass(cls):
        from emachine.pipeline.sweep import sweep
        cls.spec, cls.values, _, cls.d, request = reference()
        cls.p = request.parameters["rfm"]
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda name, ni: sweep(request.parameters, 6, os.path.join(tmp, name), ampere_turns_peak=ni,
                                         core_field=False, geometry="rfm.section2d")
            cls.no_load = run("no_load", 0.0)
            cls.loaded = run("loaded", cls.d["ampere_turns_peak"])
        # the sweep covers half an electrical period from the d axis: position 0 is the flux peak
        cls.psi = float(cls.no_load["flux_per_turn_Wb"][0])

    def test_t41_3_flux_is_peak_at_d_axis(self):
        flux = self.no_load["flux_per_turn_Wb"]
        self.assertGreater(self.psi, 0)
        self.assertLessEqual(max(abs(flux)), self.psi * 1.001)

    def test_t41_3_torque_matches_flux(self):
        """Linear iron, current on the q axis: T = 3/2 p psi NI (within 2 %)."""
        expected = 1.5 * self.d["pole_pairs"] * self.psi * self.d["ampere_turns_peak"]
        self.assertAlmostEqual(float(self.loaded["torque_Nm"].mean()) / expected, 1.0, delta=0.02)

    def test_t41_3_flux_matches_analytic_air_gap_field(self):
        """Fundamental of the magnet field (Carter factor, no slot leakage) times the winding factor:
        within 20 % (open slots: the analytic value is about 17 % high)."""
        from emachine.machines.rfm.pmsm import RadialFluxPMSM
        p, mat = self.p, self.spec["materials"]["magnet"]
        layout = RadialFluxPMSM().layout(self.spec, self.values)
        from emachine.machines.winding_layout import winding_factor
        g, hm, mu = p["air_gap"], p["magnet_thickness"], mat["mu_r"]
        effective = g + hm / mu
        x = p["slot_width"] / (2 * effective)
        gamma = 4 / math.pi * (x * math.atan(x) - math.log(math.sqrt(1 + x * x)))
        pitch = 2 * math.pi * p["bore_radius"] / p["slots"]
        carter = pitch / (pitch - gamma * effective)
        b_gap = mat["remanence_T"] * (hm / mu) / (hm / mu + carter * g)
        b_1 = 4 / math.pi * b_gap * math.sin(p["magnet_arc_ratio"] * math.pi / 2)
        pole_flux = 2 * b_1 * (p["bore_radius"] - g / 2) * p["stack_length"] * 1e-6 / p["pole_pairs"]
        analytic = self.d["coils_per_phase"] * winding_factor(layout) * pole_flux
        self.assertAlmostEqual(self.psi / analytic, 1.0, delta=0.20)

    def test_t41_3_cogging_is_small(self):
        """12 slots, 10 poles: high cogging order, small cogging (under 5 % of the rated torque)."""
        ripple = float(self.no_load["torque_Nm"].max() - self.no_load["torque_Nm"].min())
        self.assertLess(ripple, 0.05 * float(self.loaded["torque_Nm"].mean()))


@slow
class MapTest(unittest.TestCase):
    def test_t41_4_map_runs_within_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "map")
            result = subprocess.run([sys.executable, "-m", "emachine", "map", "--spec", SPEC, "--design", DESIGN,
                                     "--out", out, "--jobs", "6", "--levels", "3", "--speeds", "21",
                                     "--torques", "21"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            with open(os.path.join(out, "summary.json")) as f:
                summary = json.load(f)
            with open(os.path.join(out, "efficiency_map.csv")) as f:
                rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]
        with open(SPEC) as f:
            limits = json.load(f)["limits"]
        drive = [r for r in rows if r["within_drive_limits"] == 1]
        self.assertTrue(drive)
        for r in drive:
            self.assertLessEqual(r["bus_voltage_needed_V"], limits["bus_voltage_V"][1] * (1 + 1e-6))
            self.assertLessEqual(r["peak_current_A"], limits["max_current_A"] * (1 + 1e-6))
        for r in rows:
            if r["continuous"] == 1 and r["torque_Nm"] > 0:
                self.assertLessEqual(r["current_density_A_mm2"], limits["max_current_density_A_mm2"] * (1 + 1e-6))
            self.assertLessEqual(r["efficiency"], 1.0)
        self.assertGreater(summary["standstill_peak_torque_Nm"], summary["standstill_continuous_torque_Nm"])
        self.assertGreater(summary["best"]["efficiency"], 0.5)


if __name__ == "__main__":
    unittest.main()
