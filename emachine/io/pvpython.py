"""Where ParaView's Python (pvpython) is: the views are rendered with it, not with the project's Python."""

import glob
import os
import shutil

from .process import ROOT


def find_pvpython():
    """
    pvpython, first found of: $PVPYTHON (or the older $TFM_PVPYTHON), the pixi environment `paraview`
    (`pixi install -e paraview`), pvpython on the PATH, and the newest ParaView app in /Applications.
    None when there is none.
    """
    for name in ("PVPYTHON", "TFM_PVPYTHON"):
        if os.environ.get(name):
            return os.environ[name]
    candidates = [os.path.join(ROOT, ".pixi", "envs", "paraview", "bin", "pvpython"), shutil.which("pvpython")]
    candidates += sorted(glob.glob("/Applications/ParaView-*.app/Contents/bin/pvpython"), reverse=True)
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None
