#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Matplotlib; Python stdlib (argparse, json, sys,
# pathlib); local modules (mesh_off).
"""Render saved Funnel routes to PNG, or show them in a 3D window.

Input:  generated/routes/*.json   (written by tools/plan/run_funnel.py)
        the mesh named in each file
Output: generated/routes/<mission>.png

Rendering is separate from planning so a view can be redrawn without running
the solver again.

Examples:
  .venv/bin/python tools/plan/route_viz.py
  .venv/bin/python tools/plan/route_viz.py --routes generated/routes/cliff.json
  .venv/bin/python tools/plan/route_viz.py --show
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))

import numpy as np
import matplotlib
from plotting import unavailable_message, use_interactive

if '--show' in sys.argv:
    if use_interactive() is None:
        raise SystemExit(f'route_viz: {unavailable_message()}')
else:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from mesh_off import read_off
from figstamp import save as save_stamped
from figstamp import sha256

DEFAULT_INPUT = ROOT / 'generated/routes'
COLOURS = ('#c0392b', '#8e44ad', '#e67e22', '#16a085', '#2c3e50',
           '#7f8c8d', '#2980b9', '#d35400')
LABELS = {
    'seconds': ('solve limit', ' s'),
    'max_nodes': ('max nodes', ''),
    'clipping': ('clipping', ''),
    'shown': ('shown', ''),
    'speed': ('speed', ' m/s'),
    'max_acceleration': ('accel', ' m/s²'),
    'dwell': ('dwell', ' s'),
    'start_delay': ('delay', ' s'),
    'simplify_tolerance': ('simplify', ' m'),
    'collision_grid': ('collision grid', ' m'),
    'flight': ('flight', ''),
    'planning': ('planning', ''),
    'routes': ('routes', ''),
}


def flight_settings(mission):
    """Flight settings of the worlds built for this mission, when uniform."""
    records = []
    for path in sorted((ROOT / 'generated/simulate').glob(
            f'{mission}-*/world_metadata.json')):
        try:
            records.append(json.loads(path.read_text(encoding='utf-8')))
        except ValueError:
            continue
    if not records:
        return {}
    signatures = {json.dumps([record.get('flight'),
                              record.get('simplify_tolerance'),
                              (record.get('collision_stats') or {}).get('cell')],
                             sort_keys=True) for record in records}
    if len(signatures) > 1:
        return {'flight': 'mixed'}
    record = records[0]
    flight = record.get('flight') or {}
    return {
        'speed': flight.get('speed'),
        'max_acceleration': flight.get('max_acceleration'),
        'dwell': flight.get('dwell'),
        'start_delay': flight.get('start_delay'),
        'simplify_tolerance': record.get('simplify_tolerance'),
        'collision_grid': (record.get('collision_stats') or {}).get('cell'),
    }


def stamp_data(path, record, shown, limit):
    solver = record.get('solver') or {}
    parameters = {
        'seconds': solver.get('timeout_seconds'),
        'max_nodes': solver.get('max_nodes'),
        'clipping': solver.get('clipping', (record.get('stats') or {}).get('clipping')),
    }
    if limit > 0 and len(record['routes']) > limit:
        parameters['shown'] = shown
    parameters.update(flight_settings(path.stem))
    sources = {
        'mesh_sha256': record.get('mesh_sha256'),
        'mission_sha256': record.get('mission_sha256'),
        'module_sha256': solver.get('module_sha256'),
        'routes_sha256': sha256(path),
    }
    facts = {'routes': len(record['routes'])}
    if record.get('planning_seconds') is not None:
        facts['planning'] = f'{record["planning_seconds"]:.1f} s'
    for route in record['routes'][:12]:
        facts[route['id']] = f'{route["length"]:.1f} m'
    return parameters, facts, sources


def render(path, output, limit, show):
    record = json.loads(path.read_text(encoding='utf-8'))
    mesh_path = ROOT / record['mesh']
    points, faces = read_off(mesh_path)
    routes = record['routes']
    if limit > 0 and len(routes) > limit:
        routes = sorted(routes, key=lambda route: route['length'], reverse=True)[:limit]

    figure = plt.figure(figsize=(10, 9))
    axes = figure.add_subplot(111, projection='3d')
    axes.plot_trisurf(points[:, 0], points[:, 1], points[:, 2], triangles=faces,
                      cmap='viridis', linewidth=0., alpha=.5)
    start = points[record['source']]
    axes.scatter(*start, color='#167a40', s=90, depthshade=False, zorder=5,
                 label='START')
    for number, route in enumerate(routes, 1):
        waypoints = np.array(route['waypoints'])
        colour = COLOURS[(number - 1) % len(COLOURS)]
        axes.plot(waypoints[:, 0], waypoints[:, 1], waypoints[:, 2], color=colour,
                  linewidth=1.6,
                  label=f'{route["id"]} — {route["length"]:.1f}' if len(routes) <= 12
                  else None)
        axes.scatter(*waypoints[-1], color=colour, marker='*', s=110,
                     depthshade=False, zorder=5)

    span = points.max(axis=0) - points.min(axis=0)
    axes.set_box_aspect(tuple(float(value) or 1. for value in span))
    axes.set_xlabel('X')
    axes.set_ylabel('Y')
    axes.set_zlabel('Z')
    title = f'{path.stem} — {len(record["routes"])} route(s)'
    if record.get('planning_seconds') is not None:
        title += f', {record["planning_seconds"]:.1f}s'
    axes.set_title(title)
    if len(routes) <= 12:
        axes.legend(loc='upper left')
    if show:
        plt.show()
        saved = None, None
    else:
        parameters, facts, sources = stamp_data(path, record, len(routes), limit)
        image, sidecar = save_stamped(
            figure, output, parameters=parameters, facts=facts, sources=sources,
            labels=LABELS, script=__file__, subject=title)
        saved = image, sidecar
        print(f'Save at: {image}')
        print(f'Save at: {sidecar}')
    plt.close(figure)
    return saved


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--routes', type=Path, action='append',
                        help='Route file; repeat for several (default: all)')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT,
                        help='Folder scanned when --routes is not given')
    parser.add_argument('--output', type=Path, default=DEFAULT_INPUT,
                        help='PNG folder (default: generated/routes)')
    parser.add_argument('--max-routes', type=int, default=60, metavar='N',
                        help='Draw at most N routes, the longest ones (default: 60)')
    parser.add_argument('--show', action='store_true',
                        help='Open a 3D window instead of writing PNG files')
    args = parser.parse_args()

    paths = ([path.resolve() for path in args.routes] if args.routes
             else sorted(args.input.glob('*.json')))
    paths = [path for path in paths if path.name != 'summary.json']
    if not paths:
        raise SystemExit(f'route_viz: no route file in {args.input}; '
                         'run tools/plan/run_funnel.py first')
    for path in paths:
        if not path.is_file():
            raise SystemExit(f'route_viz: missing {path}')
        output = args.output / f'{path.stem}.png'
        render(path, output, args.max_routes, args.show)
    print(f'Rendered {len(paths)} route file(s) to {args.output}')


if __name__ == '__main__':
    main()
