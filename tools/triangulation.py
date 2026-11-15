# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Shapely; Python stdlib (argparse, json, pathlib,
# tempfile); local modules (build_navigation_surface, city,
# plan_surface_delivery).
"""Triangulate a navigation surface from the standardized city scene.

Input:  data/processed/scenes/city.standardized.glb
        generated/funnel_physics/delivery/horizontal_plan.json
Output: data/processed/meshes/city.triangulation.off

The surface is the same conservative clearance envelope used by the delivery
experiment: whole cells over the city, raised by the vertical clearance and
spread into ramps. Coordinates are in the normalized Gazebo frame (Z-up), the
same frame as the delivery plan. This is a safety envelope above the city, not
the bare terrain or rooftops.

Parameters are printed to the console and documented in
data/processed/README.md. No sidecar is written.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from build_navigation_surface import write_off
from city import load_city, write_stl
from plan_surface_delivery import CLEARANCE, HALF_WIDTH, MAX_AXIS_SLOPE, build_surface

DEFAULT_SCENE = ROOT / 'data/processed/scenes/city.standardized.glb'
DEFAULT_PLAN = ROOT / 'generated/funnel_physics/delivery/horizontal_plan.json'
DEFAULT_OUTPUT = ROOT / 'data/processed/meshes/city.triangulation.off'
DEFAULT_STL = ROOT / 'generated/funnel_preview/city.stl'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, default=DEFAULT_SCENE)
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--cell', type=float, default=5.)
    parser.add_argument('--coverage', choices=('city', 'mission'), default='city')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--stl', type=Path, default=DEFAULT_STL,
                        help='Canonical normalized city STL used by the delivery plan')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite an existing surface')
    parser.add_argument('--from-scene', action='store_true',
                        help='Rebuild the STL from the scene instead of using the canonical STL')
    args = parser.parse_args()
    if not args.scene.is_file():
        parser.error(f'Missing standardized scene: {args.scene}. Run tools/standardize.py first.')
    if not args.plan.is_file():
        parser.error(f'Missing delivery plan: {args.plan}')
    if args.output.exists() and not args.force:
        parser.error(f'{args.output} already exists; pass --force to overwrite')

    vertices, faces, _ = load_city(args.scene)
    temporary = tempfile.TemporaryDirectory()
    if args.from_scene:
        stl_path = Path(temporary.name) / 'city.standardized.stl'
        write_stl(stl_path, vertices, faces)
    else:
        if not args.stl.is_file():
            parser.error(f'Missing canonical STL: {args.stl}; run tools/prepare_funnel_gazebo.py')
        stl_path = args.stl

    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    start = np.array(plan['fixed_start'])
    goal = np.r_[plan['waypoints'][-1][:2], plan['selection']['ground_z'] + 1.1]
    mesh, points, surface_faces, source, target, stats = build_surface(
        start, goal, args.cell, args.coverage, stl_path=stl_path)

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
    temporary.cleanup()


if __name__ == '__main__':
    main()
