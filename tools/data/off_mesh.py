# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (collections).
"""Topology checks and the OFF writer used by the data stage.

`inspect_mesh` reports the properties the navigation surface must have: a
closed two-manifold where every vertex belongs to one connected fan.
`write_off` writes the triangle-only OFF text read back by the Funnel tools.
"""
from collections import Counter

import numpy as np


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


def write_off(path, points, faces, edges):
    """Write 'OFF', the V F E header, then vertices and triangle faces."""
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write('OFF\n')
        handle.write(f'{len(points)} {len(faces)} {edges}\n')
        for point in points:
            handle.write(' '.join(f'{value:.17g}' for value in point) + '\n')
        for face in faces:
            handle.write('3 ' + ' '.join(map(str, face)) + '\n')
