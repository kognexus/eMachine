#!/usr/bin/env bash
# Builds Elmer FEM (ElmerSolver, ElmerGrid) from source and installs it into a prefix.
#
#     pixi run install-elmer                    # into the pixi environment (default)
#     PREFIX=$HOME/elmer bash scripts/install_elmer.sh   # anywhere else; then export ELMER_HOME=$HOME/elmer
#
# Needs CMake, C/C++/Fortran compilers and BLAS/LAPACK; the pixi environment provides all of them.
# Elmer is not on conda-forge or PyPI, hence the source build. Serial build (no MPI): emachine runs
# rotor positions as separate processes instead.
set -euo pipefail

ELMER_VERSION="${ELMER_VERSION:-release-26.2.1}"
PREFIX="${PREFIX:-${CONDA_PREFIX:-}}"
JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
WORK="${WORK:-$(pwd)/.elmer}"

if [ -z "$PREFIX" ]; then
  echo "No install prefix: run inside the pixi environment (pixi run install-elmer) or set PREFIX." >&2
  exit 1
fi
if [ -x "$PREFIX/bin/ElmerSolver" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "Elmer is already installed in $PREFIX (set FORCE=1 to rebuild)."
  exit 0
fi

mkdir -p "$WORK"
if [ ! -d "$WORK/src/.git" ]; then
  git clone --depth 1 --branch "$ELMER_VERSION" https://github.com/ElmerCSC/elmerfem.git "$WORK/src"
fi

cmake -S "$WORK/src" -B "$WORK/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_PREFIX_PATH="$PREFIX" \
  -DUSE_MACOS_PACKAGE_MANAGER=OFF \
  -DWITH_MPI=OFF \
  -DWITH_OpenMP=OFF \
  -DWITH_ELMERGUI=OFF \
  -DBLA_VENDOR=OpenBLAS \
  > "$WORK/configure.log" 2>&1 || { tail -40 "$WORK/configure.log"; exit 1; }
cmake --build "$WORK/build" -j "$JOBS" > "$WORK/build.log" 2>&1 || { tail -40 "$WORK/build.log"; exit 1; }
cmake --install "$WORK/build" > "$WORK/install.log" 2>&1 || { tail -40 "$WORK/install.log"; exit 1; }

echo "Installed Elmer $ELMER_VERSION into $PREFIX"
echo "Build files are in $WORK (safe to delete)."
