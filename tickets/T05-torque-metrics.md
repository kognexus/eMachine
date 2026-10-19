# T05: Torque metrics for one and three phases

Status: done
Depends on: T01

## Why

The field solution covers one phase. A three-phase transverse flux machine is three such phases
on one shaft, shifted by 120 electrical degrees. Average torque and ripple of the whole machine
must be derived from the single-phase torque waveform.

## Scope

`tfm/torque.py`:

- Input: the torque of one phase sampled at N equally spaced rotor positions over half an
  electrical period, with sinusoidal current. Under that drive the phase torque repeats every
  half period.
- `machine_torque(phase_torque, phases)`: total torque waveform. For three phases the waveform
  is added to copies shifted by one third and two thirds of the half period.
- `metrics(waveform)`: mean, minimum, maximum, peak-to-peak and ripple = peak-to-peak / mean.
- Assumption recorded here: phases are magnetically independent (axially stacked).

## Acceptance criteria

- [x] Three phases need N to be a multiple of 3. Other values raise an error.
- [x] A pure sin^2 phase torque gives a constant three-phase torque equal to 1.5 times its peak.
- [x] Harmonics that are not multiples of three cancel in the three-phase sum.
- [x] Ripple is defined for zero or negative mean torque without dividing by zero.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T05-1 | Phase torque = sin^2, N = 12, 1 phase | Mean 0.5, ripple 2.0 |
| T05-2 | Same, 3 phases | Constant 1.5, ripple below 1e-12 |
| T05-3 | sin^2 plus a cogging term with one cycle per half period, 3 phases | Cogging cancels, total constant |
| T05-4 | sin^2 plus a term with three cycles per half period, 3 phases | Term survives with three times its amplitude |
| T05-5 | N = 8, 3 phases | Error |
| T05-6 | Mean torque zero | Ripple reported as infinity, no exception |

## Result

Completed 2026-10-13.

- `tfm/torque.py`: `machine_torque`, `metrics`.
- Tests in `tests/test_t05_torque.py`: T05-1 to T05-6 pass, plus a test that the input array is not modified.
- T05-3 and T05-4 confirm the expected behaviour of a three-phase machine: cogging with one cycle
  per half electrical period cancels completely, and only harmonics that are multiples of three survive.
