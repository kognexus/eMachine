"""
Prints the values of a design under the field names of the Onshape dialogs, so that they can be
typed in.

Any machine, for the feature "eMachine" (emachine/cad/featurescript/emachine_design.fs):

    emachine onshape --spec examples/rfm_spm_12s10p.json --design examples/rfm_spm_12s10p_design.json
    emachine onshape --run runs/opt1 --pick best_compromise

A TFM parameter file, for the two features "TFM stator" and "TFM rotor":

    emachine onshape --params runs/opt1/designs/best_compromise.json

--markdown writes the sheet as a Markdown table instead of plain text.
"""

import argparse
import json
import os
import sys

from emachine.cad import sheet as emachine_sheet
from emachine.machines.tfm.cad import sheet as onshape
from emachine.pipeline import design_space
from emachine.spec import load_spec
from emachine.spec.names import standard_values


def emachine_main(args):
    """The eMachine dialog values of a design (--spec and --design, or --run and --pick)."""
    spec_file = args.spec or (args.run and os.path.join(args.run, "spec.json"))
    design_file = args.design or (args.run and os.path.join(args.run, "designs", args.pick + ".json"))
    for path in (spec_file, design_file):
        if not path or not os.path.isfile(path):
            sys.exit(f"No file {path}. Give --spec and --design, or --run (and --pick).")
    spec = load_spec(spec_file)
    with open(design_file) as f:
        raw = json.load(f)
    raw = standard_values(spec, raw.get("design", raw))
    values = design_space.clip(spec, {v["name"]: raw[v["name"]] for v in design_space.variables(spec)})
    hybrid = spec["machine"]["flux_path"] == "rafm"          # the "Raxial machine" of hybrid_design.fs (T54)
    rows = emachine_sheet.raxial_rows(spec, values) if hybrid else emachine_sheet.emachine_rows(spec, values)
    heading = f"Feature \"{'Raxial machine' if hybrid else 'eMachine'}\" for {design_file}"
    print(emachine_sheet.to_markdown(rows, heading) if args.markdown else emachine_sheet.to_text(rows, heading))
    checks = emachine_sheet.raxial_checks(spec, values) if hybrid else emachine_sheet.checks(spec, values)
    if checks:
        print("" if args.markdown else "\nTo check on the finished model:")
        print(emachine_sheet.to_markdown(checks, "Checks") if args.markdown else
              "\n".join(f"  {field}: {text}" for field, text in checks))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", help="TFM parameter file with stator and rotor sections (TFM stator and rotor features)")
    ap.add_argument("--spec", help="specification of the design (eMachine feature)")
    ap.add_argument("--design", help="design values or a pick file of a run (eMachine feature)")
    ap.add_argument("--run", help="optimization run folder (eMachine feature)")
    ap.add_argument("--pick", default="best_compromise", help="pick of the run (default best_compromise)")
    ap.add_argument("--markdown", action="store_true", help="Markdown tables instead of plain text")
    args = ap.parse_args(argv)
    if not args.params:
        return emachine_main(args)
    if not os.path.isfile(args.params):
        sys.exit(f"No file {args.params}. A finished optimization writes its picks to <run folder>/designs/, "
                 "for example runs/types24/ui/designs/best_compromise.json.")
    with open(args.params) as f:
        parameters = json.load(f)
    for section in ("stator", "rotor"):
        if section not in parameters:
            sys.exit(f"{args.params}: no '{section}' section.")
    sections = onshape.sheet(parameters)
    heading = f"Onshape parameters for {args.params}"
    print(onshape.to_markdown(sections, heading) if args.markdown else onshape.to_text(sections, heading))
    if onshape.flagged(sections):
        sys.exit(1)

