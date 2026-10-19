# T66: Reference model of the ILM-E85x23 under the same rules

Status: done
Depends on: T58, T59

## Scope

An inner-rotor surface PM machine, 10 pole pairs, fractional-slot concentrated winding, 85/52 mm,
built with the section kit at the ILM-E's 25.2 mm rotor length, compared with the datasheet (kT,
resistance, inductance, peak torque); then the same machine at 30 mm and 1000 rpm under the study's
rules, so every topology is also compared with a like-for-like ILM-E.

## Acceptance criteria

- [x] kT within 10 % of 0.247 Nm/A with a plausible magnet and slot geometry; differences explained.
      (Amended, see the result: kT is set by the winding rule, so the motor constant k_M, which does not
      depend on the winding, is the test: within 1 %.)

## Result

2026-10-18. `python -m emachine.analysis.topology_study --config multi-topology-analysis/study.json --reference`,
files in `multi-topology-analysis/reference_model/`. Geometry assumed (the ILM-E's slot count and
lamination are not published): 24 slots / 20 poles FSCW, stator bore 69 mm, 0.5 mm gap, 2.5 mm NdFeB
(1.25 T) at 0.85 pole arc, tooth body 0.5 of the slot pitch, M270-35A; verified mesh, 36 positions.

kT is fixed by the winding, not by the machine: an ideal sinusoidal machine wound for a no-load speed
n0 at the DC link V has kT = (sqrt 3 / 2) V / omega0 = 0.247 Nm/A at 48 V and 1606 rpm, exactly the
datasheet value. The study winds for the voltage at rated current (with resistance, inductance and a
3 % margin), which gives fewer turns (kT 0.209 at 1606 rpm). The quantity that tests the model is
the motor constant:

| | Datasheet ILM-E85x23 | Model, 25.2 mm stack |
|---|---|---|
| Motor constant k_M at 20 C | 0.503 Nm/sqrt W | 0.507 Nm/sqrt W (+0.8 %) |
| Torque at 10.5 A, wound to kT 0.247 | 2.58 Nm | 2.59 Nm |
| Copper loss at that torque, 20 C | 26.7 W | 26.1 W |
| Peak torque at 42 A | 8.31 Nm (kT 20 % below linear) | 8.73 Nm at kT 0.209, nearly linear (0.6 % below) |
| Cogging, peak to peak | not given | 0.22 Nm (no skew) |

The model saturates much less at 42 A than the ILM-E (whose peak torque is defined at 20 % below
linear): its iron is wider than the real machine's probably is, or the real lamination saturates
earlier. Peak torques of the study are therefore optimistic by up to about 20 % for machines of this
kind; ratios between topologies are less affected. Under the study's rules (30 mm, 1000 rpm) the same
machine gives 3.27 Nm at 10.5 A, 12.8 Nm at 42 A, 87.3 % efficiency, k_M 0.562 Nm/sqrt W; this is the
"ILM-E model" row of the report.

Status: done.
