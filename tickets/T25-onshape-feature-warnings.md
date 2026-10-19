# T25: Onshape warnings in the v2 features and the UI32 studio

Status: done
Depends on: T22, T24

## Why

The user (2026-10-15) sent the warnings Onshape shows for the document:

| Studio | Warning |
|---|---|
| TFM stator v2 | 143:14 Nonconforming feature function 'tfmStator': precondition analysis failed; 177:17 Unexpected operator: GREATER |
| TFM rotor v2 | 182:14 Nonconforming feature function 'tfmInrunnerRotor': precondition analysis failed; 214:13 Unexpected operator: GREATER |
| TFM UI32 design | 190:7 'tfmStator': Missing export; 923:7 'tfmInrunnerRotor': Missing export |

Causes:

- `if (definition.phases > 1)` around "Phase spacing" in both preconditions (added in T22). It
  compiles, but Onshape's precondition analysis accepts only comparisons such as `==` and `!=` of
  parameters, so the analysis of the whole dialog fails. The note of 2026-10-14 that "numeric
  visibility conditions compile fine" was true but not enough.
- `tfm_ui32_design.fs` carried the two features as unexported `defineFeature` copies.

## Changes

- "Phase spacing" is always shown (rotary stator; rotor), without the condition. It is ignored
  for one phase.
- `tfm_ui32_build.py` writes `tfm_ui32_design.fs` from `tfm_stator.fs` and `tfm_rotor.fs`. The two
  features become plain functions (`tfmStator`, `tfmInrunnerRotor`) that fill missing fields from
  the feature defaults, so the studio exports only "TFM UI32 machine". Exporting the copies instead
  would list "TFM stator" and "TFM rotor" twice in the document.

## Acceptance criteria

- [x] No `.fs` file has a numeric comparison in a precondition, and every `defineFeature` is exported.
- [x] `tfm_ui32_design.fs` is exactly the output of `tfm_ui32_build.py`.
- [x] The three studios on Onshape compile, and the warnings above are gone (to be confirmed by the
      user in the Onshape interface; the MCP tools return compile errors only).
- [x] The UI32 machine still builds the same bodies.

## Test cases

| ID | Test | Expected |
|---|---|---|
| T25-1 | Precondition lint of every `.fs` file | No `<`, `>`, `<=`, `>=` in a precondition; every `defineFeature` exported |
| T25-2 | `tfm_ui32_build.py --check` | Up to date |
| T25-3 | Onshape: compile the three files (`put_featurescript`) | No errors |

## Result

2026-10-15:

- `tests/test_t25_onshape_warnings.py`: T25-1 and T25-2 pass. Run on the files before the fix, the
  lint finds exactly the four reported problems (`phases > 1` in the stator and in the rotor
  precondition, twice in the UI32 copy; `tfmStator` and `tfmInrunnerRotor` not exported in UI32).
- T25-3: `put_featurescript` wrote `tfm_stator.fs` to "TFM stator v2", `tfm_rotor.fs` to "TFM rotor v2"
  and `tfm_ui32_design.fs` to "TFM UI32 design"; all three compile without errors. The live rotor
  studio was read first and matched the local file apart from this fix.
- The fast suite passes (203 tests).

Open: the warning list in the Onshape interface (put_featurescript does not report warnings), and
a regeneration of the UI32 machine in its Part Studio, are to be checked by the user.

Closed 2026-10-19 by the user: the studios compile and the Onshape check is accounted for (`tests/tickets/test_t25_onshape_warnings.py` passes).
