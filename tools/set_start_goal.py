#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, dataclasses, hashlib, heapq,
# json, math, pathlib, re, sys, time); local modules (funnel_tree, verification).
"""Set START and GOAL points on the navigation surface and plan Funnel routes.

Input:  data/processed/meshes/city.standardized.triangulation.off (or --mesh)
        START: --start X Y Z or --start-vertex N
        GOAL:  --goal X Y Z (repeat), --goal-vertex N (repeat), or --all-goals
        --mission mission.json may carry the same choices
Output: generated/missions/<name>/plan.json
        generated/missions/<name>/<name>.paths.json   (all-goals only)
        generated/missions/<name>/routes.png

Coordinates are snapped to the nearest surface vertex before planning; the
distance is reported and checked against half a grid diagonal. --all-goals
makes every other vertex a goal, which is the one-source shortest-path tree
used by the fixture meshes such as cliff.off. Explicit goals share one source
graph and one cache. The Funnel route is not certified optimal.
"""
import argparse
from dataclasses import dataclass, field
import hashlib
import heapq
import json
import math
from pathlib import Path
import re
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from funnel_tree import propagate, reconstruct
from verification import segment_on_mesh

DEFAULT_MESH = ROOT / 'data/processed/meshes/city.standardized.triangulation.off'
DEFAULT_OUTPUT = ROOT / 'generated/missions'
PROVENANCE = ('src/funnel_tree.py', 'src/verification.py',
              'tools/set_start_goal.py')
COLOURS = ('#c0392b', '#8e44ad', '#e67e22', '#16a085', '#2c3e50', '#7f8c8d')


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float

    def distance(self, other):
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))


@dataclass
class Mesh:
    """Triangle surface with the adjacency Funnel propagation walks on."""

    points: list
    faces: list
    vertex_faces: list = field(init=False)
    edge_faces: dict = field(init=False)

    def __post_init__(self):
        self.vertex_faces = [[] for _ in self.points]
        self.edge_faces = {}
        seen_faces = set()
        coords = [(point.x, point.y, point.z) for point in self.points]
        if any(not all(math.isfinite(value) for value in item) for item in coords):
            raise ValueError('non-finite vertex coordinate')
        if len(set(coords)) != len(coords):
            raise ValueError('duplicate vertex coordinate')
        for face_id, face in enumerate(self.faces):
            if len(set(face)) != 3 or any(v < 0 or v >= len(self.points) for v in face):
                raise ValueError(f'face {face_id} has invalid vertex indices')
            if tuple(sorted(face)) in seen_faces:
                raise ValueError(f'face {face_id} is repeated')
            seen_faces.add(tuple(sorted(face)))
            a, b, c = [self.points[v] for v in face]
            u = (b.x - a.x, b.y - a.y, b.z - a.z)
            w = (c.x - a.x, c.y - a.y, c.z - a.z)
            cross = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2],
                     u[0] * w[1] - u[1] * w[0])
            if sum(value * value for value in cross) == 0:
                raise ValueError(f'face {face_id} is degenerate')
            for vertex in face:
                self.vertex_faces[vertex].append(face_id)
            a, b, c = face
            for first, second in ((a, b), (b, c), (c, a)):
                edge = tuple(sorted((first, second)))
                self.edge_faces.setdefault(edge, []).append(face_id)
                if len(self.edge_faces[edge]) > 2:
                    raise ValueError(f'edge {edge} borders more than two faces')
        if any(not faces for faces in self.vertex_faces):
            raise ValueError('a vertex belongs to no face')

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


def read_off(path):
    """Read a triangle-only OFF file: 'OFF', header V F E, then V and F lines."""
    lines = [line.strip() for line in
             Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not lines or lines[0] != 'OFF':
        raise ValueError(f'{path}: not an OFF file')
    vertex_count, face_count, _ = map(int, lines[1].split())
    if vertex_count < 3 or face_count < 1 or len(lines) != 2 + vertex_count + face_count:
        raise ValueError(f'{path}: header and line count disagree')
    points = [Point(*(float(value) for value in line.split()))
              for line in lines[2:2 + vertex_count]]
    faces = []
    for line in lines[2 + vertex_count:]:
        count, *face = (int(value) for value in line.split())
        if count != 3 or len(face) != 3:
            raise ValueError(f'{path}: only triangle faces are supported')
        faces.append(tuple(face))
    return Mesh(points, faces)


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n',
                         encoding='utf-8')
    temporary.replace(path)


