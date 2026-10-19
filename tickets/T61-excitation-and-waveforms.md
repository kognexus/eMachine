# T61: Excitation per principle (dq/MTPA, SRM flux maps and dynamics), phase voltage analysis

Status: done
Depends on: T58 to T60

## Scope

- Synchronous machines (PM, IPM, SynRM, PMaSynRM, vernier): Park transform of the three phase
  fluxes at a rotor position gives psi_d, psi_q; torque 3/2 p (psi_d i_q - psi_q i_d); maximum torque
  per ampere angle from a few current angles; voltage from psi_d, psi_q and the resistance.
- Switched reluctance: flux linkage psi(theta, i) of one phase over a rotor pole pitch at several
  currents; co-energy torque; dynamic simulation of a phase with the asymmetric half bridge on the
  bus (current chopping, turn-on and turn-off angles optimized for torque at the rms current).
- Waveforms of the rated point, as Motor-CAD shows them: phase voltages and phase flux linkages over
  an electrical period (reconstructed from a 1/2 period sweep by the half-wave symmetry), back-EMF at
  no load, line voltage against the DC link limit.
- Skew: continuous and step skew from the harmonics of torque and flux (factor
  sin(n theta_sk / 2) / (n theta_sk / 2)); step skew verified by slices with FE for the finalists.

## Acceptance criteria

- [x] dq torque within 3 % of the Arkkio mean torque for an SPM design (24/20 SPM: 3/2 p Phi N I = 3.31 Nm against
      Arkkio 3.29 Nm). For FSCW reluctance machines the fundamental flux torque at one position can be far off
      (12/8 SynRM: 0.25 against 0.97 Nm), so the searches use Arkkio's torque averaged over two positions 30 el.
      deg apart (the 6th harmonic cancels).
- [x] SRM simulation of a linear test case: electrical and mechanical work per stroke equal within 1 % (T61-2).
- [x] Phase voltage figure of every optimal design (report/figures/*_phase_voltage.svg).

## Test cases

T61-1 Park transform of ideal sinusoidal fluxes. T61-2 SRM linear case. T61-3 skew factor removes a
harmonic whose period equals the skew angle.

## Result

2026-10-18. `emachine/physics/drive.py` and `emachine/pipeline/drive.py`. Synchronous machines: no load at two
positions (magnet flux, phase sequence: the vernier field turns against its rotor), current angle of the
most torque (6 angles + refinement; 3 near i_d = 0 for surface magnets), torque and flux at three
ampere-turn levels, the most turns the bus allows (3 % kept for harmonics; fewer if the efficiency would
be below 80 %, else those of the best efficiency), winding (paths, AWG 12 to 32, strands, fill 0.5 to 0.7),
rated sweep over half a period (12 positions; 36 when verified), peak current with the current angle
advanced (MTPA). Solutions at one rotor angle share their mesh. SRM: phase A alone, 9 positions x 6
ampere-turn levels, a dynamic model (asymmetric half bridge, soft chopping, adaptive step: 1.5 % of the
aligned flux per step), firing angles and chopping current searched for the most torque at the rms
current, the turns among 9 candidates; peak torque with ideal flat-top 42 A currents. Bugs found: one-step
offset between current and flux in the SRM record; too coarse steps at low speed (current overshoot, the
search returned 0 A).
Tests: `tests/tickets/test_t61_excitation.py`, `tests/tickets/test_t58_drive.py`.

Skew check (T61-3 with the field solver, `python -m emachine.analysis.topology_study --skew-check rfm_spm_in`):
the inner-rotor SPM pick (skew 7.5 el. deg) solved as 5 rotor slices shifted over the skew angle (18
positions, optimization mesh): mean torque 3.195 Nm, the harmonic skew model 3.196 Nm; ripple 5.0 %
against the model's 5.3 % (5.5 % unskewed). The harmonic model used in the optimization is confirmed.
Phase voltage figures: `multi-topology-analysis/report/figures/*_phase_voltage.svg` (every verified pick).

