# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (ctypes); libassimp5 from the Gazebo image.
"""Check that Assimp, the loader Gazebo uses for mesh visuals, imports a GLB.

Gazebo reads a visual `.glb` through gz-rendering's AssimpLoader. A GLB that
browsers tolerate can still be rejected there, and the model then appears in
the entity tree without geometry. This script calls the same library and
reports the import error, so the failure is visible before a flight.

Run it inside the Gazebo container, which ships libassimp5:

    docker run --rm -v "$PWD:/work" -w /work \
      ghcr.io/openrobotics/gazebo:jetty-full \
      python3 tools/simulate/check_glb.py generated/simulate/*/city.sim.glb

`run_simulate.sh --check` calls it for the world it is about to fly.
"""
import ctypes
import sys
from pathlib import Path

# aiScene starts with mFlags, then mRootNode, then mNumMeshes; the pointer
# before the count is why mNumMeshes is read at byte offset 16, not 4.
MESH_COUNT_OFFSET = 16


def load_assimp(library='libassimp.so.5'):
    lib = ctypes.CDLL(library)
    lib.aiImportFile.restype = ctypes.c_void_p
    lib.aiImportFile.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    lib.aiGetErrorString.restype = ctypes.c_char_p
    return lib


def check(lib, path):
    """Return (mesh_count, error). error is empty when the import worked."""
    scene = lib.aiImportFile(str(path).encode('utf-8'), 0)
    if not scene:
        return 0, (lib.aiGetErrorString() or b'unknown error').decode('utf-8', 'replace')
    count = ctypes.c_uint.from_address(scene + MESH_COUNT_OFFSET).value
    return int(count), ''


def main():
    paths = [Path(argument) for argument in sys.argv[1:]]
    if not paths:
        print('usage: check_glb.py FILE.glb [FILE.glb ...]', file=sys.stderr)
        return 2
    try:
        lib = load_assimp()
    except OSError as error:
        print(f'check_glb: cannot load libassimp: {error}', file=sys.stderr)
        return 2
    failed = 0
    for path in paths:
        if not path.is_file():
            print(f'fail {path}: missing')
            failed += 1
            continue
        count, error = check(lib, path)
        if error:
            print(f'fail {path}: {error}')
            failed += 1
        else:
            print(f'ok   {path}: {count} mesh(es), {path.stat().st_size} bytes')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