def simplify(points):
    """Remove only forward collinear face crossings, retaining route corners."""
    result = []
    for point in points:
        if result and math.dist(result[-1], point) < 1e-12:
            continue
        while len(result) >= 2:
            a, b, c = np.array(result[-2]), np.array(result[-1]), np.array(point)
            delta = c - a
            length = float(np.linalg.norm(delta))
            if length <= 1e-12:
                break
            t = float(np.dot(b - a, delta) / (length * length))
            deviation = float(np.linalg.norm(b - (a + t * delta)))
            if not 0 <= t <= 1 or deviation > 1e-10:
                break
            result.pop()
        result.append(point)
    return result


def secondary_sources(mesh, source):
    boundary = {vertex for edge, adjacent in mesh.edge_faces.items()
                if len(adjacent) == 1 for vertex in edge}
    result = [source]
    for vertex, faces in enumerate(mesh.vertex_faces):
        if vertex == source:
            continue
        angle = 0.
        for face_id in faces:
            a, b = [index for index in mesh.faces[face_id] if index != vertex]
            angle += mesh.angle(a, vertex, b)
        if angle > (math.pi if vertex in boundary else 2 * math.pi) + 1e-5:
            result.append(vertex)
    return result


def candidate_route(mesh, source, goal, previous):
    chunks, chain, current = [], [goal], goal
    seen = set()
    while current != source:
        if current in seen:
            raise ValueError('cycle in secondary-source route')
        seen.add(current)
        parent, edge = previous[current]
        path = edge['path']
        if math.dist(path[0], vars_point(mesh.points[parent])) > 1e-7:
            raise ValueError('segment start mismatch')
        if math.dist(path[-1], vars_point(mesh.points[current])) > 1e-7:
            raise ValueError('segment end mismatch')
        chunks.append(path)
        current = parent
        chain.append(current)
    points = []
    for chunk in reversed(chunks):
        points.extend(chunk if not points else chunk[1:])
    return points, list(reversed(chain))


def vars_point(point):
    return (point.x, point.y, point.z)


def verify(mesh, points, path):
    triangles = np.array(points)[np.array(mesh.faces)]
    lows, highs = triangles.min(axis=1), triangles.max(axis=1)
    for a, b in zip(path, path[1:]):
        low, high = np.minimum(a, b) - 1e-7, np.maximum(a, b) + 1e-7
        ids = np.flatnonzero(np.all(highs >= low, axis=1) & np.all(lows <= high, axis=1))
        if not segment_on_mesh(a, b, points, [mesh.faces[int(i)] for i in ids], 1e-7):
            return False
    return True


def fail(message):
    raise SystemExit(f'set_start_goal: {message}')


