#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, hashlib, json, math, sys,
# pathlib, xml.etree.ElementTree); local modules (glb2off, mesh_glb, mesh_off).
"""Build the Gazebo world and meshes for one planned Funnel route.

Input:  generated/routes/<mission>.json      (stage plan)
        data/processed/meshes/...off         (the surface named in the route)
        data/processed/scenes/city.standardized.glb   (or --scene)
Output: generated/simulate/<mission>-<goal>/
          city.sim.glb               Z-up visual
          city.sim.collision.stl     decimated collision mesh
          surface.stl                optional visual of the envelope
          funnel_physics.sdf
          route.json                 route in the plugin's schema
          world_metadata.json        hashes and counts of this build

The city visual is a Z-up GLB: Gazebo does not rotate glTF from Y-up, so the
standardized scene (Y-up) cannot be used directly. Collision uses a vertex
clustered STL so the static mesh stays cheap; --collision full keeps every
triangle.

--goal is fail-closed: a route with several goals needs an explicit id, because
one Gazebo session flies one route.

Examples:
  .venv/bin/python tools/simulate/build_world.py --mission city.standardized.triangulation --goal g1
  .venv/bin/python tools/simulate/build_world.py --mission cliff --list-goals
  .venv/bin/python tools/simulate/build_world.py --mission city.standardized.triangulation --goal g1 --check
"""
import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT / 'tools/data'))
from mesh_glb import write_glb
from mesh_off import read_off
from glb2off import read_glb_scene

DEFAULT_ROUTES = ROOT / 'generated/routes'
DEFAULT_OUTPUT = ROOT / 'generated/simulate'
DEFAULT_SCENE = ROOT / 'data/processed/scenes/city.standardized.glb'
SPEED = 5.
MAX_ACCELERATION = 3.
START_DELAY = 2.
DWELL = 1.5


def fail(message):
    raise SystemExit(f'build_world: {message}')


def relative(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def triangle_areas(points, faces):
    triangles = points[faces]
    return np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0],
                                   triangles[:, 2] - triangles[:, 0]), axis=1) / 2


