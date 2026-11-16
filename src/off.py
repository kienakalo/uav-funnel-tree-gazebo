# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (collections, pathlib).
"""OFF: the triangle-mesh text format shared by the data stage.

One reader, one writer and one topology check, so a format rule changes in a
single place:

- `read_off` parses `OFF`, the `V F E` header, one `x y z` line per vertex and
  one `3 a b c` line per triangle.
- `write_off` writes the same text with `%.17g` coordinates, so a value read
  back is bit-identical to the computed double.
- `inspect_mesh` reports the topology the navigation surface must have: a
  closed two-manifold where every vertex belongs to one connected fan.

The declared edge count `E` is never trusted: real edges are derived from the
faces, because some fixtures carry an inaccurate `E`.
"""
from collections import Counter
from pathlib import Path

import numpy as np


def read_off(path):
    """Parse a triangle-only OFF file into vertex and face arrays."""
    lines = [line.strip() for line in
             Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not lines or lines[0] != 'OFF':
        raise SystemExit(f'{path}: not an OFF file')
    try:
        vertex_count, face_count, _ = map(int, lines[1].split())
    except ValueError:
        raise SystemExit(f'{path}: the header is not "V F E"') from None
    if vertex_count < 3 or face_count < 1 or len(lines) != 2 + vertex_count + face_count:
        raise SystemExit(f'{path}: header and line count disagree')
    points = np.array([[float(value) for value in line.split()]
                       for line in lines[2:2 + vertex_count]], dtype=float)
    faces = np.array([[int(value) for value in line.split()[1:]]
                      for line in lines[2 + vertex_count:]], dtype=np.int64)
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise SystemExit(f'{path}: only triangle faces are supported')
    if faces.min() < 0 or faces.max() >= vertex_count:
        raise SystemExit(f'{path}: face index outside 0..{vertex_count - 1}')
    if not np.isfinite(points).all():
        raise SystemExit(f'{path}: non-finite vertex coordinate')
    return points, faces


def inspect_mesh(points, faces):
    """Count edges, boundary and non-manifold edges, bad fans and degenerates."""
    edge_faces = {}
    vertex_faces = [[] for _ in points]
    for face_id, face in enumerate(faces):
        for vertex in face:
            vertex_faces[vertex].append(face_id)
        for a, b in zip(face, np.roll(face, -1)):
            edge_faces.setdefault(tuple(sorted((int(a), int(b)))), []).append(face_id)
    boundary_degree = Counter()
    bad_edges = 0
    for (a, b), adjacent in edge_faces.items():
        if len(adjacent) == 1:
            boundary_degree[a] += 1
            boundary_degree[b] += 1
        if len(adjacent) > 2:
            bad_edges += 1
    bad_fans = 0
    for vertex, incident in enumerate(vertex_faces):
        adjacency = {face: set() for face in incident}
        for face in incident:
            for other in faces[face]:
                if other == vertex:
                    continue
                for neighbour in edge_faces[tuple(sorted((int(vertex), int(other))))]:
                    if neighbour != face:
                        adjacency[face].add(neighbour)
        if not incident:
            bad_fans += 1
            continue
        reached = {incident[0]}
        stack = [incident[0]]
        while stack:
            for neighbour in adjacency[stack.pop()]:
                if neighbour not in reached:
                    reached.add(neighbour)
                    stack.append(neighbour)
        if len(reached) != len(incident):
            bad_fans += 1
    areas = np.linalg.norm(np.cross(points[faces[:, 1]] - points[faces[:, 0]],
                                    points[faces[:, 2]] - points[faces[:, 0]]),
                           axis=1) / 2
    return {'vertices': len(points), 'triangles': len(faces), 'edges': len(edge_faces),
            'boundary_edges': sum(len(a) == 1 for a in edge_faces.values()),
            'nonmanifold_edges': bad_edges,
            'bad_boundary_vertices': sum(d != 2 for d in boundary_degree.values()),
            'disconnected_vertex_fans': bad_fans,
            'degenerate_triangles': int((areas <= 1e-12).sum()),
            'area': float(areas.sum())}


def unique_edge_count(faces):
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    return int(np.unique(edges, axis=0).shape[0])


def write_off(path, points, faces, edges=None):
    """Write 'OFF', the V F E header, then vertices and triangle faces."""
    if edges is None:
        edges = unique_edge_count(faces)
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write('OFF\n')
        handle.write(f'{len(points)} {len(faces)} {edges}\n')
        for point in points:
            handle.write(' '.join(f'{value:.17g}' for value in point) + '\n')
        for face in faces:
            handle.write('3 ' + ' '.join(map(str, face)) + '\n')
    return edges
