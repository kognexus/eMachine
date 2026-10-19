# T65: ParaView export and views of the optimal and highest-torque designs

Status: done
Depends on: T63

## Scope

For every topology's optimal design and the highest-torque designs: one electrical period at the
rated point and the peak point, `.pvd` time series of the section (radial: extruded to the stack;
axial: slices wrapped onto their cylinders), flux density, vector potential (flux lines), current
density, materials; pictures rendered headless with pvpython 6.2.

## Acceptance criteria

- [x] Every export opens in ParaView 6.2; pictures looked at (radial: full section, close-up at the gap, peak
      current; axial: slices wrapped onto their cylinders and the middle slice unrolled; raxial: the T56 export).

## Result

2026-10-18. `emachine/analysis/topology_export.py` (rated sweep and no-load sweep as .pvd series, the field at the
peak current solved again and kept; axial: wrapped slices and the unrolled middle slice), `emachine/io/topology_views.py`
(pvpython, headless: |B| with flux lines, materials, close-ups), `emachine/analysis/topology_postprocess.py`.
Exports in `multi-topology-analysis/paraview/<topology>_<pick>/` (pictures in `views/`). The raxial machine's
quasi-3D model writes no 2D field files: its pick was exported with the T56 export (`t56_export/`, views from
`emachine/io/paraview_views.py`).
