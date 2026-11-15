# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, hashlib, json, pathlib);
# local modules (glb, mesh).
"""Convert raw OFF fixtures into simulation-ready GLB for Gazebo.

Input:  data/raw/meshes/*.off (model units, Z-up, as used by the planner)
Output: data/processed/scenes/meshes/*.sim.glb

Coordinates are kept unchanged by default: the fixtures use Z as the
elevation axis, which matches Gazebo. Pass --to-z-up for Y-up sources; Gazebo
does not convert glTF axes, so the rotation (x, y, z) -> (x, -z, y) has to be
baked into the file. glTF viewers assume Y-up, so a Z-up .sim.glb appears
rotated there; that is expected for a simulation asset.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from glb import read_glb, write_glb
from mesh import read_off

DEFAULT_INPUT = ROOT / 'data/raw/meshes'
DEFAULT_OUTPUT = ROOT / 'data/processed/scenes/meshes'


def convert(source, output, to_z_up=False):
    mesh = read_off(source)
    if to_z_up:
        vertices = [(point.x, -point.z, point.y) for point in mesh.points]
        axis = 'Z-up (baked from Y-up)'
    else:
        vertices = [(point.x, point.y, point.z) for point in mesh.points]
        axis = 'as authored (fixtures use Z-up)'
    faces = [tuple(face) for face in mesh.faces]
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
                       extras=extras, generator='uav-funnel-tree-gazebo off_to_glb')
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
    parser.add_argument('--to-z-up', action='store_true',
                        help='Bake (x,y,z) -> (x,-z,y) for Y-up sources')
    args = parser.parse_args()
    sources = sorted(args.input.glob('*.off'))
    if args.mesh:
        wanted = set(args.mesh)
        sources = [path for path in sources if path.stem in wanted]
    if not sources:
        parser.error(f'No .off fixtures found in {args.input}')
    for source in sources:
        output = args.output / f'{source.stem}.sim.glb'
        report = convert(source, output, args.to_z_up)
        print(f'{source.stem}: {json.dumps(report)}')
        print(f'Save at: {output}')


if __name__ == '__main__':
    main()
