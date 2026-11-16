#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, json, struct, sys, pathlib);
# local modules (mesh_off).
"""Convert a city GLB into a triangle OFF mesh.

Input:  data/processed/scenes/city.standardized.glb
Output: data/processed/meshes/city.standardized.glb2off.off

The reader bakes the nested node transforms, converts the glTF Y-up frame to
Z-up and normalizes the width to 200 m, so the OFF shares the coordinate
frame of city.standardized.triangulation.off. Materials and textures are
dropped. Vertices stay as stored per primitive; nothing is welded, so seams
between glTF primitives remain.

Examples:
  .venv/bin/python tools/data/glb2off.py
  .venv/bin/python tools/data/glb2off.py data/raw/scenes/city.glb --output /tmp/city.off
"""
import argparse
import json
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
from mesh_off import write_off

DEFAULT_INPUT = ROOT / 'data/processed/scenes/city.standardized.glb'
DEFAULT_OUTPUT = ROOT / 'data/processed/meshes'
JSON_CHUNK = 0x4e4f534a
BIN_CHUNK = 0x004e4942
TYPES = {5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
WIDTHS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def read_document(filename):
    """Parse a GLB 2 file into its JSON document and binary chunk."""
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
    return document, binary


def _accessor(document, binary, index):
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


def _node_matrix(node):
    """Local transform of one node, as a 4x4 matrix."""
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


def iter_scene_meshes(filename):
    """Yield (name, vertices, faces) per mesh node, in world coordinates.

    Vertices carry the scene's own axes and units: the nested node transforms
    are baked, nothing is rotated or rescaled. Use read_glb_scene for the
    project frame (Z-up, 200 m wide) or transformed_objects for triangle soup.
    """
    document, binary = read_document(filename)

    def walk(index, parent):
        node = document['nodes'][index]
        matrix = parent @ _node_matrix(node)
        if 'mesh' in node:
            parts, triangles, offset = [], [], 0
            for primitive in document['meshes'][node['mesh']]['primitives']:
                if (primitive.get('mode', 4) != 4 or
                        primitive.get('extensions', {}).get('KHR_draco_mesh_compression')):
                    raise SystemExit('glb2off: only uncompressed triangle primitives '
                                     'are supported')
                positions = _accessor(document, binary,
                                      primitive['attributes']['POSITION']).astype(float)
                positions = (np.c_[positions, np.ones(len(positions))] @ matrix.T)[:, :3]
                if 'indices' in primitive:
                    indices = _accessor(document, binary, primitive['indices']).ravel()
                else:
                    indices = np.arange(len(positions))
                parts.append(positions)
                triangles.append(indices.reshape(-1, 3) + offset)
                offset += len(positions)
            yield (node.get('name', str(index)), np.vstack(parts),
                   np.vstack(triangles).astype(np.int64))
        for child in node.get('children', []):
            yield from walk(child, matrix)

    for root in document['scenes'][document.get('scene', 0)]['nodes']:
        yield from walk(root, np.eye(4))


def transformed_objects(filename):
    """Yield (name, world-space triangle soup) per mesh node, own axes."""
    for name, vertices, faces in iter_scene_meshes(filename):
        yield name, vertices[faces]


def read_glb_scene(filename, width):
    """All scene triangles in the project frame: Z-up, width metres wide."""
    parts, triangles, offset = [], [], 0
    for _, vertices, faces in iter_scene_meshes(filename):
        # glTF scene Y-up -> Z-up after all nested transforms.
        vertices = vertices[:, [0, 2, 1]] * np.array([1, -1, 1])
        triangles.append(faces + offset)
        parts.append(vertices)
        offset += len(vertices)
    if not parts:
        raise SystemExit(f'glb2off: {filename} contains no triangle geometry')
    vertices = np.vstack(parts)
    faces = np.vstack(triangles).astype(np.int64)

    low, high = vertices.min(axis=0), vertices.max(axis=0)
    scale = width / max(high[0] - low[0], high[1] - low[1])
    origin = np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])
    return (vertices - origin) * scale, faces


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
