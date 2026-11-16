# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (json, struct, pathlib).
"""Read the triangle soup of every node in this asset's GLB 2 scene.

`transformed_objects` walks the scene graph, bakes the nested transforms and
returns one (name, triangles) pair per mesh node. It keeps the scene's own
axes and units; the Y-up -> Z-up switch and the 200 m normalization belong to
tools/data/glb2off.py. Only uncompressed triangle primitives are supported, which is
what data/raw/scenes/city.glb contains.
"""
import json
import struct
from pathlib import Path

import numpy as np


def transformed_objects(filename):
    blob = Path(filename).read_bytes()
    magic, version, total = struct.unpack_from('<4sII', blob)
    if magic != b'glTF' or version != 2 or total != len(blob):
        raise ValueError('Invalid GLB 2 file.')
    chunks = {}
    offset = 12
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        chunks[kind] = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    document = json.loads(chunks[0x4e4f534a])
    binary = chunks[0x004e4942]

    def accessor(index):
        entry = document['accessors'][index]
        if 'sparse' in entry:
            raise ValueError('Sparse accessor not supported.')
        view = document['bufferViews'][entry['bufferView']]
        if view.get('buffer', 0) != 0:
            raise ValueError('External buffer not supported.')
        dtype = np.dtype({5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[
            entry['componentType']])
        width = {'SCALAR': 1, 'VEC3': 3}[entry['type']]
        return np.ndarray((entry['count'], width), dtype=dtype, buffer=binary,
                          offset=view.get('byteOffset', 0) + entry.get('byteOffset', 0),
                          strides=(view.get('byteStride', width * dtype.itemsize),
                                   dtype.itemsize)).copy()

    def local_matrix(node):
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

    def walk(index, parent):
        node = document['nodes'][index]
        matrix = parent @ local_matrix(node)
        if 'mesh' in node:
            pieces = []
            for primitive in document['meshes'][node['mesh']]['primitives']:
                if (primitive.get('mode', 4) != 4 or
                        primitive.get('extensions', {}).get('KHR_draco_mesh_compression')):
                    raise ValueError('Only uncompressed triangle primitives supported.')
                position = accessor(primitive['attributes']['POSITION']).astype(float)
                position = (np.c_[position, np.ones(len(position))] @ matrix.T)[:, :3]
                if 'indices' in primitive:
                    indices = accessor(primitive['indices']).ravel()
                else:
                    indices = np.arange(len(position))
                pieces.append(position[indices.reshape(-1, 3)])
            yield node.get('name', str(index)), np.concatenate(pieces)
        for child in node.get('children', []):
            yield from walk(child, matrix)

    for root in document['scenes'][document.get('scene', 0)]['nodes']:
        yield from walk(root, np.eye(4))
