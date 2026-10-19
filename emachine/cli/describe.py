"""Short descriptions of the machine of a specification, for reports (names: docs/naming.md)."""

from emachine.core import registry


def machine_of(spec):
    m = spec["machine"]
    return registry.create("machine", f"{m['flux_path']}/{m['principle']}")


def label(spec):
    """The standard label of the machine, e.g. "TFM-PMSM (halbach)", "RFM-PMSM (surface)"."""
    m = spec["machine"]
    text = f"{m['flux_path'].upper()}-{m['principle'].upper().replace('SYNRM', 'SynRM')}"
    return f"{text} ({m['rotor']})" if m.get("rotor") else text


def winding_text(spec, values):
    """The winding of a design in one line, e.g. "FSCW, q = 0.4, 2 layers, pitch 1 slot, k_w1 = 0.933"."""
    from emachine.machines import winding_layout
    description = machine_of(spec).winding_description(spec, values)
    if description is None:
        return ""
    text = winding_layout.text(description)
    return text if description["label"] == "ring" or description["k_w1"] is not None else text + " (not balanced)"


def option_rows(spec):
    """(label, value) rows of the machine's own options (those it adds to the section `machine`)."""
    m = spec["machine"]
    return [(key.replace("_", " ").capitalize(), m[key]) for key in machine_of(spec).options() if key in m]


def summary(spec):
    """One line: label, rotor placement and options, phases."""
    m = spec["machine"]
    options = ", ".join(f"{name.lower()} {value}" for name, value in option_rows(spec))
    return f"{label(spec)}, {m['rotor_placement']} rotor, {options}, {m['phases']} phase(s)"