def relative(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def point(values, label):
    if values is None or len(values) != 3:
        fail(f'{label} needs three coordinates')
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        fail(f'{label} contains a non-finite coordinate')
    return result


def load_mission(path):
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        fail(f'cannot read mission file {path}: {error}')
    if not isinstance(payload, dict):
        fail(f'mission file {path} must contain an object')
    name = payload.get('name')
    has_start = 'start' in payload
    has_start_vertex = 'start_vertex' in payload
    if has_start == has_start_vertex:
        fail('mission needs exactly one of "start" or "start_vertex"')
    start = point(payload['start'], 'mission start') if has_start else None
    start_vertex = payload.get('start_vertex')
    if start_vertex is not None and (not isinstance(start_vertex, int) or start_vertex < 0):
        fail('mission start_vertex must be a non-negative integer')
    all_goals = bool(payload.get('all_goals', False))
    goal_vertices = payload.get('goal_vertices') or []
    goals = payload.get('goals') or []
    if all_goals and (goals or goal_vertices):
        fail('mission all_goals cannot be combined with goals or goal_vertices')
    if not all_goals and not goals and not goal_vertices:
        fail('mission needs goals, goal_vertices or all_goals')
    parsed = []
    for number, item in enumerate(goals, 1):
        if isinstance(item, dict):
            parsed.append((str(item.get('id', f'g{number}')),
                           point(item.get('point'), f'mission goal {number}')))
        else:
            parsed.append((f'g{number}', point(item, f'mission goal {number}')))
    if not all(isinstance(value, int) and value >= 0 for value in goal_vertices):
        fail('mission goal_vertices must be non-negative integers')
    return dict(name=name, start=start, start_vertex=start_vertex,
                goals=parsed, goal_vertices=goal_vertices, all_goals=all_goals)


def vertex_spacing(vertices):
    xs = np.unique(np.round(vertices[:, 0], 6))
    spacing = np.diff(xs)
    spacing = spacing[spacing > 1e-6]
    return float(np.median(spacing)) if len(spacing) else 5.


def snap(vertices, target, mode, max_snap, label):
    delta = vertices - np.array(target)
    planar = np.linalg.norm(delta[:, :2], axis=1)
    total = np.linalg.norm(delta, axis=1)
    metric = planar if mode == 'xy' else total
    index = int(metric.argmin())
    result = dict(input=list(target), vertex=index,
                  snapped=[round(float(value), 6) for value in vertices[index]],
                  snap_metric=float(metric[index]),
                  snap_xy=float(planar[index]),
                  snap_z=float(abs(delta[index, 2])),
                  snap_total=float(total[index]))
    if result['snap_metric'] > max_snap + 1e-9:
        fail(f'{label} is {result["snap_metric"]:.3f} from the nearest vertex, '
             f'more than --max-snap {max_snap:.3f}; pass a larger value if intended')
    return result


def vertex_start(vertices, index, label):
    if not 0 <= index < len(vertices):
        fail(f'{label} {index} is outside 0..{len(vertices) - 1}')
    return dict(input=[round(float(value), 6) for value in vertices[index]],
                vertex=index,
                snapped=[round(float(value), 6) for value in vertices[index]],
                snap_metric=0., snap_xy=0., snap_z=0., snap_total=0.)


def signature(mesh_path, source, targets):
    digest = hashlib.sha256()
    digest.update(Path(mesh_path).read_bytes())
    for relative in PROVENANCE:
        digest.update((ROOT / relative).read_bytes())
    digest.update(json.dumps([source, sorted(targets)]).encode())
    return digest.hexdigest()


def solve_goal(mesh, vertices, source, goal, targets, cache, cache_path, seconds):
    if source == goal:
        return [tuple(vertices[source])], [source], dict(nodes=0, clip_events=0,
                                                         deleted_children=0, levels=0)
    costs, previous, settled = {source: 0.}, {}, set()
    heuristic = np.linalg.norm(vertices - vertices[goal], axis=1)
    queue = [(float(heuristic[source]), 0., source)]
    while queue:
        _, cost, current = heapq.heappop(queue)
        if current in settled:
            continue
        if current == goal:
            points, chain = candidate_route(mesh, source, goal, previous)
            return points, chain, dict(settled_sources=len(settled),
                                       cached_sources_used=len(cache['runs']))
        key = str(current)
        if key not in cache['runs']:
            print(f'  propagating source {current} ({cost:.2f})', flush=True)
            deadline = time.monotonic() + seconds
            distances, best, stats = propagate(mesh, current, deadline, 200000, True,
                                               target_vertices=targets - {current})
            edges = {}
            for target in sorted(targets - {current}):
                if best[target] is None:
                    continue
                path = reconstruct(mesh, current, best[target], deadline=deadline)
                length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
                if abs(length - distances[target]) > 1e-6 * max(1., length):
                    raise ValueError('Funnel reconstruction length mismatch')
                edges[str(target)] = dict(length=length, path=path)
            cache['runs'][key] = dict(edges=edges, stats=stats)
            write_json(cache_path, cache)
        settled.add(current)
        for target, edge in cache['runs'][key]['edges'].items():
            target = int(target)
            total = cost + edge['length']
            if target not in settled and total < costs.get(target, math.inf):
                costs[target] = total
                previous[target] = (current, edge)
                heapq.heappush(queue, (total + heuristic[target], total, target))
    raise ValueError(f'Funnel did not reach goal vertex {goal}')


def solve_all(mesh, vertices, source, seconds):
    count = len(vertices)
    if count > 300:
        fail('--all-goals is intended for small fixture meshes; pass explicit '
             '--goal points for large surfaces')
    targets = set(range(count))
    costs, previous, settled, runs = {source: 0.}, {}, set(), {}
    queue = [(0., source)]
    stats = dict(source_runs=0, nodes=0, clip_events=0, deleted_children=0, levels=0)
    while queue:
        cost, current = heapq.heappop(queue)
        if current in settled or cost > costs.get(current, math.inf) + 1e-12:
            continue
        settled.add(current)
        if current not in runs:
            print(f'  propagating source {current} ({cost:.2f})', flush=True)
            deadline = time.monotonic() + seconds
            distances, best, run_stats = propagate(mesh, current, deadline, 200000, True,
                                                   target_vertices=targets - {current})
            edges = {}
            for target in sorted(targets - {current}):
                if best[target] is None:
                    continue
                path = reconstruct(mesh, current, best[target], deadline=deadline)
                length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
                if abs(length - distances[target]) > 1e-6 * max(1., length):
                    raise ValueError('Funnel reconstruction length mismatch')
                edges[target] = dict(length=length, path=path)
            runs[current] = edges
            stats['source_runs'] += 1
            for key in ('nodes', 'clip_events', 'deleted_children', 'levels'):
                stats[key] += run_stats.get(key, 0)
        for target, edge in runs[current].items():
            total = cost + edge['length']
            if target not in settled and total < costs.get(target, math.inf):
                costs[target] = total
                previous[target] = (current, edge)
                heapq.heappush(queue, (total, target))
    results = []
    for index in range(count):
        if index == source:
            point = (float(vertices[index][0]), float(vertices[index][1]), float(vertices[index][2]))
            results.append((index, 0., [point, point]))
        elif index in previous:
            path, chain = candidate_route(mesh, source, index, previous)
            results.append((index, costs[index], simplify(path)))
    return results, stats


def route_length(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def verify_segments(mesh, coordinates, paths):
    triangles = np.array(coordinates)[np.array(mesh.faces)]
    lows, highs = triangles.min(axis=1), triangles.max(axis=1)
    checked = set()
    for path in paths:
        for a, b in zip(path, path[1:]):
            if math.dist(a, b) < 1e-12:
                continue
            key = tuple(round(value, 9) for point3 in (a, b) for value in point3)
            if key in checked:
                continue
            checked.add(key)
            low, high = np.minimum(a, b) - 1e-7, np.maximum(a, b) + 1e-7
            ids = np.flatnonzero(np.all(highs >= low, axis=1) & np.all(lows <= high, axis=1))
            if not segment_on_mesh(a, b, coordinates, [mesh.faces[int(i)] for i in ids], 1e-7):
                return False, len(checked)
    return True, len(checked)


def render(vertices, faces, start, routes, output, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(10, 9))
    axes = figure.add_subplot(111, projection='3d')
    axes.plot_trisurf(vertices[:, 0], vertices[:, 1], vertices[:, 2], triangles=faces,
                      cmap='viridis', linewidth=0., alpha=0.55)
    axes.scatter(*vertices[start['vertex']], color='#167a40', s=80, depthshade=False,
                 label='START', zorder=5)
    for number, route in enumerate(routes):
        path = np.array(route['surface_waypoints'])
        colour = COLOURS[number % len(COLOURS)]
        axes.plot(path[:, 0], path[:, 1], path[:, 2], color=colour, linewidth=1.6,
                  label=route.get('label'))
        axes.scatter(*path[-1], color=colour, marker='*', s=120, depthshade=False, zorder=5)
    span = vertices.max(axis=0) - vertices.min(axis=0)
    axes.set_box_aspect(tuple(float(value) or 1. for value in span))
    axes.set_xlabel('X')
    axes.set_ylabel('Y')
    axes.set_zlabel('Z')
    axes.set_title(title)
    if len(routes) <= 12:
        axes.legend(loc='upper left')
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150, bbox_inches='tight')
    plt.close(figure)
    return output


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mesh', type=Path, default=DEFAULT_MESH,
                        help='Triangulated navigation surface (.off)')
    parser.add_argument('--start', nargs=3, type=float, metavar=('X', 'Y', 'Z'),
                        help='START point in surface coordinates')
    parser.add_argument('--start-vertex', type=int, metavar='N',
                        help='START vertex index, as drawn by data_viz.py')
    parser.add_argument('--goal', nargs=3, type=float, action='append',
                        metavar=('X', 'Y', 'Z'),
                        help='GOAL point; repeat for several goals')
    parser.add_argument('--goal-vertex', type=int, action='append', metavar='N',
                        help='GOAL vertex index; repeat for several goals')
    parser.add_argument('--all-goals', action='store_true',
                        help='Use every other vertex as a goal')
    parser.add_argument('--mission', type=Path,
                        help='JSON mission with name, start/start_vertex and goals')
    parser.add_argument('--name', help='Mission name; defaults to <mesh>-v<start>')
    parser.add_argument('--snap', choices=('xy', '3d'), default='xy',
                        help='Snap coordinates in the XY plane (default) or in 3D')
    parser.add_argument('--max-snap', type=float,
                        help='Reject points farther than this from a vertex '
                             '(default: half a grid diagonal)')
    parser.add_argument('--seconds', type=float, default=30.,
                        help='Time limit for one source propagation')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                        help='Base folder for generated missions')
    parser.add_argument('--no-paths', action='store_true',
                        help='With --all-goals, skip the per-vertex .paths.json')
    parser.add_argument('--no-png', action='store_true', help='Skip the route image')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite an existing plan.json')
    args = parser.parse_args()

    if args.mission and (args.start is not None or args.start_vertex is not None or
                         args.goal or args.goal_vertex or args.all_goals):
        fail('use either --mission or the START/GOAL options, not both')
    if args.start and args.start_vertex is not None:
        fail('use either --start or --start-vertex, not both')
    if args.all_goals and (args.goal or args.goal_vertex):
        fail('--all-goals cannot be combined with --goal or --goal-vertex')

    if args.mission:
        mission = load_mission(args.mission)
        name = args.name or mission['name']
        start_point, start_vertex = mission['start'], mission['start_vertex']
        goals, goal_vertices = mission['goals'], mission['goal_vertices']
        all_goals = mission['all_goals']
    else:
        name = args.name
        start_point, start_vertex = args.start, args.start_vertex
        goals = [(f'g{number}', point(values, f'--goal {number}'))
                 for number, values in enumerate(args.goal or [], 1)]
        goal_vertices = args.goal_vertex or []
        all_goals = args.all_goals
    if not all_goals and not goals and not goal_vertices:
        fail('pass --goal, --goal-vertex or --all-goals')

    mesh_path = args.mesh.resolve()
    if not mesh_path.is_file():
        fail(f'missing mesh {mesh_path}; run "python3 main.py data" first')
    mesh = read_off(mesh_path)
    vertices = np.array([(p.x, p.y, p.z) for p in mesh.points])
    faces = np.array(mesh.faces)
    cell = vertex_spacing(vertices)
    max_snap = args.max_snap if args.max_snap is not None else cell * math.sqrt(2.) / 2.
    if args.seconds <= 0 or not math.isfinite(args.seconds):
        fail('--seconds must be positive and finite')

    if start_vertex is not None:
        start = vertex_start(vertices, start_vertex, '--start-vertex')
    elif start_point is not None:
        start = snap(vertices, start_point, args.snap, max_snap, 'START')
    else:
        fail('pass --start X Y Z or --start-vertex N')
    source = start['vertex']
    name = name or f'{mesh_path.stem}-v{source}'
    if not re.fullmatch(r'[A-Za-z0-9._-]+', name):
        fail(f'mission name {name!r} must match [A-Za-z0-9._-]+')

    snapped = []
    for identifier, target in goals:
        record = snap(vertices, target, args.snap, max_snap, f'GOAL {identifier}')
        record['id'] = identifier
        snapped.append(record)
    for index in goal_vertices:
        record = vertex_start(vertices, index, '--goal-vertex')
        record['id'] = f'v{index}'
        snapped.append(record)
    uses_coordinates = start_point is not None or bool(goals)
    goals = snapped
    for number, goal in enumerate(goals):
        if goal['vertex'] == source:
            fail(f'GOAL {goal["id"]} is the START vertex')
        if any(goal['vertex'] == other['vertex'] for other in goals[:number]):
            fail(f'GOAL {goal["id"]} repeats another goal vertex')

    output = args.output / name
    plan_path = output / 'plan.json'
    if plan_path.exists() and not args.force:
        fail(f'{plan_path} exists; pass --force to overwrite')
    output.mkdir(parents=True, exist_ok=True)
    coordinates = vertices.tolist()
    grid = f', grid {cell:g}' if uses_coordinates else ''
    print(f'Mesh: {relative(mesh_path)} — {len(vertices)} vertices, '
          f'{len(faces)} triangles{grid}', flush=True)
    print(f'START: vertex {source} {start["snapped"]}'
          + (f' (snap {start["snap_metric"]:.3f})' if start['snap_metric'] else ''),
          flush=True)

    plan = dict(name=name, mesh=str(relative(mesh_path)),
                mesh_sha256=hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
                mesh_vertices=len(vertices), mesh_faces=len(faces),
                vertex_spacing=cell, max_snap=max_snap, snap_mode=args.snap,
                start=start,
                input_sha256={filename: hashlib.sha256(
                                  (ROOT / filename).read_bytes()).hexdigest()
                              for filename in PROVENANCE},
                optimality_certified=False,
                note='START and GOAL snap to surface vertices; the snapped z is the '
                     'envelope height, not the input height.')

    if all_goals:
        started = time.monotonic()
        try:
            results, stats = solve_all(mesh, vertices, source, args.seconds)
        except (ValueError, TimeoutError, RuntimeError) as error:
            fail(f'all-goals: {error}')
        paths = [path for _, _, path in results]
        ok, checked = verify_segments(mesh, coordinates, paths)
        if not ok:
            fail('all-goals: a Funnel route leaves the surface')
        longest = sorted(results, key=lambda item: item[1], reverse=True)
        shown = longest if len(longest) <= 60 else longest[:40]
        routes = [dict(label=f'vertex {index} — {distance:.2f}',
                       surface_waypoints=[list(point) for point in path])
                  for index, distance, path in shown]
        reached = sum(1 for index, _, _ in results if index != source)
        goals_only = [distance for index, distance, _ in results if index != source]
        plan.update(mode='all-goals',
                    goals=dict(count=len(vertices) - 1, reached=reached,
                               unreached=len(vertices) - 1 - reached,
                               max_distance=float(max(goals_only, default=0.)),
                               mean_distance=float(np.mean(goals_only)) if goals_only else 0.),
                    vertices=[dict(vertex=index, distance=distance)
                              for index, distance, _ in results],
                    segments_checked=checked, stats=stats,
                    planning_seconds=round(time.monotonic() - started, 3))
        if not args.no_paths:
            payload = dict(mesh=str(relative(mesh_path)), source=source,
                           coordinate_system='mesh coordinates; one path per reached goal vertex',
                           vertices=[index for index, _, _ in results],
                           paths=[[list(point) for point in path] for path in paths])
            write_json(output / f'{name}.paths.json', payload)
            print(f'Save at: {output / f"{name}.paths.json"}')
        print(f'{reached}/{len(vertices) - 1} goal vertices reached, '
              f'{checked} segments checked, {plan["planning_seconds"]:.1f}s', flush=True)
        title = f'{reached} routes from vertex {source}'
    else:
        targets = set(secondary_sources(mesh, source)) | {goal['vertex'] for goal in goals}
        cache_path = output / 'funnel_cache.json'
        cache = dict(signature=signature(mesh_path, source, targets), runs={})
        if cache_path.exists():
            saved = json.loads(cache_path.read_text(encoding='utf-8'))
            if saved.get('signature') == cache['signature']:
                cache = saved
            else:
                print('Cache signature changed; starting a new source graph', flush=True)
        results = []
        for goal in goals:
            print(f'Planning {goal["id"]} (vertex {goal["vertex"]}, '
                  f'snap {goal["snap_metric"]:.3f}) ...', flush=True)
            started = time.monotonic()
            try:
                path, chain, stats = solve_goal(mesh, vertices, source, goal['vertex'],
                                                targets, cache, cache_path, args.seconds)
            except (ValueError, TimeoutError, RuntimeError) as error:
                fail(f'{goal["id"]}: {error}')
            path = simplify(path)
            if not verify(mesh, coordinates, path):
                fail(f'{goal["id"]}: Funnel route leaves the surface')
            waypoints = simplify([list(start['input']), *path])
            record = dict(goal, surface_waypoints=[list(point) for point in path],
                          waypoints=[list(point) for point in waypoints],
                          label=f'{goal["id"]} — {route_length(waypoints):.1f}',
                          surface_length=route_length(path),
                          flight_length=route_length(waypoints),
                          source_chain=chain, stats=stats,
                          planning_seconds=round(time.monotonic() - started, 3))
            results.append(record)
            print(f'{goal["id"]}: {len(path)} surface points, '
                  f'{record["flight_length"]:.2f} long, {record["planning_seconds"]:.1f}s',
                  flush=True)
            write_json(cache_path, cache)
        plan.update(mode='explicit', goals=results,
                    cache=dict(signature=cache['signature'], source_runs=len(cache['runs'])))
        title = f'{len(results)} goal(s) from vertex {source}'

    write_json(plan_path, plan)
    print(f'Save at: {plan_path}')
    if not args.no_png:
        image = render(vertices, faces, start, routes if all_goals else results,
                       output / 'routes.png', title)
        print(f'Save at: {image}')


if __name__ == '__main__':
    main()
