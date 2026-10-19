# T43: Naming standard and machine identity (flux path, principle, rotor layout)

Status: done
Depends on: T42

## Why

The user (2026-10-16) asked for one standard set of names and a machine matrix. Today a machine is
`family/topology` and the list mixes two kinds of choice: `ipm` and `pmasynrm` are rotor layouts
of the PMSM and SynRM principles, not principles of their own. Option names also differ between
machines (`stator_type` codes `u`, `cp`, `tr`; `configuration` `inrunner`; `rotor_type`
`flux_concentrating`; `sides` 1 or 2). The standard is written down in `docs/naming.md`.

## Scope

1. Spec keys `machine.flux_path`, `machine.principle`, `machine.rotor`, `machine.stator`,
   `machine.rotor_placement`, `machine.arrangement` (AFM), as in `docs/naming.md`.
2. Registry keys `<flux_path>/<principle>`: `rfm/ipm` becomes `rfm/pmsm` with rotor `interior`,
   `rfm/pmasynrm` becomes `rfm/synrm` with rotor `flux_barrier_pm`. Each machine lists its rotor
   layouts (`rotors`) and rejects others with a message naming the allowed ones.
3. `Machine` attributes `flux_path`, `principle`, `rotors` instead of `family`, `topology`
   (interfaces, pipeline, CLI, reports, plots: about 75 places in 30 files).
4. Aliases: every old key and value in the table of `docs/naming.md` is translated when a spec
   loads; the normalised spec (saved as `spec.json` of a run) uses the new names.
5. Display label `<FLUX PATH>-<PRINCIPLE> (<rotor>)` in reports, `describe` and plot titles.
6. Backlog tickets B06 and B08 renamed to the new machine names; README, `docs/architecture.md`,
   `docs/extending.md` updated.

## Acceptance criteria

- [x] Every spec in `specs/` and `spec_example.json`, and every `spec.json` under `runs/`, loads
      and gives the same machine as before (old names).
- [x] The same specs written with the new names load to the identical normalised spec.
- [x] Characterization tests unchanged (golden master: same numbers for the TFM reference).
- [x] An unknown or unsupported rotor layout fails with the list of allowed ones.
- [x] No `family` or `topology` left in `emachine/` outside the alias table (test greps for it).
- [x] Full slow suite passes.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T43-1 | Load each old spec; translate it to new names and load again | identical normalised specs, machine keys `tfm/pmsm`, `rfm/pmsm` |
| T43-2 | `{"flux_path": "rfm", "topology": "ipm"}` (old key) and `{"flux_path": "rfm", "principle": "pmsm", "rotor": "interior"}` | same machine `rfm/pmsm`, rotor `interior` |
| T43-3 | `rfm/srm` with rotor `surface` | SpecError naming `salient` |
| T43-4 | TFM `stator_type` `cp`, `rotor_type` `flux_concentrating`, `configuration` `outrunner` | `stator` `claw_pole`, `rotor` `spoke`, `rotor_placement` `outer` |
| T43-5 | Optimization dry run of the TFM reference with old and new names | identical `all_designs.csv` |
| T43-6 | Source scan | `family` / `topology` only in the alias table of `emachine/spec` |
| T43-7 | Label | "TFM-PMSM (halbach)", "RFM-PMSM (surface)" in `describe` and reports |

## Result

2026-10-16. `emachine/spec/names.py` holds every old name: `standard_machine`/`standard_spec`
translate a user's file, `legacy_spec` writes a loaded spec back in the old names and `cache_view`
gives the view the cache keys hash, so results cached before the standard are found
(`evaluate.keyed_spec`, `effmap._signature`). `SpecError` moved to `spec/errors.py`. The loader
uses `machine.flux_path`, `principle`, `rotor` (checked against the machine's `rotors`),
`rotor_placement`; the TFM options are `stator` and `rotor` with standard names and
`machines/tfm/options.py` translates them to the codes of the geometry parameter files (unchanged,
so old parameter files, goldens and run folders stay valid). `Machine` has `flux_path`,
`principle`, `rotors`, `rotor_status`; `rfm/ipm` and `rfm/pmasynrm` are now rotor layouts.
`describe.label` gives "RFM-PMSM (surface)"; reports, `compare` and `list` use it. The spec files in
`specs/` and the root examples were rewritten in the new names (each loads to the identical spec).

Tests (`tests/unit/spec/test_names.py`, 8): old and new names give identical specs for every file
in `specs/`, the examples and every `runs/*/spec.json`; cache keys and map signatures equal to the
values recorded before the change for 28 of 29 cases (all specs and runs, and every old machine
except `tfm/srm`, whose old spec carried the TFM `rotor_type` "halbach"; it cannot be solved, so no
cache of it exists); a dry-run optimization with old and with new names writes the same table; no
old name left outside `spec/names.py` (AST scan). Characterization tests unchanged (the spec
comparison goes through `legacy_spec`). Tests that asserted old keys were updated.

Full slow suite after T43 to T47: 366 tests pass (1 skipped) in 1374 s.
