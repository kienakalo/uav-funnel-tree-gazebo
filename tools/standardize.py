# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, hashlib, json, struct, pathlib);
# local modules (glb, inspect_flight_levels_fixed).
"""Standardize a raw city GLB into a scene with a documented contract.

Input:  data/raw/scenes/city.glb (third-party, Y-up, Sketchfab node names)
Output: data/processed/standardized/city.standardized.glb

The output keeps one node per city object, applies the scene transforms once,
drops materials and textures, and records provenance, axis and counts in the
asset extras. Geometry is not changed.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from glb import indexed_from_triangles, read_glb, write_glb
from inspect_flight_levels_fixed import transformed_objects

DEFAULT_INPUT = ROOT / 'data/raw/scenes/city.glb'
DEFAULT_OUTPUT = ROOT / 'data/processed/standardized/city.standardized.glb'


def asset_extras(path):
    blob = path.read_bytes()
    _, _, total = struct.unpack_from('<4sII', blob)
    if total != len(blob):
        raise ValueError('Invalid GLB length')
    offset, chunks = 12, {}
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        chunks[kind] = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    return json.loads(chunks[0x4E4F534A]).get('asset', {}).get('extras', {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f'Missing raw scene: {args.input}')

    extras = asset_extras(args.input)
    meshes = []
    triangles = 0
    for index, (name, soup) in enumerate(transformed_objects(args.input)):
        vertices, faces = indexed_from_triangles(soup)
        meshes.append({'name': f'object_{index:03d}', 'vertices': vertices,
                       'faces': faces, 'extras': {'source_name': name}})
        triangles += len(faces)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        'source_file': args.input.relative_to(ROOT).as_posix(),
        'source_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'license': extras.get('license'),
        'author': extras.get('author'),
        'source_url': extras.get('source'),
        'title': extras.get('title'),
        'units': 'original model units',
        'axis': 'Y-up (glTF convention)',
        'objects': len(meshes),
        'vertices': int(sum(len(m['vertices']) for m in meshes)),
        'triangles': int(triangles),
        'policy': 'transforms baked once; materials and textures dropped; node names normalized',
    }
    report = write_glb(args.output, meshes, extras=manifest,
                       generator='uav-funnel-tree-gazebo standardize')

    reloaded = read_glb(args.output)
    if sum(len(faces) for _, _, faces in reloaded) != triangles:
        raise ValueError('Reloaded scene triangle count does not match the source')
    if not all(np.isfinite(vertices).all() for _, vertices, _ in reloaded):
        raise ValueError('Reloaded scene has non-finite coordinates')
    print(json.dumps(report, indent=2))
    print(f'Save at: {args.output}')


if __name__ == '__main__':
    main()
