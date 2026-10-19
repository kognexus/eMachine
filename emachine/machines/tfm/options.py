"""
Options of the TFM in the specification section `machine`, next to the common keys. The spec uses
the standard names of docs/naming.md; the geometry parameter files (and the Gmsh and Onshape
builders) keep their short codes, translated here.
"""

from emachine.spec import SpecError
from emachine.spec.loader import number

#: stator layouts (machine.stator) -> code of the geometry parameter files
STATOR_CODES = {"u_core": "u", "ui_core": "ui", "c_core": "c", "e_core": "e", "z_core": "z",
                "claw_pole": "cp", "toothed_ring": "tr"}
#: rotor layouts (machine.rotor) -> code of the geometry parameter files. The TFM SRM (B12) has no
#: rotor geometry yet; its dimensions are those of a surface rotor of the same radial room.
ROTOR_CODES = {"halbach": "halbach", "surface": "surface", "spoke": "flux_concentrating", "axial_ring": "axial",
               "salient": "surface"}
#: rotor layouts of the TFM PMSM, the default first
ROTORS = ("halbach", "surface", "spoke", "axial_ring")

SUPPORTED_STATORS = ("u", "ui", "cp", "tr")         # codes that can be analysed
KNOWN_STATORS = ("u", "ui", "c", "cp", "e", "z", "tr")
ROTOR_TYPES = ("surface", "halbach", "flux_concentrating", "axial")

OPTIONS = {
    "stator": "ui_core",            # "u_core", "ui_core" (U-core with I-bridge), "claw_pole" or "toothed_ring"
                                    # (review paper Fig. 17); "c_core", "e_core", "z_core" as geometry only
    "phase_spacing_mm": 2.0,        # axial gap between neighbouring phases
    "pole_shift_el_deg": 0.0,       # extra offset of every second stator core, in electrical degrees.
                                    # 30 cancels the sixth torque harmonic of a three-phase machine.
                                    # The model then covers two pole pairs and takes twice as long.
    "ring_arched_valleys": False,   # toothed ring: arch from tooth to tooth instead of straight-cut teeth
    "ring_staggered_teeth": False,  # toothed ring: back-wall teeth one pole pitch after the front wall;
                                    # the rotor then has one magnet row per phase instead of two
    # T71 to T73 (gear TFM at low speed). All off by default: older specifications build the same machine.
    "halbach_segments": 2,          # Halbach rotor: magnet segments per pole (2: radial and tangential; 3, 4, ...)
    "rotor_magnet_slots": False,    # toothed ring with staggered teeth: the magnets sit in two pockets of the
                                    # rotor, one over each side wall, instead of one row across the coil slot;
                                    # variable magnet_overhang_mm sets how far each pocket reaches over the slot
    "rotor_skew_el_deg": 0.0,       # step skew of the rotor magnets inside each phase, electrical degrees
                                    # between the first and the last step
    "rotor_skew_steps": 1,          # axial steps of that skew (1: no skew)
    "ring_tooth_tips": False,       # toothed ring: each tooth carries a tip that reaches axially over the coil
                                    # slot (variables ring_tip_overhang_mm, ring_tip_height_mm); the coil sits
                                    # below the tips. With staggered teeth the tips of the two walls interleave.
}


def stator_code(machine):
    """Geometry code of the stator layout of a spec section `machine`."""
    return STATOR_CODES[machine["stator"]]


def rotor_code(machine):
    """Geometry code of the rotor layout of a spec section `machine`."""
    return ROTOR_CODES[machine["rotor"]]


def outer_rotor(machine):
    return machine["rotor_placement"] == "outer"


def validate(spec):
    machine = spec["machine"]
    if machine["stator"] not in STATOR_CODES:
        raise SpecError(f"'machine.stator' must be one of {tuple(STATOR_CODES)}, got {machine['stator']!r}.")
    if stator_code(machine) not in SUPPORTED_STATORS:
        supported = tuple(name for name, code in STATOR_CODES.items() if code in SUPPORTED_STATORS)
        raise SpecError(f"'machine.stator' = {machine['stator']!r} is not supported yet "
                        f"(see ticket B02). Supported: {supported}.")
    if machine["phases"] not in (1, 3):
        raise SpecError(f"'machine.phases' must be 1 or 3, got {machine['phases']!r}.")
    number(spec, "machine.phase_spacing_mm", low=0)
    number(spec, "machine.pole_shift_el_deg", low=-90.0, high=90.0)
    if machine["pole_shift_el_deg"] and stator_code(machine) == "cp":
        raise SpecError("'machine.pole_shift_el_deg' is not available for the claw-pole stator.")
    for key in ("ring_arched_valleys", "ring_staggered_teeth", "rotor_magnet_slots", "ring_tooth_tips"):
        if not isinstance(machine[key], bool):
            raise SpecError(f"'machine.{key}' must be true or false.")
        if machine[key] and stator_code(machine) != "tr":
            raise SpecError(f"'machine.{key}' applies to the toothed ring (stator 'toothed_ring') only.")
    number(spec, "machine.halbach_segments", low=2, high=8, integer=True)
    if machine["halbach_segments"] != 2 and rotor_code(machine) != "halbach":
        raise SpecError("'machine.halbach_segments' applies to the Halbach rotor only.")
    if machine["rotor_magnet_slots"]:
        if not machine["ring_staggered_teeth"]:
            raise SpecError("'machine.rotor_magnet_slots' needs the toothed ring with staggered teeth "
                            "('ring_staggered_teeth': true).")
        if rotor_code(machine) not in ("halbach", "surface"):
            raise SpecError("'machine.rotor_magnet_slots' applies to the Halbach and surface rotors.")
    number(spec, "machine.rotor_skew_el_deg", low=0.0, high=180.0)
    number(spec, "machine.rotor_skew_steps", low=1, high=8, integer=True)
    if machine["rotor_skew_el_deg"] and machine["rotor_skew_steps"] < 2:
        raise SpecError("'machine.rotor_skew_el_deg' needs 'machine.rotor_skew_steps' of 2 or more.")
    if machine["rotor_skew_steps"] > 1 and rotor_code(machine) == "axial":
        raise SpecError("The rotor skew is not available for the axial-ring rotor.")
