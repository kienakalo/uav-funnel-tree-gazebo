# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Shapely; Python stdlib (argparse, heapq, json, math,
# sys, pathlib); local modules (glb2off, mesh_off).
"""Triangulate a navigation surface over the standardized city scene.

Input:  data/processed/scenes/city.standardized.glb
Output: data/processed/meshes/city.standardized.triangulation.off

The surface is the same conservative clearance envelope used by the delivery
experiment: whole cells over the city, raised by the vertical clearance and
spread into ramps. It only spans the corridor around START and GOAL, so those
two points are arguments; the defaults are the delivery mission endpoints.
Coordinates are in the normalized Z-up frame. This is a safety
envelope above the city, not the bare terrain or rooftops.

The city triangles are read from the standardized scene, so the step needs no
intermediate STL. The scene is re-read with the same reader the visualization
uses, which bakes the node transforms, switches to Z-up and normalizes the
width to 200 m.

Parameters are printed to the console and written to a sidecar next to the
surface (<name>.params.json) with the hashes of the scene, the script and the
output, so a surface can be traced back to the run that produced it.
"""
import argparse
import hashlib
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely import polygons
from shapely.geometry import box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb2off import read_glb_scene
from mesh_off import inspect_mesh, write_off

DEFAULT_SCENE = ROOT / 'data/processed/scenes/city.standardized.glb'
DEFAULT_OUTPUT = ROOT / 'data/processed/meshes/city.standardized.triangulation.off'
# Delivery mission endpoints. The envelope only exists between them, so pass
# --start/--goal to build a surface for a different mission.
DEFAULT_START = (-38.7521239854311, 22.103391740920674, 7.205632472302205)
DEFAULT_GOAL = (74.73658745332892, -55.35715733632823, 7.205632472302205)

CLEARANCE = 1.5
HALF_WIDTH = 1.6
MAX_AXIS_SLOPE = .5