def write_stl(path, points, faces):
    """Write a binary STL; reject degenerate triangles."""
    points = np.asarray(points, dtype=float)
    faces = np.asarray(faces, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3:
        fail('write_stl: points must be Nx3 and faces Mx3')
    if not np.isfinite(points).all():
        fail('write_stl: non-finite vertex coordinate')
    if faces.min() < 0 or faces.max() >= len(points):
        fail('write_stl: face index outside the vertex array')
    triangles = points[faces]
    degenerate = int((triangle_areas(points, faces) <= 1e-12).sum())
    if degenerate:
        fail(f'write_stl: {degenerate} degenerate triangles')
    normals = np.cross(triangles[:, 1] - triangles[:, 0],
                       triangles[:, 2] - triangles[:, 0])
    length = np.linalg.norm(normals, axis=1)
    normals /= np.maximum(length[:, None], 1e-30)
    records = np.zeros(len(faces), dtype=[('normal', '<f4', (3,)),
                                          ('vertices', '<f4', (3, 3)),
                                          ('attribute', '<u2')])
    records['normal'] = normals
    records['vertices'] = triangles
    with Path(path).open('wb') as handle:
        handle.write(b'Gazebo collision mesh; attribution in ATTRIBUTION.md'.ljust(80, b' '))
        handle.write(np.array([len(faces)], dtype='<u4').tobytes())
        handle.write(records.tobytes())
    return len(faces)


def decimate(points, faces, cell):
    """Vertex clustering: snap vertices to a grid and drop the collapsed faces."""
    if not (cell > 0 and math.isfinite(cell)):
        fail('decimate: cell must be positive and finite')
    points = np.asarray(points, dtype=float)
    faces = np.asarray(faces, dtype=np.int64)
    keys = np.floor(points / cell).astype(np.int64)
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    sums = np.zeros((len(unique), 3))
    counts = np.zeros(len(unique))
    np.add.at(sums, inverse, points)
    np.add.at(counts, inverse, 1)
    clustered = sums / counts[:, None]
    mapped = inverse[faces]
    keep = ((mapped[:, 0] != mapped[:, 1]) & (mapped[:, 1] != mapped[:, 2])
            & (mapped[:, 0] != mapped[:, 2]))
    mapped = mapped[keep]
    if not len(mapped):
        fail('decimate: every triangle collapsed; use a smaller cell')
    key = np.sort(mapped, axis=1)
    _, first = np.unique(key, axis=0, return_index=True)
    mapped = mapped[np.sort(first)]
    areas = triangle_areas(clustered, mapped)
    mapped = mapped[areas > 1e-12]
    if not len(mapped):
        fail('decimate: every triangle became degenerate; use a smaller cell')
    used = np.unique(mapped)
    remap = np.full(len(clustered), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    stats = {'faces_before': int(len(faces)), 'faces_after': int(len(mapped)),
             'vertices_before': int(len(points)), 'vertices_after': int(len(used)),
             'cell': cell}
    return clustered[used], remap[mapped], stats


def simplify(points, tolerance):
    """Douglas-Peucker on the 3D polyline; keeps the path within tolerance."""
    if tolerance <= 0 or len(points) < 3:
        return [tuple(map(float, point)) for point in points]

    def recurse(segment):
        first, last = segment[0], segment[-1]
        ab = [last[i] - first[i] for i in range(3)]
        length2 = sum(value * value for value in ab)
        best, index = -1., 0
        for position in range(1, len(segment) - 1):
            ap = [segment[position][i] - first[i] for i in range(3)]
            if length2 < 1e-18:
                distance = math.sqrt(sum(value * value for value in ap))
            else:
                t = sum(ap[i] * ab[i] for i in range(3)) / length2
                t = max(0., min(1., t))
                projection = [first[i] + t * ab[i] for i in range(3)]
                distance = math.dist(segment[position], projection)
            if distance > best:
                best, index = distance, position
        if best <= tolerance:
            return [first, last]
        left = recurse(segment[:index + 1])
        right = recurse(segment[index:])
        return left[:-1] + right

    return recurse([tuple(map(float, point)) for point in points])


def load_route(path):
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(record, dict) or not record.get('routes'):
        fail(f'{path}: not a route file; run tools/plan/run_funnel.py')
    return record


def choose_goal(record, goal):
    routes = {route['id']: route for route in record['routes']}
    if goal is None:
        if len(routes) != 1:
            lines = '\n'.join(f'  {identifier}  vertex {route["vertex"]}  '
                              f'{route["length"]:.2f} m'
                              for identifier, route in routes.items())
            fail(f'this route has {len(routes)} goals; pass --goal\n{lines}')
        goal = next(iter(routes))
        print(f'Only one route: using --goal {goal}', flush=True)
    if goal not in routes:
        lines = ', '.join(f'{identifier} ({route["length"]:.2f} m)'
                          for identifier, route in routes.items())
        fail(f'unknown goal {goal!r}; available: {lines}')
    route = routes[goal]
    waypoints = route.get('waypoints') or []
    if len(waypoints) < 2:
        fail(f'goal {goal} has fewer than two waypoints')
    return goal, route['vertex'], waypoints


def world_name(mission, goal):
    stem = ''.join(character if character.isalnum() else '_'
                   for character in f'{mission}_{goal}')
    return f'funnel_sim_{stem}'


def build_meshes(scene, surface, out, collision_cell, full_collision,
                 visual_format, with_surface):
    vertices, faces = read_glb_scene(scene, 200.)
    # The source scene carries a few zero-area slivers; they cannot be written
    # to STL and carry no collision, so drop them once for both meshes.
    areas = triangle_areas(vertices, faces)
    degenerate = areas <= 1e-12
    if degenerate.any():
        print(f'Dropped {int(degenerate.sum())} degenerate city triangles', flush=True)
        faces = faces[~degenerate]
    visual = out / ('city.sim.glb' if visual_format == 'glb' else 'city.sim.stl')
    if visual_format == 'glb':
        write_glb(visual, [{'name': 'city', 'vertices': vertices, 'faces': faces}],
                  extras={'frame': 'Z-up, width 200 m', 'source_sha256': sha256(scene),
                          'vertices': int(len(vertices)), 'triangles': int(len(faces)),
                          'policy': 'visual only; collision uses a separate STL'},
                  generator='uav-funnel-tree-gazebo build_world')
        visual_triangles = len(faces)
    else:
        visual_triangles = write_stl(visual, vertices, faces)

    if full_collision:
        collision_points, collision_faces = vertices, faces
        collision_stats = {'faces_before': int(len(faces)), 'faces_after': int(len(faces)),
                           'vertices_before': int(len(vertices)),
                           'vertices_after': int(len(vertices)), 'cell': None}
    else:
        collision_points, collision_faces, collision_stats = decimate(
            vertices, faces, collision_cell)
    collision = out / 'city.sim.collision.stl'
    write_stl(collision, collision_points, collision_faces)

    surface_stl = None
    if with_surface:
        points, surface_faces = read_off(surface)
        surface_stl = out / 'surface.stl'
        write_stl(surface_stl, points, surface_faces)

    return {'visual': visual, 'visual_triangles': int(visual_triangles),
            'collision': collision, 'collision_stats': collision_stats,
            'surface_stl': surface_stl}


def build_route(record, goal, vertex, waypoints, world):
    payload = {
        'mission': record['mission'],
        'goal': goal,
        'goal_vertex': vertex,
        'world': world,
        'waypoints': [[float(value) for value in point] for point in waypoints],
        'speed': SPEED,
        'max_acceleration': MAX_ACCELERATION,
        'start_delay': START_DELAY,
        'dwell': DWELL,
    }
    return payload


def mesh_element(parent, uri, scale=None):
    geometry = ET.SubElement(parent, 'geometry')
    mesh = ET.SubElement(geometry, 'mesh')
    ET.SubElement(mesh, 'uri').text = uri
    if scale is not None:
        ET.SubElement(mesh, 'scale').text = scale
    return mesh


def build_sdf(out, world, route, meshes, surface_stl):
    root = ET.Element('sdf', version='1.9')
    world_element = ET.SubElement(root, 'world', name=world)
    physics = ET.SubElement(world_element, 'physics', name='1ms', type='ignored')
    ET.SubElement(physics, 'max_step_size').text = '0.001'
    ET.SubElement(physics, 'real_time_factor').text = '1.0'
    ET.SubElement(world_element, 'plugin', filename='gz-sim-physics-system',
                  name='gz::sim::systems::Physics')
    ET.SubElement(world_element, 'plugin', filename='gz-sim-user-commands-system',
                  name='gz::sim::systems::UserCommands')
    ET.SubElement(world_element, 'plugin', filename='gz-sim-scene-broadcaster-system',
                  name='gz::sim::systems::SceneBroadcaster')
    scene = ET.SubElement(world_element, 'scene')
    ET.SubElement(scene, 'ambient').text = '0.6 0.6 0.6 1'
    ET.SubElement(scene, 'background').text = '0.72 0.81 0.9 1'
    ET.SubElement(scene, 'shadows').text = 'true'

    city = ET.SubElement(world_element, 'model', name='city')
    ET.SubElement(city, 'static').text = 'true'
    link = ET.SubElement(city, 'link', name='link')
    collision = ET.SubElement(link, 'collision', name='collision')
    mesh_element(collision, meshes['collision'].as_uri())
    visual = ET.SubElement(link, 'visual', name='visual')
    mesh_element(visual, meshes['visual'].as_uri())
    material = ET.SubElement(visual, 'material')
    ET.SubElement(material, 'ambient').text = '0.55 0.58 0.6 1'
    ET.SubElement(material, 'diffuse').text = '0.62 0.65 0.66 1'

    if surface_stl is not None:
        envelope = ET.SubElement(world_element, 'model', name='navigation_surface')
        ET.SubElement(envelope, 'static').text = 'true'
        envelope_link = ET.SubElement(envelope, 'link', name='link')
        envelope_visual = ET.SubElement(envelope_link, 'visual', name='visual')
        mesh_element(envelope_visual, surface_stl.as_uri())
        envelope_material = ET.SubElement(envelope_visual, 'material')
        ET.SubElement(envelope_material, 'ambient').text = '0.2 0.7 0.4 0.35'
        ET.SubElement(envelope_material, 'diffuse').text = '0.2 0.7 0.4 0.35'

    start = route['waypoints'][0]
    drone = ET.SubElement(world_element, 'model', name='drone')
    ET.SubElement(drone, 'pose').text = ' '.join(f'{value:.6f}' for value in
                                                 [start[0], start[1], start[2], 0., 0., 0.])
    body = ET.SubElement(drone, 'link', name='body')
    ET.SubElement(body, 'gravity').text = 'true'
    inertial = ET.SubElement(body, 'inertial')
    ET.SubElement(inertial, 'mass').text = '1.0'
    inertia = ET.SubElement(inertial, 'inertia')
    for key in ('ixx', 'iyy', 'izz'):
        ET.SubElement(inertia, key).text = '0.01'
    for key in ('ixy', 'ixz', 'iyz'):
        ET.SubElement(inertia, key).text = '0.0'

    body_collision = ET.SubElement(body, 'collision', name='body_collision')
    box = ET.SubElement(ET.SubElement(body_collision, 'geometry'), 'box')
    ET.SubElement(box, 'size').text = '0.9 0.6 0.25'
    body_visual = ET.SubElement(body, 'visual', name='body_visual')
    box = ET.SubElement(ET.SubElement(body_visual, 'geometry'), 'box')
    ET.SubElement(box, 'size').text = '0.9 0.6 0.25'
    body_material = ET.SubElement(body_visual, 'material')
    ET.SubElement(body_material, 'ambient').text = '0.85 0.15 0.15 1'
    ET.SubElement(body_material, 'diffuse').text = '0.9 0.2 0.2 1'

    locator = ET.SubElement(body, 'visual', name='locator')
    ET.SubElement(locator, 'pose').text = '0 0 2.1 0 0 0'
    sphere = ET.SubElement(ET.SubElement(locator, 'geometry'), 'sphere')
    ET.SubElement(sphere, 'radius').text = '0.5'
    locator_material = ET.SubElement(locator, 'material')
    ET.SubElement(locator_material, 'emissive').text = '0.8 0.02 0.6 1'

    plugin = ET.SubElement(drone, 'plugin',
                           filename='gz-sim-python-system-loader-system',
                           name='gz::sim::systems::PythonSystemLoader')
    ET.SubElement(plugin, 'module_name').text = 'funnel_drone_system'

    ET.indent(root)
    path = out / 'funnel_physics.sdf'
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    return path


def check_world(out, route_record, meshes):
    sdf_path = out / 'funnel_physics.sdf'
    if not sdf_path.is_file():
        fail(f'{relative(sdf_path)} is missing')
    root = ET.parse(sdf_path).getroot()
    world = root.find('world')
    if world is None:
        fail('SDF has no world element')
    for name in ('city', 'drone'):
        if world.find(f"model[@name='{name}']") is None:
            fail(f'SDF has no model {name}')
    plugin = world.find("model[@name='drone']/plugin")
    if plugin is None or plugin.findtext('module_name') != 'funnel_drone_system':
        fail('SDF is missing the Python system plugin')
    uris = [element.text for element in root.iter('uri')]
    if not uris:
        fail('SDF has no mesh URI')
    for uri in uris:
        if not uri.startswith('file://'):
            fail(f'SDF mesh URI is not absolute: {uri}')
        mesh_path = Path(uri[len('file://'):])
        if not mesh_path.is_file():
            fail(f'SDF mesh does not exist: {mesh_path}')
    route_path = out / 'route.json'
    payload = json.loads(route_path.read_text(encoding='utf-8'))
    waypoints = payload.get('waypoints') or []
    if len(waypoints) < 2:
        fail('route.json has fewer than two waypoints')
    if payload['world'] != world.get('name'):
        fail('route.json world does not match the SDF world')
    if payload['mission'] != route_record['mission']:
        fail('route.json mission does not match the plan record')
    header = np.fromfile(meshes['collision'], dtype='<u4', count=1, offset=80)
    expected = 84 + 50 * int(header[0])
    if meshes['collision'].stat().st_size != expected:
        fail('collision STL size does not match its triangle count')
    print('check: SDF, URIs, route.json and collision STL are consistent')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mission', help='Route stem, e.g. city.standardized.triangulation')
    parser.add_argument('--route', type=Path, help='Route JSON path (overrides --mission)')
    parser.add_argument('--goal', help='Goal id inside the route file')
    parser.add_argument('--list-goals', action='store_true',
                        help='Print the goals of the route and exit')
    parser.add_argument('--scene', type=Path, default=DEFAULT_SCENE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--collision-grid', type=float, default=1.0, metavar='M',
                        help='Vertex clustering cell for collision (default: 1.0 m)')
    parser.add_argument('--collision', choices=('decimated', 'full'), default='decimated')
    parser.add_argument('--visual', choices=('glb', 'stl'), default='glb')
    parser.add_argument('--simplify', type=float, default=0.1, metavar='M',
                        help='Douglas-Peucker tolerance for the route in metres '
                             '(default: 0.1; 0 disables)')
    parser.add_argument('--surface', action='store_true',
                        help='Also write surface.stl as a visual of the envelope')
    parser.add_argument('--check', action='store_true',
                        help='Validate an existing build instead of writing one')
    args = parser.parse_args()

    if args.route is not None:
        route_path = args.route.resolve()
    elif args.mission:
        route_path = (DEFAULT_ROUTES / f'{args.mission}.json').resolve()
    else:
        parser.error('pass --mission or --route')
    if not route_path.is_file():
        fail(f'missing route {route_path}; run "python3 main.py plan" first')
    record = load_route(route_path)

    if args.list_goals:
        print(f'{relative(route_path)} — {len(record["routes"])} goal(s):')
        for route in record['routes']:
            print(f'  {route["id"]:4s} vertex {route["vertex"]:>6}  {route["length"]:.2f} m')
        return

    goal, goal_vertex, waypoints = choose_goal(record, args.goal)
    original_waypoints = len(waypoints)
    if args.simplify < 0 or not math.isfinite(args.simplify):
        parser.error('--simplify must be zero or positive and finite')
    waypoints = simplify(waypoints, args.simplify)
    mission = Path(record['mission']).stem
    out = args.output / f'{mission}-{goal}'

    surface = (ROOT / record['mesh']).resolve()
    if not surface.is_file():
        fail(f'missing surface {relative(surface)}')
    if sha256(surface) != record['mesh_sha256']:
        fail(f'{relative(surface)} changed since the route was planned')
    if not args.scene.is_file():
        fail(f'missing scene {args.scene}')

    if args.check:
        meshes = {
            'visual': out / ('city.sim.glb' if args.visual == 'glb' else 'city.sim.stl'),
            'collision': out / 'city.sim.collision.stl',
        }
        if not meshes['visual'].is_file():
            fail(f'{relative(meshes["visual"])} is missing')
        check_world(out, record, meshes)
        return

    if args.collision_grid <= 0 or not math.isfinite(args.collision_grid):
        parser.error('--collision-grid must be positive and finite')
    out.mkdir(parents=True, exist_ok=True)
    world = world_name(mission, goal)
    meshes = build_meshes(args.scene, surface, out, args.collision_grid,
                          args.collision == 'full', args.visual, args.surface)
    payload = build_route(record, goal, goal_vertex, waypoints, world)
    (out / 'route.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    sdf = build_sdf(out, world, payload, meshes, meshes['surface_stl'])

    metadata = {
        'mission': record['mission'],
        'goal': goal,
        'goal_vertex': goal_vertex,
        'route_file': str(relative(route_path)),
        'route_sha256': sha256(route_path),
        'surface': str(relative(surface)),
        'surface_sha256': record['mesh_sha256'],
        'scene': str(relative(args.scene)),
        'scene_sha256': sha256(args.scene),
        'world': world,
        'visual_format': args.visual,
        'collision_mode': args.collision,
        'collision_stats': meshes['collision_stats'],
        'waypoints': len(waypoints),
        'waypoints_before_simplify': original_waypoints,
        'simplify_tolerance': args.simplify,
        'waypoint_length': round(sum(math.dist(a, b) for a, b in
                                      zip(waypoints, waypoints[1:])), 6),
        'model': '1 kg point mass with force feedback; box body collision; decorative rotors',
        'frame': 'Z-up, width 200 m',
    }
    (out / 'world_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n',
                                             encoding='utf-8')

    print(f'Mission {mission}, goal {goal} (vertex {goal_vertex})')
    print(f'Route: {original_waypoints} -> {len(waypoints)} waypoints '
          f'(simplify {args.simplify:g} m), {metadata["waypoint_length"]:.2f} m')
    print(f'Visual: {relative(meshes["visual"])} — {meshes["visual_triangles"]} triangles')
    stats = meshes['collision_stats']
    print(f'Collision: {relative(meshes["collision"])} — '
          f'{stats["faces_after"]}/{stats["faces_before"]} triangles, '
          f'{stats["vertices_after"]}/{stats["vertices_before"]} vertices')
    for name in ('funnel_physics.sdf', 'route.json', 'world_metadata.json'):
        print(f'Save at: {out / name}')
    check_world(out, record, meshes)


if __name__ == '__main__':
    main()
