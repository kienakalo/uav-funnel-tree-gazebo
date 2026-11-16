# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, hashlib, json, pathlib);
# local modules (glb, off).
"""Convert raw OFF fixtures into glTF binary (Y-up by default).

Input:  data/raw/meshes/*.off (model units; axis documented in data/README.md)
Output: data/processed/scenes/meshes/*.off2glb.glb (Y-up unless --keep-z-up)

Coordinates are kept unchanged by default: the fixtures use Z as the
elevation axis. Pass --keep-z-up for Z-up simulation frames; the default output
does not convert glTF axes, so the rotation (x, y, z) -> (x, -z, y) has to be
baked into the file. glTF viewers assume Y-up, so a Z-up .off2glb.glb appears
rotated there; that is expected for a simulation asset.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from glb import read_glb, write_glb
from off import read_off

DEFAULT_INPUT = ROOT / 'data/raw/meshes'
DEFAULT_OUTPUT = ROOT / 'data/processed/scenes/meshes'


def convert(source, output, keep_z_up=False):
    points, faces = read_off(source)
    if keep_z_up:
        vertices = points
        axis = 'Z-up (simulation)'
    else:
        vertices = points[:, [0, 2, 1]] * np.array([1., 1., -1.])
        axis = 'Y-up (glTF)'
    output.parent.mkdir(parents=True, exist_ok=True)
    extras = {
        'source_file': source.relative_to(ROOT).as_posix(),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'axis': axis,
        'units': 'original model units',
        'vertices': len(vertices),
        'triangles': len(faces),
        'policy': 'format conversion only; no geometric repair',
    }
    report = write_glb(output, [{'name': source.stem, 'vertices': vertices,
                                 'faces': faces, 'extras': extras}],
                       extras=extras, generator='uav-funnel-tree-gazebo off2glb')
    name, reloaded_vertices, reloaded_faces = read_glb(output)[0]
    if len(reloaded_vertices) != len(vertices) or len(reloaded_faces) != len(faces):
        raise ValueError(f'{source}: reloaded counts differ')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--mesh', action='append', default=None,
                        help='Convert only these stems (default: all)')
    parser.add_argument('--keep-z-up', action='store_true',
                        help='Keep Z-up coordinates for a simulation frame instead of writing Y-up glTF')
    args = parser.parse_args()
    sources = sorted(args.input.glob('*.off'))
    if args.mesh:
        wanted = set(args.mesh)
        sources = [path for path in sources if path.stem in wanted]
    if not sources:
        parser.error(f'No .off fixtures found in {args.input}')
    for source in sources:
        output = args.output / f'{source.stem}.off2glb.glb'
        report = convert(source, output, args.keep_z_up)
        print(f'{source.stem}: {json.dumps(report)}')
        print(f'Save at: {output}')


if __name__ == '__main__':
    main()
