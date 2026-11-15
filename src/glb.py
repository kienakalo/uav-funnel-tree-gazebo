# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy (geometry arrays); Python stdlib (json, struct, pathlib).
"""Minimal glTF 2.0 binary writer and reader for indexed triangle meshes.

Only the subset used by the project is implemented: one buffer, one binary
chunk, POSITION float32 and uint32 triangle indices, identity node transforms.
"""
import json
import struct
from pathlib import Path

import numpy as np

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def _pad(data, fill=b'\x00'):
    return data + fill * ((4 - len(data) % 4) % 4)


def indexed_from_triangles(triangles):
    """Weld a triangle soup into indexed vertices and faces."""
    flat = np.asarray(triangles, dtype=np.float32).reshape(-1, 3)
    if not np.isfinite(flat).all():
        raise ValueError('Non-finite coordinates in triangle soup')
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    return vertices.astype(np.float32), faces


def write_glb(path, meshes, extras=None, generator='uav-funnel-tree-gazebo'):
    """Write meshes as a GLB. Each mesh is {name, vertices, faces, extras?}."""
    binary = bytearray()
    buffer_views = []
    accessors = []
    primitives = []
    nodes = []
    for index, mesh in enumerate(meshes):
        vertices = np.asarray(mesh['vertices'], dtype=np.float32)
        faces = np.asarray(mesh['faces'], dtype=np.int64)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0:
            raise ValueError(f'Mesh {index}: vertices must be a non-empty Nx3 array')
        if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0:
            raise ValueError(f'Mesh {index}: faces must be a non-empty Mx3 array')
        if faces.min() < 0 or faces.max() >= len(vertices):
            raise ValueError(f'Mesh {index}: face index outside vertex array')

        while len(binary) % 4:
            binary.append(0)
        position_offset = len(binary)
        binary.extend(vertices.astype('<f4').tobytes())
        while len(binary) % 4:
            binary.append(0)
        index_offset = len(binary)
        binary.extend(faces.astype('<u4').tobytes())

        buffer_views.append({'buffer': 0, 'byteOffset': position_offset,
                             'byteLength': vertices.nbytes, 'target': 34962})
        buffer_views.append({'buffer': 0, 'byteOffset': index_offset,
                             'byteLength': faces.nbytes, 'target': 34963})
        accessors.append({
            'bufferView': len(buffer_views) - 2, 'componentType': 5126,
            'count': int(len(vertices)), 'type': 'VEC3',
            'min': [float(v) for v in vertices.min(axis=0)],
            'max': [float(v) for v in vertices.max(axis=0)],
        })
        accessors.append({
            'bufferView': len(buffer_views) - 1, 'componentType': 5125,
            'count': int(faces.size), 'type': 'SCALAR',
        })
        primitives.append({'attributes': {'POSITION': len(accessors) - 2},
                           'indices': len(accessors) - 1, 'mode': 4})
        entry = {'name': mesh.get('name', f'mesh_{index}'), 'mesh': index}
        if mesh.get('extras'):
            entry['extras'] = mesh['extras']
        nodes.append(entry)

    document = {
        'asset': {'version': '2.0', 'generator': generator, 'extras': extras or {}},
        'scene': 0,
        'scenes': [{'nodes': list(range(len(nodes))), 'name': 'scene'}],
        'nodes': nodes,
        'meshes': [{'name': mesh.get('name', f'mesh_{i}'), 'primitives': [primitive]}
                   for i, (mesh, primitive) in enumerate(zip(meshes, primitives))],
        'accessors': accessors,
        'bufferViews': buffer_views,
        'buffers': [{'byteLength': len(binary)}],
    }
    text = _pad(json.dumps(document, separators=(',', ':')).encode('utf-8'), b' ')
    body = _pad(bytes(binary))
    total = 12 + 8 + len(text) + 8 + len(body)
    blob = struct.pack('<4sII', b'glTF', 2, total)
    blob += struct.pack('<II', len(text), JSON_CHUNK) + text
    blob += struct.pack('<II', len(body), BIN_CHUNK) + body
    Path(path).write_bytes(blob)
    return {'meshes': len(meshes), 'vertices': int(sum(len(m['vertices']) for m in meshes)),
            'triangles': int(sum(len(m['faces']) for m in meshes)), 'bytes': len(blob)}


def read_glb(path):
    """Read the subset written above; returns [(name, vertices, faces)]."""
    blob = Path(path).read_bytes()
    magic, version, total = struct.unpack_from('<4sII', blob)
    if magic != b'glTF' or version != 2 or total != len(blob):
        raise ValueError('Invalid GLB 2 file')
    chunks = {}
    offset = 12
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        chunks[kind] = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    document = json.loads(chunks[JSON_CHUNK])
    binary = chunks.get(BIN_CHUNK, b'')
    result = []
    for node in document['nodes']:
        mesh = document['meshes'][node['mesh']]
        primitive = mesh['primitives'][0]
        position = document['accessors'][primitive['attributes']['POSITION']]
        index = document['accessors'][primitive['indices']]
        view = document['bufferViews'][position['bufferView']]
        start = view.get('byteOffset', 0) + position.get('byteOffset', 0)
        vertices = np.frombuffer(binary, dtype='<f4', count=position['count'] * 3,
                                 offset=start).reshape(-1, 3)
        view = document['bufferViews'][index['bufferView']]
        start = view.get('byteOffset', 0) + index.get('byteOffset', 0)
        faces = np.frombuffer(binary, dtype='<u4', count=index['count'],
                              offset=start).reshape(-1, 3)
        result.append((node.get('name'), vertices.astype(np.float64), faces.astype(np.int64)))
    return result
