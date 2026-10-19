"""
CAD of the TFM: the Onshape FeatureScript features (featurescript/), the generator of the
combined "TFM UI32 machine" studio (ui32_build.py) and the parameter sheet that lists a design
under the field names of the Onshape dialogs (sheet.py).
"""

import os

FEATURESCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "featurescript")


def featurescript(name):
    """Path of a FeatureScript file, e.g. featurescript("tfm_stator.fs")."""
    return os.path.join(FEATURESCRIPT_DIR, name)
