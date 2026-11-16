#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Matplotlib; Python stdlib (argparse, json, math, sys,
# pathlib); local modules (glb2off, off).
"""Render OFF meshes to PNG, or open them in an interactive 3D window.

GLB files can be opened by Blender, MeshLab or any glTF viewer; OFF files need
a dedicated reader. This tool is that reader. It draws the triangulated
surface, can overlay the expected paths from data/expected, and can compare a
mesh with the standardized city scene, before and after triangulation. It
saves one PNG per mesh under generated/data_viz/.

Examples:
  .venv/bin/python tools/data/data_viz.py --all
  .venv/bin/python tools/data/data_viz.py L terrain
  .venv/bin/python tools/data/data_viz.py L --show
  .venv/bin/python tools/data/data_viz.py city.standardized.triangulation --scene
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
if '--show' not in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb2off import read_glb_scene
from off import read_off

DEFAULT_INPUT = ROOT / 'data/processed/meshes'
DEFAULT_OUTPUT = ROOT / 'generated/data_viz'
DEFAULT_SCENE = ROOT / 'data/processed/scenes/city.standardized.glb'


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


def read_scene(path, limit):
    if limit < 0:
        raise SystemExit('--scene-triangles must be zero or positive')
    vertices, faces = read_glb_scene(path, 200.)
    stride = max(1, len(faces) // limit) if limit else 1
    return vertices[faces[::stride]], len(faces)


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


def render_compare(path, scene, scene_total, output, show):
    points, faces = read_off(path)

    limits = np.vstack([scene.reshape(-1, 3), points])
    low, high = limits.min(axis=0), limits.max(axis=0)
    span = high - low

    figure = plt.figure(figsize=(14, 7))
    before = figure.add_subplot(121, projection='3d')
    before.add_collection3d(Poly3DCollection(scene, facecolors='#7b8794',
                                             edgecolors='#3f4750', linewidths=0.05))
    shown = (f'{len(scene)} of {scene_total} triangles shown'
             if len(scene) < scene_total else f'{scene_total} triangles')
    before.set_title(f'before: standardized scene ({shown})')
    after = figure.add_subplot(122, projection='3d')
    after.plot_trisurf(points[:, 0], points[:, 1], points[:, 2],
                       triangles=faces, cmap='viridis',
                       edgecolor='#333333', linewidth=0.2, alpha=0.95)
    after.set_title(f'after: triangulated surface ({len(faces)} triangles)')

    for axes in (before, after):
        axes.set_xlim(low[0], high[0])
        axes.set_ylim(low[1], high[1])
        axes.set_zlim(low[2], high[2])
        axes.set_box_aspect(tuple(float(value) or 1. for value in span))
        axes.view_init(elev=30, azim=-58)
        axes.set_xlabel('X')
        axes.set_ylabel('Y')
        axes.set_zlabel('Z')

    figure.suptitle(f'{path.stem} — standardized scene (left) and the surface after triangulation (right)')
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
    parser.add_argument('--scene', nargs='?', const=str(DEFAULT_SCENE), default=None,
                        metavar='GLB',
                        help='Compare the mesh with the standardized city scene, before/after '
                             f'triangulation (default: {DEFAULT_SCENE.relative_to(ROOT)})')
    parser.add_argument('--scene-triangles', type=int, default=0, metavar='N',
                        help='Maximum scene triangles to draw; 0 draws all (default: 0)')
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

    scene = None
    if args.scene:
        scene_path = Path(args.scene)
        if not scene_path.is_file():
            parser.error(f'Scene not found: {scene_path}. Run the data stage first.')
        scene, scene_total = read_scene(scene_path, args.scene_triangles)

    for path in paths:
        if scene is not None:
            output = args.output / f'{path.stem}-compare.png'
            saved = render_compare(path, scene, scene_total, output, args.show)
        else:
            output = args.output / f'{path.stem}.png'
            saved = render(path, output, not args.no_paths, args.source, args.show)
        if saved is not None:
            print(f'Save at: {saved}')
    if not args.show:
        print(f'Rendered {len(paths)} mesh(es) to {args.output}')


if __name__ == '__main__':
    main()
