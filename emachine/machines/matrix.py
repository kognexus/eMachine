"""
The machine matrix: flux path x torque principle (docs/naming.md), with the status of every cell.

    solvable        a registered machine with at least one rotor layout that has a geometry
    specified       a registered machine: variables, checks, estimates; geometry in its ticket
    planned         nothing registered yet; a backlog ticket
    not meaningful  the combination does not make a machine (reason given)

Registered machines get their status from the registry; the other cells are listed in UNREGISTERED.
`emachine list` prints the matrix, `list --markdown` writes it for docs/machines.md.
"""

from emachine.core import registry

FLUX_PATHS = ("tfm", "rfm", "afm", "rafm")
PRINCIPLES = ("pmsm", "synrm", "srm", "vernier")
NAMES = {"tfm": "TFM", "rfm": "RFM", "afm": "AFM", "rafm": "RAFM",
         "pmsm": "PMSM", "synrm": "SynRM", "srm": "SRM", "vernier": "Vernier"}

#: cells without a registered machine: (flux path, principle) -> (status, ticket or reason)
UNREGISTERED = {
    ("tfm", "synrm"): ("not meaningful", "each TFM phase is a ring coil with a pulsating field of its own; there is "
                                         "no rotating field for a d-q anisotropic rotor. The reluctance TFM is tfm/srm"),
    ("tfm", "vernier"): ("planned", "B15"),
    ("rfm", "vernier"): ("planned", "B15"),
    ("afm", "synrm"): ("planned", "B16"),
    ("afm", "vernier"): ("planned", "B15"),
    ("rafm", "synrm"): ("planned", "B14"),
    ("rafm", "srm"): ("planned", "B14"),
    ("rafm", "vernier"): ("planned", "B14"),
}


class Cell:
    def __init__(self, flux_path, principle, status, tickets=(), reason="", rotors=()):
        self.flux_path, self.principle, self.status = flux_path, principle, status
        self.tickets, self.reason, self.rotors = tuple(tickets), reason, tuple(rotors)

    @property
    def key(self):
        return f"{self.flux_path}/{self.principle}"

    def short(self):
        """Text of the cell in a table: status and ticket."""
        if self.status in ("solvable", "specified"):
            open_tickets = [t for _, solvable, t in self.rotors if not solvable]
            text = self.status + (f" ({', '.join(open_tickets)})" if self.status == "specified" and open_tickets else "")
            return text
        if self.status == "planned":
            return f"planned ({', '.join(self.tickets)})"
        return "not meaningful"


def cells():
    """All cells of the matrix, flux path by flux path, as Cell objects."""
    known = set(registry.names("machine"))
    out = []
    for flux_path in FLUX_PATHS:
        for principle in PRINCIPLES:
            key = f"{flux_path}/{principle}"
            if key in known:
                cls = registry.get("machine", key)
                rotors = [(rotor, *cls.rotor_status(rotor)) for rotor in cls.rotors]
                status = "solvable" if any(solvable for _, solvable, _ in rotors) else "specified"
                out.append(Cell(flux_path, principle, status, sorted({t for _, s, t in rotors if not s}), rotors=rotors))
            else:
                status, text = UNREGISTERED.get((flux_path, principle), ("planned", "?"))
                if status == "planned":
                    out.append(Cell(flux_path, principle, status, [text]))
                else:
                    out.append(Cell(flux_path, principle, status, reason=text))
    return out


def table(width=22):
    """The matrix as plain text, one row per flux path."""
    by_key = {cell.key: cell for cell in cells()}
    lines = [(" " * 6 + "".join(f"{NAMES[p]:<{width}}" for p in PRINCIPLES)).rstrip()]
    for flux_path in FLUX_PATHS:
        lines.append(f"{NAMES[flux_path]:<6}" + "".join(f"{by_key[f'{flux_path}/{p}'].short():<{width}}"
                                                         for p in PRINCIPLES).rstrip())
    return "\n".join(lines)


def markdown():
    """The matrix and the rotor layouts as Markdown (docs/machines.md)."""
    all_cells = cells()
    by_key = {cell.key: cell for cell in all_cells}
    out = ["# Machine matrix", "",
           "Flux path x torque principle (names: [naming.md](naming.md)). Written by "
           "`emachine list --markdown`; a test checks that it agrees with the code.", "",
           "| | " + " | ".join(NAMES[p] for p in PRINCIPLES) + " |", "|---|" + "---|" * len(PRINCIPLES)]
    for flux_path in FLUX_PATHS:
        out.append(f"| **{NAMES[flux_path]}** | " + " | ".join(by_key[f"{flux_path}/{p}"].short() for p in PRINCIPLES) + " |")
    out += ["", "- **solvable**: at least one rotor layout has a geometry and is analysed with the field solver.",
            "- **specified**: the machine is registered (variables, checks, winding, thermal estimates); "
            "the ticket builds its geometry.",
            "- **planned**: nothing registered yet; the backlog ticket.",
            "- **not meaningful**: the combination does not make a machine (reason below).", "",
            "## Rotor layouts of the registered machines", "",
            "| Machine | Rotor layout | Status |", "|---|---|---|"]
    for cell in all_cells:
        for rotor, solvable, ticket in cell.rotors:
            out.append(f"| `{cell.key}` | `{rotor}` | {'solvable' if solvable else 'specified'} ({ticket}) |")
    reasons = [cell for cell in all_cells if cell.status == "not meaningful"]
    if reasons:
        out += ["", "## Not meaningful", ""]
        out += [f"- `{cell.key}`: {cell.reason}." for cell in reasons]
    return "\n".join(out) + "\n"
