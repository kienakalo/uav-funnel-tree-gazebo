# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Shapely; Python stdlib (argparse, heapq, json, math,
# sys, pathlib); local modules (build_navigation_surface, glb2off).
"""Triangulate a navigation surface from the standardized city scene.

Input:  data/processed/scenes/city.standardized.glb
        generated/funnel_physics/delivery/horizontal_plan.json
Output: data/processed/meshes/city.standardized.triangulation.off

The surface is the same conservative clearance envelope used by the delivery
experiment: whole cells over the city, raised by the vertical clearance and
spread into ramps. Coordinates are in the normalized Gazebo frame (Z-up), the
same frame as the delivery plan. This is a safety envelope above the city, not
the bare terrain or rooftops.

The city triangles are read from the standardized scene, so the step needs no
intermediate STL. The scene is re-read with the same reader the visualization
uses, which bakes the node transforms, switches to Z-up and normalizes the
width to 200 m.

Parameters are printed to the console and documented in
data/processed/README.md. No sidecar is written.
"""
import argparse
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely import polygons
from shapely.geometry import box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from build_navigation_surface import inspect_mesh, write_off
from glb2off import read_glb_scene

DEFAULT_SCENE = ROOT / 'data/processed/scenes/city.standardized.glb'
DEFAULT_PLAN = ROOT / 'generated/funnel_physics/delivery/horizontal_plan.json'
DEFAULT_OUTPUT = ROOT / 'data/processed/meshes/city.standardized.triangulation.off'

CLEARANCE = 1.5
HALF_WIDTH = 1.6
MAX_AXIS_SLOPE = .5


def build_surface(triangles, start, goal, step, coverage='city'):
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
            query = box(xs[i] - HALF_WIDTH, ys[j] - HALF_WIDTH,
                        xs[i + 1] + HALF_WIDTH, ys[j + 1] + HALF_WIDTH)
            ids = spatial.query(query)
            required[i, j] = (float(high[ids, 2].max()) if len(ids) else 0.) + CLEARANCE
    heights = np.full((len(xs), len(ys)), CLEARANCE)
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
            candidate = height - MAX_AXIS_SLOPE * distance
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
        ids = spatial.query(box(x - HALF_WIDTH, y - HALF_WIDTH,
                                x + HALF_WIDTH, y + HALF_WIDTH))
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
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--cell', type=float, default=5.)
    parser.add_argument('--coverage', choices=('city', 'mission'), default='city')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--force', action='store_true',
                        help='Overwrite an existing surface')
    args = parser.parse_args()
    if not args.scene.is_file():
        parser.error(f'Missing standardized scene: {args.scene}. Run tools/standardize.py first.')
    if not args.plan.is_file():
        parser.error(f'Missing delivery plan: {args.plan}')
    if args.output.exists() and not args.force:
        parser.error(f'{args.output} already exists; pass --force to overwrite')

    vertices, faces = read_glb_scene(args.scene, 200.)
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    start = np.array(plan['fixed_start'])
    goal = np.r_[plan['waypoints'][-1][:2], plan['selection']['ground_z'] + 1.1]
    points, surface_faces, source, target, stats = build_surface(
        vertices[faces], start, goal, args.cell, args.coverage)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_off(args.output, points, surface_faces, stats['edges'])
    parameters = {
        'cell': args.cell, 'coverage': args.coverage,
        'vertical_clearance': CLEARANCE, 'horizontal_half_width': HALF_WIDTH,
        'max_axis_slope': MAX_AXIS_SLOPE,
    }
    print('Parameters:', json.dumps(parameters))
    print('Result:', json.dumps({
        'vertices': int(len(points)), 'triangles': int(len(surface_faces)),
        'edges': int(stats['edges']), 'surface_source': int(source),
        'surface_target': int(target),
        'nonmanifold_edges': int(stats['nonmanifold_edges']),
    }))
    print(f'Save at: {args.output}')


if __name__ == '__main__':
    main()
