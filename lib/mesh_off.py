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
- `Mesh` is the data structure the algorithms walk on: points, faces and the
  two adjacency tables, plus the intrinsic queries (distance, angle, the face
  across an edge). It is built from arrays, so it does not know about files.

The declared edge count `E` is never trusted: real edges are derived from the
faces, because some fixtures carry an inaccurate `E`.
"""
from collections import Counter
from dataclasses import dataclass
import math
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


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float

    def distance(self, other):
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2
                         + (self.z - other.z) ** 2)


class Mesh:
    """Triangle surface with the adjacency the Funnel algorithms need."""

    def __init__(self, points, faces):
        self.points = [point if isinstance(point, Point) else Point(*map(float, point))
                       for point in points]
        self.faces = [tuple(int(vertex) for vertex in face) for face in faces]
        if len(self.points) < 3 or len(self.faces) < 1:
            raise ValueError('mesh is empty')
        coordinates = [(point.x, point.y, point.z) for point in self.points]
        if len(set(coordinates)) != len(coordinates):
            raise ValueError('two vertices share coordinates')
        self.vertex_faces = [[] for _ in self.points]
        self.edge_faces = {}
        seen = set()
        for face_id, face in enumerate(self.faces):
            if len(set(face)) != 3 or any(v < 0 or v >= len(self.points) for v in face):
                raise ValueError(f'face {face_id} has invalid vertex indices')
            key = tuple(sorted(face))
            if key in seen:
                raise ValueError(f'face {face_id} is repeated')
            seen.add(key)
            for vertex in face:
                self.vertex_faces[vertex].append(face_id)
            for a, b in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((a, b)))
                self.edge_faces.setdefault(edge, []).append(face_id)
                if len(self.edge_faces[edge]) > 2:
                    raise ValueError(f'edge {edge} borders more than two faces')
        if any(not faces for faces in self.vertex_faces):
            raise ValueError('a vertex belongs to no face')
        self.stats = _stats(self.points, self.faces)

    def distance(self, a, b):
        return self.points[a].distance(self.points[b])

    def angle(self, a, b, c):
        """Angle ABC at B, in radians, by the law of cosines."""
        ab, bc, ac = self.distance(a, b), self.distance(b, c), self.distance(a, c)
        if ab == 0 or bc == 0:
            raise ValueError('angle is undefined for a zero-length edge')
        cosine = (ab * ab + bc * bc - ac * ac) / (2 * ab * bc)
        return math.acos(max(-1., min(1., cosine)))

    def other_face(self, a, b, current_face):
        """Face on the other side of edge AB; None on a boundary edge."""
        adjacent = self.edge_faces[tuple(sorted((a, b)))]
        if current_face not in adjacent:
            raise ValueError('current face does not contain the queried edge')
        return next((face for face in adjacent if face != current_face), None)

    def third_vertex(self, face_id, a, b):
        face = self.faces[face_id]
        if a == b or a not in face or b not in face:
            raise ValueError('two vertices must define an edge of the face')
        return next(vertex for vertex in face if vertex != a and vertex != b)


def read_mesh(path):
    """Read an OFF file and build the Mesh the algorithms walk on."""
    return Mesh(*read_off(path))


def _stats(points, faces):
    """Topology counts; `inspect_mesh` returns this without judging validity."""
    coordinates = [(point.x, point.y, point.z) for point in points]
    edges = {}
    vertex_faces = [[] for _ in points]
    for face_id, face in enumerate(faces):
        for vertex in face:
            vertex_faces[vertex].append(face_id)
        for a, b in zip(face, face[1:] + face[:1]):
            edges.setdefault(tuple(sorted((int(a), int(b)))), []).append(face_id)
    boundary_degree = Counter()
    nonmanifold = 0
    for (a, b), adjacent in edges.items():
        if len(adjacent) == 1:
            boundary_degree[a] += 1
            boundary_degree[b] += 1
        if len(adjacent) > 2:
            nonmanifold += 1
    bad_fans = 0
    for vertex, incident in enumerate(vertex_faces):
        if not incident:
            bad_fans += 1
            continue
        adjacency = {face: set() for face in incident}
        for face in incident:
            for other in faces[face]:
                if other == vertex:
                    continue
                for neighbour in edges[tuple(sorted((int(vertex), int(other))))]:
                    if neighbour != face:
                        adjacency[face].add(neighbour)
        reached, stack = {incident[0]}, [incident[0]]
        while stack:
            for neighbour in adjacency[stack.pop()]:
                if neighbour not in reached:
                    reached.add(neighbour)
                    stack.append(neighbour)
        if len(reached) != len(incident):
            bad_fans += 1
    coords = np.array(coordinates, dtype=float)
    array = coords[np.array(faces, dtype=int)]
    areas = np.linalg.norm(np.cross(array[:, 1] - array[:, 0],
                                    array[:, 2] - array[:, 0]), axis=1) / 2
    return {'vertices': len(points), 'triangles': len(faces), 'edges': len(edges),
            'boundary_edges': sum(len(a) == 1 for a in edges.values()),
            'nonmanifold_edges': nonmanifold,
            'bad_boundary_vertices': sum(d != 2 for d in boundary_degree.values()),
            'disconnected_vertex_fans': bad_fans,
            'degenerate_triangles': int((areas <= 1e-12).sum()),
            'area': float(areas.sum())}


def inspect_mesh(points, faces):
    """Return the topology counts without raising on invalid meshes."""
    as_points = [point if isinstance(point, Point) else Point(*map(float, point))
                 for point in points]
    return _stats(as_points, [tuple(int(v) for v in face) for face in faces])


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
