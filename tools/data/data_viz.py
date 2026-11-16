#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Matplotlib; Python stdlib (argparse, json, math, sys,
# pathlib); local modules (mesh_off).
"""Render OFF meshes to PNG, or open them in an interactive 3D window.

GLB files can be opened by Blender, MeshLab or any glTF viewer; OFF files need
a dedicated reader. This tool is that reader. It draws the triangulated
surface and can overlay the expected paths from data/expected. It saves one PNG
per mesh under generated/data_viz/.

Examples:
  .venv/bin/python tools/data/data_viz.py --all
  .venv/bin/python tools/data/data_viz.py L terrain
  .venv/bin/python tools/data/data_viz.py L --show
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import matplotlib
from plotting import unavailable_message, use_interactive

if '--show' in sys.argv:
    if use_interactive() is None:
        raise SystemExit(f'data_viz: {unavailable_message()}')
else:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mesh_off import read_off

DEFAULT_INPUT = ROOT / 'data/processed/meshes'
DEFAULT_OUTPUT = ROOT / 'generated/data_viz'


def read_paths(path):
    """Read a .paths.json overlay; accepts the wrapper or a bare list."""
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    records = payload['paths'] if isinstance(payload, dict) else payload
    routes = []
    for number, record in enumerate(records, 1):
        if not isinstance(record, list) or len(record) < 2:
            raise SystemExit(f'{path}: invalid path at entry {number}')
        route = [tuple(float(value) for value in point) for point in record]
        if any(len(point) != 3 or not all(math.isfinite(value) for value in point)
               for point in route):
            raise SystemExit(f'{path}: invalid coordinates at entry {number}')
        routes.append(route)
    return routes


def render(path, output, show_paths, source, show):
    points, faces = read_off(path)

    figure = plt.figure(figsize=(9, 8))
    axes = figure.add_subplot(111, projection='3d')
    axes.plot_trisurf(points[:, 0], points[:, 1], points[:, 2],
                      triangles=faces, cmap='viridis',
                      edgecolor='#333333', linewidth=0.2, alpha=0.95)

    expected = ROOT / 'data/expected' / f'{path.stem}.paths.json'
    if show_paths and expected.is_file():
        for number, route in enumerate(read_paths(expected), 1):
            route = np.array(route)
            axes.plot(route[:, 0], route[:, 1], route[:, 2],
                      color='#c0392b', linewidth=1.2,
                      label='expected path' if number == 1 else None)
        axes.legend(loc='upper right')

    if source is not None:
        if not 0 <= source < len(points):
            raise SystemExit(f'{path}: source {source} outside 0..{len(points) - 1}')
        axes.scatter(*points[source], color='#e67e22', s=60, depthshade=False,
                     label=f'source {source}')
        axes.legend(loc='upper right')

    span = points.max(axis=0) - points.min(axis=0)
    axes.set_box_aspect((span[0] or 1., span[1] or 1., span[2] or 1.))
    axes.set_xlabel('X')
    axes.set_ylabel('Y')
    axes.set_zlabel('Z')
    axes.set_title(f'{path.name} — {len(points)} vertices, {len(faces)} triangles')

    if show:
        plt.show()
        return None
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150, bbox_inches='tight')
    plt.close(figure)
    return output


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('meshes', nargs='*', metavar='name',
                        help='Mesh stems or paths (default: all with --all)')
    parser.add_argument('--all', action='store_true', help='Render every .off in the input folder')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--source', type=int, default=None,
                        help='Mark this vertex index as the path source')
    parser.add_argument('--no-paths', action='store_true',
                        help='Do not overlay data/expected paths')
    parser.add_argument('--show', action='store_true',
                        help='Open interactive windows instead of writing PNG files')
    args = parser.parse_args()

    if args.all:
        paths = sorted(args.input.glob('*.off'))
    else:
        if not args.meshes:
            parser.error('Pass one or more mesh names, or --all')
        paths = []
        for name in args.meshes:
            candidate = Path(name)
            if not candidate.is_file():
                candidate = args.input / (name if name.endswith('.off') else name + '.off')
            if not candidate.is_file():
                parser.error(f'Mesh not found: {name}')
            paths.append(candidate)

    for path in paths:
        output = args.output / f'{path.stem}.png'
        saved = render(path, output, not args.no_paths, args.source, args.show)
        if saved is not None:
            print(f'Save at: {saved}')
    if not args.show:
        print(f'Rendered {len(paths)} mesh(es) to {args.output}')


if __name__ == '__main__':
    main()
