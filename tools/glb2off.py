#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, json, struct, sys, pathlib).
"""Convert a city GLB into a triangle OFF mesh.

Input:  data/processed/scenes/city.standardized.glb
Output: generated/meshes/city.standardized.glb2off.off

The reader bakes the nested node transforms, converts the glTF Y-up frame to
Gazebo Z-up and normalizes the width to 200 m, so the OFF shares the coordinate
frame of city.standardized.triangulation.off. Materials and textures are
dropped. Vertices stay as stored per primitive; nothing is welded, so seams
between glTF primitives remain.

Examples:
  .venv/bin/python tools/glb2off.py
  .venv/bin/python tools/glb2off.py data/raw/scenes/city.glb --output /tmp/city.off
"""
import argparse
import json
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / 'data/processed/scenes/city.standardized.glb'
DEFAULT_OUTPUT = ROOT / 'generated/meshes'
JSON_CHUNK = 0x4e4f534a
BIN_CHUNK = 0x004e4942
TYPES = {5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
WIDTHS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def read_glb_scene(filename, width):
    blob = Path(filename).read_bytes()
    magic, version, total = struct.unpack_from('<4sII', blob)
    if magic != b'glTF' or version != 2 or total != len(blob):
        raise SystemExit(f'glb2off: {filename} is not a valid GLB 2 file')
    chunks = {}
    offset = 12
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        chunks[kind] = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    try:
        document = json.loads(chunks[JSON_CHUNK])
    except KeyError:
        raise SystemExit(f'glb2off: {filename} has no JSON chunk') from None
    try:
        binary = chunks[BIN_CHUNK]
    except KeyError:
        raise SystemExit(f'glb2off: {filename} has no binary chunk') from None

    def accessor(index):
        entry = document['accessors'][index]
        if 'sparse' in entry:
            raise SystemExit('glb2off: sparse accessors are not supported')
        view = document['bufferViews'][entry['bufferView']]
        dtype = np.dtype(TYPES[entry['componentType']])
        components = WIDTHS[entry['type']]
        return np.ndarray(
            (entry['count'], components), dtype=dtype, buffer=binary,
            offset=view.get('byteOffset', 0) + entry.get('byteOffset', 0),
            strides=(view.get('byteStride', components * dtype.itemsize),
                     dtype.itemsize)).copy()

    def transform(node):
        if 'matrix' in node:
            return np.array(node['matrix']).reshape(4, 4, order='F')
        x, y, z, w = node.get('rotation', [0, 0, 0, 1])
        rotation = np.array([
            [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * z * w, 2 * x * z + 2 * y * w],
            [2 * x * y + 2 * z * w, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * x * w],
            [2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x * x - 2 * y * y]])
        matrix = np.eye(4)
        matrix[:3, :3] = rotation @ np.diag(node.get('scale', [1, 1, 1]))
        matrix[:3, 3] = node.get('translation', [0, 0, 0])
        return matrix

    parts = []
    triangles = []
    offset = 0

    def walk(index, parent):
        nonlocal offset
        node = document['nodes'][index]
        matrix = parent @ transform(node)
        if 'mesh' in node:
            for primitive in document['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode', 4) != 4:
                    raise SystemExit('glb2off: only triangle primitives are supported')
                positions = accessor(primitive['attributes']['POSITION']).astype(float)
                positions = (np.c_[positions, np.ones(len(positions))] @ matrix.T)[:, :3]
                # glTF scene Y-up -> Gazebo Z-up after all nested transforms.
                positions = positions[:, [0, 2, 1]] * np.array([1, -1, 1])
                if 'indices' in primitive:
                    indices = accessor(primitive['indices']).ravel()
                else:
                    indices = np.arange(len(positions))
                triangles.append(indices.reshape(-1, 3) + offset)
                parts.append(positions)
                offset += len(positions)
        for child in node.get('children', []):
            walk(child, matrix)

    for root in document['scenes'][document.get('scene', 0)]['nodes']:
        walk(root, np.eye(4))
    if not parts:
        raise SystemExit(f'glb2off: {filename} contains no triangle geometry')
    vertices = np.vstack(parts)
    faces = np.vstack(triangles).astype(np.int64)

    low, high = vertices.min(axis=0), vertices.max(axis=0)
    scale = width / max(high[0] - low[0], high[1] - low[1])
    origin = np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])
    vertices = (vertices - origin) * scale
    return vertices, faces


def unique_edge_count(faces):
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    return int(np.unique(edges, axis=0).shape[0])


def write_off(path, vertices, faces):
    edges = unique_edge_count(faces)
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write('OFF\n')
        handle.write(f'{len(vertices)} {len(faces)} {edges}\n')
        for x, y, z in vertices:
            handle.write(f'{x:.17g} {y:.17g} {z:.17g}\n')
        for a, b, c in faces:
            handle.write(f'3 {a} {b} {c}\n')
    return edges


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('scene', nargs='?', type=Path, default=DEFAULT_INPUT,
                        help=f'GLB scene (default: {DEFAULT_INPUT.relative_to(ROOT)})')
    parser.add_argument('--output', type=Path, default=None, metavar='OFF',
                        help='Output path (default: '
                             f'{DEFAULT_OUTPUT.relative_to(ROOT)}/<stem>.glb2off.off)')
    parser.add_argument('--width', type=float, default=200.,
                        help='Normalized width in metres (default: 200)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite an existing OFF file')
    args = parser.parse_args()

    if not (args.width > 0 and np.isfinite(args.width)):
        parser.error('--width must be positive and finite')
    scene = args.scene.resolve()
    if not scene.is_file():
        parser.error(f'GLB not found: {scene}')
    output = (args.output or (DEFAULT_OUTPUT / f'{scene.stem}.glb2off.off')).resolve()
    if output.exists() and not args.force:
        parser.error(f'{output} exists; pass --force to overwrite')

    vertices, faces = read_glb_scene(scene, args.width)
    output.parent.mkdir(parents=True, exist_ok=True)
    edges = write_off(output, vertices, faces)

    lines = sum(1 for _ in output.open(encoding='utf-8'))
    expected = 2 + len(vertices) + len(faces)
    if lines != expected:
        raise SystemExit(f'glb2off: wrote {lines} lines, expected {expected}')
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    print(f'Input:  {scene} — {len(vertices)} vertices, {len(faces)} triangles')
    print(f'Bounds: x [{low[0]:.2f}, {high[0]:.2f}] '
          f'y [{low[1]:.2f}, {high[1]:.2f}] z [{low[2]:.2f}, {high[2]:.2f}]')
    print(f'Output: {output} — {edges} edges, '
          f'{output.stat().st_size / 1e6:.1f} MB')
    print(f'Save at: {output}')


if __name__ == '__main__':
    main()
