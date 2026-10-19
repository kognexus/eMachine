"""Running external programs (Gmsh scripts, ElmerGrid, ElmerSolver) with their output in a log file."""

import os
import subprocess

#: The project folder: subprocesses that run Python modules of emachine get it on their path.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class StageError(RuntimeError):
    """A program of the chain failed. The message names the log file."""


def read_text(path):
    with open(path, errors="replace") as f:
        return f.read()


def run(cmd, cwd, log):
    """Runs a command with its output in a log file. Raises StageError on failure."""
    path = os.environ.get("PYTHONPATH", "")
    env = dict(os.environ, OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1",
               PYTHONPATH=ROOT + (os.pathsep + path if path else ""))
    with open(log, "w") as f:
        f.write("$ " + " ".join(cmd) + "\n\n")
        f.flush()
        code = subprocess.call(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env)
    if code != 0:
        tail = "\n".join(read_text(log).splitlines()[-15:])
        raise StageError(f"{os.path.basename(cmd[0])} failed ({code}), see {log}\n{tail}")
