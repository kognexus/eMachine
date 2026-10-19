# T62: Design principles from the literature: parameter ranges and ripple methods

Status: done
Depends on: T58

## Scope

Literature notes (`multi-topology-analysis/literature/*.md`, from the Zotero collection
Robotics/Actuators) condensed into `docs/design_principles.md`: per topology the variable ranges
used by the study (pole arcs, barrier ratios, Di/Do, magnet arcs, slot openings), the slot/pole
combinations offered, the ripple methods modelled (skew, magnet arc, Halbach, notches, slot opening,
asymmetric barriers, SRM pole arcs and current profiling), and which ripple the control removes.

## Acceptance criteria

- [x] Every variable range of the study cites the rule or paper it comes from (docs/design_principles.md, and
      `sources` of every topology class, printed in the report).
- [x] Ripple methods split into design-stage (modelled) and control-stage (stated).

## Result

2026-10-18. Four literature agents read the 72 items of the Zotero collection Robotics/Actuators (full texts
from the local Zotero storage where the index was cut off; read only): `multi-topology-analysis/literature/`
`srm.md`, `synrm_ipm.md`, `afpm_tfm.md`, `ripple_methods.md`. Gaps: the library has no dedicated papers on PM
cogging, skew or Halbach arrays (textbook rules marked [GK]); semantic search was not available (chromadb
missing); QP6RDFUS, WQDSQ9U9, 9ZIXLFZN, ZHMWTD9G have no PDF. Condensed into `docs/design_principles.md`.
