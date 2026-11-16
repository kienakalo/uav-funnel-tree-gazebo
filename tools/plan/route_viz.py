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

import numpy as np
import matplotlib
if '--show' not in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
from mesh_off import read_off

DEFAULT_INPUT = ROOT / 'generated/routes'
COLOURS = ('#c0392b', '#8e44ad', '#e67e22', '#16a085', '#2c3e50',
           '#7f8c8d', '#2980b9', '#d35400')


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
        saved = None
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=150, bbox_inches='tight')
        saved = output
        print(f'Save at: {output}')
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
