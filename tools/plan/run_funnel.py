#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, hashlib, json, math, platform,
# sys, time, pathlib); local modules (funnel_tree, mesh_off).
"""Run Funnel on the saved missions and write one route file per mission.

Input:  data/processed/missions/*.mission.json  (or --mission)
Output: generated/routes/<mission>.routes.json

For a mission with explicit goals only those routes are kept; for an
"all-goals" mission every vertex except START is kept. Each route lists the
surface waypoints, so the length is the sum of the Euclidean steps between
them, and the file records the mesh, mission and algorithm hashes plus the
resource limits, so a result can be traced back to the inputs that produced
it.

Examples:
  .venv/bin/python tools/plan/run_funnel.py
  .venv/bin/python tools/plan/run_funnel.py --mission data/processed/missions/cliff.mission.json
  .venv/bin/python tools/plan/run_funnel.py --seconds 600 --no-clipping
"""
import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT / 'algo'))
from funnel_tree import solve_targets
from mesh_off import read_mesh

DEFAULT_MISSIONS = ROOT / 'data/processed/missions'
MISSION_SUFFIX = '.mission.json'


def mission_id(path):
    """cliff.mission.json -> cliff; tolerate an explicit file without suffix."""
    name = Path(path).name
    return name[:-len(MISSION_SUFFIX)] if name.endswith(MISSION_SUFFIX) else Path(path).stem
DEFAULT_OUTPUT = ROOT / 'generated/routes'
ALGORITHM = ROOT / 'algo/funnel_tree.py'


def fail(message):
    raise SystemExit(f'run_funnel: {message}')


def relative(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def route_length(waypoints):
    return sum(math.dist(a, b) for a, b in zip(waypoints, waypoints[1:]))


def load_mission(path):
    record = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(record, dict) or 'mesh' not in record or 'start' not in record:
        fail(f'{path}: not a mission file; run tools/data/set_start_goal.py')
    return record


def plan_mission(path, seconds, max_nodes, clipping):
    mission = load_mission(path)
    mesh_path = (ROOT / mission['mesh']).resolve()
    if not mesh_path.is_file():
        fail(f'{path}: missing mesh {mesh_path}')
    if sha256(mesh_path) != mission.get('mesh_sha256'):
        fail(f'{path}: {relative(mesh_path)} changed since the mission was saved')
    mesh = read_mesh(mesh_path)
    if (len(mesh.points) != mission.get('mesh_vertices') or
            len(mesh.faces) != mission.get('mesh_faces')):
        fail(f'{path}: mesh size differs from the mission record')
    source = mission['start']['vertex']
    if mission['mode'] == 'all-goals':
        goals = [(f'v{vertex}', vertex) for vertex in range(len(mesh.points))
                 if vertex != source]
    else:
        goals = [(goal['id'], goal['vertex']) for goal in mission.get('goals') or []]
    if not goals:
        fail(f'{path}: the mission has no GOAL')

    started = time.monotonic()
    per_goal = {}
    try:
        if mission['mode'] == 'explicit' and len(goals) > 1:
            # One search per goal: a combined search keeps a frontier sized by
            # the farthest goal, which is slower than three shorter searches.
            paths, propagations, considered = {}, 0, 0
            for _, vertex in goals:
                goal_started = time.monotonic()
                found, search = solve_targets(mesh, source, [vertex],
                                              timeout=seconds, max_nodes=max_nodes,
                                              clipping=clipping)
                paths.update(found)
                propagations += search['propagations']
                considered = max(considered, search['sources_considered'])
                per_goal[vertex] = {
                    'propagations': search['propagations'],
                    'seconds': round(time.monotonic() - goal_started, 3),
                }
            stats = {'sources_considered': considered,
                     'propagations': propagations, 'mode': 'per-goal',
                     'clipping': clipping}
        else:
            paths, stats = solve_targets(mesh, source, [vertex for _, vertex in goals],
                                         timeout=seconds, max_nodes=max_nodes,
                                         clipping=clipping)
            stats['mode'] = 'combined'
    except (ValueError, TimeoutError, RuntimeError) as error:
        fail(f'{relative(path)}: {error}')
    elapsed = round(time.monotonic() - started, 3)

    routes = []
    for identifier, vertex in goals:
        waypoints = [[round(value, 9) for value in point] for point in paths[vertex]]
        entry = {'id': identifier, 'vertex': vertex,
                 'length': round(route_length(paths[vertex]), 9),
                 'waypoints': waypoints}
        if vertex in per_goal:
            # Per-goal cost, so a table of one goal can be reproduced without
            # splitting the run: the total in stats hides which goal is slow.
            entry['search'] = per_goal[vertex]
        routes.append(entry)
    record = {
        'mission': str(relative(path)),
        'mission_sha256': sha256(path),
        'mesh': str(relative(mesh_path)),
        'mesh_sha256': mission['mesh_sha256'],
        'source': source,
        'solver': {
            'name': 'funnel_tree',
            'module': str(ALGORITHM.relative_to(ROOT)),
            'module_sha256': sha256(ALGORITHM),
            'timeout_seconds': seconds,
            'max_nodes': max_nodes,
            'clipping': clipping,
        },
        'mode': mission['mode'],
        'routes': routes,
        'stats': stats,
        'planning_seconds': elapsed,
        'environment': {'python': platform.python_version(),
                        'numpy': np.__version__},
    }
    return record, elapsed


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mission', type=Path, action='append',
                        help='Mission file; repeat for several (default: all)')
    parser.add_argument('--input', type=Path, default=DEFAULT_MISSIONS,
                        help='Folder scanned when --mission is not given')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--seconds', type=float, default=300.,
                        help='Time limit for one search; a multi-goal mission gets one per goal '
                             '(default: 300)')
    parser.add_argument('--max-nodes', type=int, default=200000,
                        help='Node limit for one propagation (default: 200000)')
    parser.add_argument('--no-clipping', action='store_true',
                        help='Disable funnel clipping')
    args = parser.parse_args()

    if not (args.seconds > 0 and math.isfinite(args.seconds)):
        parser.error('--seconds must be positive and finite')
    if args.max_nodes < 1:
        parser.error('--max-nodes must be positive')
    missions = ([path.resolve() for path in args.mission] if args.mission
                else sorted(args.input.glob(f'*{MISSION_SUFFIX}')))
    if not missions:
        fail(f'no mission in {args.input}; run "python3 main.py data" first')
    args.output.mkdir(parents=True, exist_ok=True)

    total = len(missions)
    for index, path in enumerate(missions, 1):
        if not path.is_file():
            fail(f'missing mission {path}')
        # The city mission needs about three minutes, so announce each solve:
        # without this line a silent terminal looks like a hang.
        mission = mission_id(path)
        print(f'[{index}/{total}] {mission}: solving', flush=True)
        record, elapsed = plan_mission(path, args.seconds, args.max_nodes,
                                       not args.no_clipping)
        output = args.output / f'{mission}.routes.json'
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')
        temporary.replace(output)
        longest = max(route['length'] for route in record['routes'])
        print(f'{mission}: {len(record["routes"])} route(s), '
              f'dài nhất {longest:.3f}, {elapsed:.1f}s', flush=True)
        print(f'Save at: {output}')


if __name__ == '__main__':
    main()
