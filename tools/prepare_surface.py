# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Shapely; Python stdlib (argparse, hashlib, json,
# pathlib, tempfile); local modules (build_navigation_surface, city,
# plan_surface_delivery).
"""Triangulate a navigation surface from the standardized city scene.

Input:  data/processed/scenes/city.scene.glb
        generated/funnel_physics/delivery/horizontal_plan.json
Output: data/processed/meshes/city.surface.cell5.off
        data/processed/meshes/city.surface.cell5.json

The surface is the same conservative clearance envelope used by the delivery
experiment: whole cells over the city, raised by the vertical clearance and
spread into ramps. Coordinates are in the normalized Gazebo frame (Z-up), the
same frame as the delivery plan. This is a safety envelope above the city, not
the bare terrain or rooftops.
"""
import argparse
import hashlib
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

DEFAULT_SCENE = ROOT / 'data/processed/scenes/city.scene.glb'
DEFAULT_PLAN = ROOT / 'generated/funnel_physics/delivery/horizontal_plan.json'
DEFAULT_OUTPUT = ROOT / 'data/processed/meshes/city.surface.cell5.off'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, default=DEFAULT_SCENE)
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--cell', type=float, default=5.)
    parser.add_argument('--coverage', choices=('city', 'mission'), default='city')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--stl', type=Path, default=ROOT / 'generated/funnel_preview/city.stl',
                        help='Canonical normalized city STL used by the delivery plan')
    parser.add_argument('--from-scene', action='store_true',
                        help='Rebuild the STL from the scene instead of using the canonical STL')
    args = parser.parse_args()
    if not args.scene.is_file():
        parser.error(f'Missing standardized scene: {args.scene}. Run tools/prepare_scene.py first.')
    if not args.plan.is_file():
        parser.error(f'Missing delivery plan: {args.plan}')

    vertices, faces, metadata = load_city(args.scene)
    temporary = tempfile.TemporaryDirectory()
    if args.from_scene:
        stl_path = Path(temporary.name) / 'city.scene.stl'
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
    manifest = {
        'process': 'triangulate',
        'method': 'conservative cell envelope over city triangles',
        'parameters': {
            'cell': args.cell, 'coverage': args.coverage,
            'vertical_clearance': CLEARANCE, 'horizontal_half_width': HALF_WIDTH,
            'max_axis_slope': MAX_AXIS_SLOPE,
        },
        'scene': {
            'file': args.scene.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(args.scene.read_bytes()).hexdigest(),
            'scale': metadata.get('scale'), 'origin': metadata.get('origin'),
        },
        'stl': {
            'file': stl_path.relative_to(ROOT).as_posix() if stl_path.is_relative_to(ROOT) else 'temporary from scene',
            'sha256': hashlib.sha256(stl_path.read_bytes()).hexdigest(),
            'mode': 'rebuilt from scene' if args.from_scene else 'canonical delivery STL',
        },
        'plan': {
            'file': args.plan.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(args.plan.read_bytes()).hexdigest(),
            'start': [float(v) for v in start], 'goal': [float(v) for v in goal],
        },
        'result': {
            'vertices': int(len(points)), 'triangles': int(len(surface_faces)),
            'edges': int(stats['edges']), 'surface_source': int(source),
            'surface_target': int(target),
            'nonmanifold_edges': int(stats['nonmanifold_edges']),
        },
        'coordinates': 'normalized Gazebo units, Z-up; same frame as the delivery plan',
        'scope': 'safety envelope above the city, not the bare terrain or rooftops',
    }
    manifest_path = args.output.with_suffix('.json')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    temporary.cleanup()
    print(json.dumps(manifest['result'], indent=2))
    print(f'Save at: {args.output}')
    print(f'Save at: {manifest_path}')


if __name__ == '__main__':
    main()