def relative(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_surface(triangles, start, goal, step, coverage='city',
                  clearance=CLEARANCE, half_width=HALF_WIDTH,
                  max_slope=MAX_AXIS_SLOPE):
    """Every whole mesh cell clears all inflated city-triangle AABBs below it."""
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    spatial = STRtree(polygons(triangles[:, :, :2]))
    xy = np.array([start[:2], goal[:2]])
    if coverage == 'city':
        extent = np.vstack((low[:, :2], high[:, :2], xy))
    else:
        extent = xy
    minimum = np.floor((extent.min(axis=0) - 16.) / step) * step
    maximum = np.ceil((extent.max(axis=0) + 16.) / step) * step
    xs = np.unique(np.r_[np.arange(minimum[0], maximum[0] + step / 2, step), xy[:, 0]])
    ys = np.unique(np.r_[np.arange(minimum[1], maximum[1] + step / 2, step), xy[:, 1]])
    required = np.empty((len(xs) - 1, len(ys) - 1))
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            query = box(xs[i] - half_width, ys[j] - half_width,
                        xs[i + 1] + half_width, ys[j + 1] + half_width)
            ids = spatial.query(query)
            required[i, j] = (float(high[ids, 2].max()) if len(ids) else 0.) + clearance
    heights = np.full((len(xs), len(ys)), clearance)
    for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
        section = heights[di:di + len(xs) - 1, dj:dj + len(ys) - 1]
        np.maximum(section, required, out=section)

    # Spread roof heights outward to make ramps. This only raises the envelope.
    queue = [(-float(h), i, j) for (i, j), h in np.ndenumerate(heights)]
    heapq.heapify(queue)
    while queue:
        negative_height, i, j = heapq.heappop(queue)
        height = -negative_height
        if height < heights[i, j] - 1e-10:
            continue
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if not (0 <= a < len(xs) and 0 <= b < len(ys)):
                continue
            distance = math.hypot(xs[a] - xs[i], ys[b] - ys[j])
            candidate = height - max_slope * distance
            if candidate > heights[a, b] + 1e-10:
                heights[a, b] = candidate
                heapq.heappush(queue, (-candidate, a, b))

    points = np.array([(x, y, heights[i, j]) for i, x in enumerate(xs)
                       for j, y in enumerate(ys)])
    faces = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            a = i * len(ys) + j
            b, c, d = a + len(ys), a + 1, a + len(ys) + 1
            faces.extend([(a, b, c), (b, d, c)])
            if min(heights[i, j], heights[i + 1, j], heights[i, j + 1],
                   heights[i + 1, j + 1]) < required[i, j] - 1e-9:
                raise ValueError('Surface clearance construction failed')
    faces = np.array(faces, dtype=int)
    stats = inspect_mesh(points, faces)
    for key in ('nonmanifold_edges', 'bad_boundary_vertices',
                'disconnected_vertex_fans', 'degenerate_triangles'):
        if stats[key]:
            raise ValueError(f'Invalid surface topology: {key}')
    source = int(np.linalg.norm(points[:, :2] - xy[0], axis=1).argmin())
    target = int(np.linalg.norm(points[:, :2] - xy[1], axis=1).argmin())
    # Entry and delivery descent must also have clear vertical columns.
    for location, surface_index in ((start, source), (goal, target)):
        x, y, bottom = location
        ids = spatial.query(box(x - half_width, y - half_width,
                                x + half_width, y + half_width))
        top = points[surface_index, 2]
        overlap = ((high[ids, 2] >= min(bottom, top) - .2) &
                   (low[ids, 2] <= max(bottom, top) + .2))
        if overlap.any():
            raise ValueError('The vertical surface entry or delivery descent '
                             'intersects city geometry')
    return points, faces, source, target, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, default=DEFAULT_SCENE)
    parser.add_argument('--start', nargs=3, type=float, default=DEFAULT_START,
                        metavar=('X', 'Y', 'Z'),
                        help='Envelope start point (default: delivery mission start)')
    parser.add_argument('--goal', nargs=3, type=float, default=DEFAULT_GOAL,
                        metavar=('X', 'Y', 'Z'),
                        help='Envelope goal point (default: delivery mission goal)')
    parser.add_argument('--cell', type=float, default=5.)
    parser.add_argument('--clearance', type=float, default=CLEARANCE,
                        help=f'Vertical clearance above the city in metres '
                             f'(default: {CLEARANCE})')
    parser.add_argument('--half-width', type=float, default=HALF_WIDTH,
                        help=f'Inflation around each cell in metres '
                             f'(default: {HALF_WIDTH})')
    parser.add_argument('--max-slope', type=float, default=MAX_AXIS_SLOPE,
                        help=f'Largest height change per metre while spreading '
                             f'the envelope (default: {MAX_AXIS_SLOPE})')
    parser.add_argument('--coverage', choices=('city', 'mission'), default='city')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--force', action='store_true',
                        help='Overwrite an existing surface')
    args = parser.parse_args()
    if not args.scene.is_file():
        parser.error(f'Missing standardized scene: {args.scene}. Run tools/data/standardize.py first.')
    if args.output.exists() and not args.force:
        parser.error(f'{args.output} already exists; pass --force to overwrite')

    vertices, faces = read_glb_scene(args.scene, 200.)
    start = np.array(args.start)
    goal = np.array(args.goal)
    points, surface_faces, source, target, stats = build_surface(
        vertices[faces], start, goal, args.cell, args.coverage,
        args.clearance, args.half_width, args.max_slope)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_off(args.output, points, surface_faces)
    parameters = {
        'cell': args.cell, 'coverage': args.coverage,
        'vertical_clearance': args.clearance,
        'horizontal_half_width': args.half_width,
        'max_axis_slope': args.max_slope,
    }
    print('Parameters:', json.dumps(parameters))
    result = {
        'vertices': int(len(points)), 'triangles': int(len(surface_faces)),
        'edges': int(stats['edges']), 'surface_source': int(source),
        'surface_target': int(target),
        'nonmanifold_edges': int(stats['nonmanifold_edges']),
    }
    print('Result:', json.dumps(result))
    print(f'Save at: {relative(args.output)}')

    sidecar = args.output.with_suffix('.params.json')
    sidecar.write_text(json.dumps({
        'output': str(relative(args.output)),
        'output_sha256': sha256(args.output),
        'script': str(relative(Path(__file__))),
        'script_sha256': sha256(Path(__file__)),
        'scene': str(relative(args.scene)),
        'scene_sha256': sha256(args.scene),
        'parameters': parameters,
        'result': result,
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Save at: {relative(sidecar)}')


if __name__ == '__main__':
    main()
