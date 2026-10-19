"""
After the study (T65, T64): ParaView export and pictures of every verified pick, then the report.

    python -m emachine.analysis.topology_postprocess --config <study folder>/study.json [--only KEY ...]
        [--skip-export] [--skip-views]

Exports go to <study>/paraview/<topology>_<pick>/ (pictures in views/); picks that are the same design are
exported once. The pictures are rendered by ParaView's pvpython (PVPYTHON or the ParaView 6.2 app).
"""

import argparse
import concurrent.futures
import json
import os
import subprocess

from .topology_export import export
from .topology_report import build
from .topology_study import load_config

PVPYTHON = os.environ.get("PVPYTHON", "/Applications/ParaView-6.2.0.app/Contents/bin/pvpython")
VIEWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "io", "topology_views.py")


def unique_picks(rundir):
    out, seen = [], set()
    for name in ("optimal", "highest_torque", "closest"):
        path = os.path.join(rundir, "verify", f"{name}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            r = json.load(f)
        if not r.get("analysed"):
            continue
        tag = json.dumps(r["values"], sort_keys=True)
        if tag in seen:
            continue
        seen.add(tag)
        out.append(name)
    return out


def export_one(args):
    key, name, cfg_path, out = args
    cfg = load_config(cfg_path)
    target = os.path.join(out, "paraview", f"{key}_{name}")
    try:
        export(os.path.join(out, "runs", key), name, target, cfg, log=lambda *_: None)
    except Exception as error:            # one design must not stop the others
        print(f"export of {key} {name} failed: {error}", flush=True)
    return key, name, target


def render(target, title):
    subprocess.run([PVPYTHON, "--force-offscreen-rendering", VIEWS, "--export", target, "--out", os.path.join(target, "views"),
                    "--title", title], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--skip-export", action="store_true")
    ap.add_argument("--skip-views", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    out = args.out or cfg["_dir"]
    keys = args.only or cfg["topologies"]
    jobs = [(key, name, args.config, out) for key in keys for name in unique_picks(os.path.join(out, "runs", key))]
    if not args.skip_export:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for key, name, target in pool.map(export_one, jobs):
                print(f"exported {key} {name}", flush=True)
    if not args.skip_views:
        for key, name, _, _ in jobs:
            target = os.path.join(out, "paraview", f"{key}_{name}")
            if os.path.isfile(os.path.join(target, "summary.json")):
                render(target, f"{key} ({name.replace('_', ' ')})")
                print(f"views {key} {name}", flush=True)
    build(cfg, out)


if __name__ == "__main__":
    main()
