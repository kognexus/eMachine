# T45: The machine matrix

Status: done
Depends on: T43, T44

## Why

The user (2026-10-16) wants to see the machines as a matrix: flux path (TFM, RFM, AFM, RAFM)
against torque principle (PMSM, SynRM, SRM, Vernier), with the rotor layouts of each cell. Today
`python -m emachine list` prints a flat list, and an empty combination cannot be told apart from
one that is not wanted.

## Scope

- Every cell of the matrix has a status: `solvable` (geometry and solver), `specified` (variables,
  checks, estimates; `NotSolvableYet` with its ticket), `planned` (a backlog ticket, nothing
  registered), `not meaningful` (with the reason, e.g. a ring winding with salient-pole switching
  is the TFM SRM, a separate cell).
- The cells that are not registered are listed in one table in the code
  (`emachine/machines/matrix.py`: flux path, principle, status, ticket, reason).
- `python -m emachine list` prints the matrix, then the rotor layouts and windings of each
  registered machine; `--flat` gives the old list.
- `docs/machines.md` holds the same matrix; a test checks that it agrees with the registry.

## Acceptance criteria

- [x] All 16 cells have a status; every `specified` or `planned` cell names a ticket.
- [x] `list` shows the matrix in a terminal of 100 columns.
- [x] The documentation table equals the output of the code.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T45-1 | Matrix from the registry and `matrix.py` | 4 x 4 cells, no cell without status; `rfm/pmsm`, `tfm/pmsm` solvable |
| T45-2 | Register a fake machine `afm/vernier` in a test | its cell turns `specified` |
| T45-3 | `docs/machines.md` | same cells and statuses as T45-1 |
| T45-4 | `list` output | fits 100 columns; `--flat` gives one machine per line |

## Result

2026-10-16. `emachine/machines/matrix.py` (cells of the 4 x 4 matrix, the unregistered ones with
their ticket or reason), `python -m emachine list` (matrix, then the rotor layouts of every
machine with the ticket of those that cannot be solved yet; `--flat`, `--markdown`),
`docs/machines.md` written by `list --markdown`. Status today: TFM-PMSM and RFM-PMSM solvable;
TFM-SRM, RFM-SynRM, RFM-SRM, AFM-PMSM, AFM-SRM specified; Vernier (B15), AFM-SynRM (new backlog
ticket B16) and RAFM (B14) planned; TFM-SynRM not meaningful (each TFM phase has a pulsating field
of its own; the reluctance TFM is the SRM).

Tests (`tests/unit/machines/test_matrix.py`, 4): 16 cells, every planned or specified cell has a
ticket file; a fake machine fills its cell; `docs/machines.md` equals the generated text; the
output fits 94 columns.

Full slow suite after T43 to T47: 366 tests pass (1 skipped) in 1374 s.
