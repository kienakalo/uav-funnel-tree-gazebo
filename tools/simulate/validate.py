#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib; Python stdlib (argparse, csv, json, math, sys,
# pathlib).
"""Check one Gazebo run against the route it was given.

Input:  generated/simulate/<mission>-<goal>/physics_telemetry.csv
        the telemetry metadata beside it
Output: validation.json and tracking.png in the same folder

Two different questions are answered here. Validity: the last telemetry row is
in the complete phase and the vehicle stopped within --arrival-tolerance of the
goal. Quality: the largest position error stayed under --max-error (default
1.0 m), which is a reporting target, not a condition for the run to count. The
exit code is non-zero only for an invalid run, so a stage stops on a broken
flight and not on a corner the vehicle lagged behind by a few centimetres.

Examples:
  .venv/bin/python tools/simulate/validate.py --mission city.standardized.triangulation --goal g1
  .venv/bin/python tools/simulate/validate.py --run generated/simulate/cliff-v3 --max-error 0.5
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
from figstamp import save as save_stamped

DEFAULT_ROOT = ROOT / 'generated/simulate'
LABELS = {
    'max_error_limit': ('error limit', ' m'),
    'speed': ('speed', ' m/s'),
    'max_acceleration': ('accel', ' m/s²'),
    'dwell': ('dwell', ' s'),
    'start_delay': ('delay', ' s'),
    'simplify': ('simplify', ' m'),
    'collision_grid': ('collision grid', ' m'),
    'goal': ('goal', ''),
    'rows': ('rows', ''),
    'duration': ('duration', ''),
    'max_error': ('max error', ''),
    'mean_error': ('mean', ''),
    'completed': ('completed', ''),
    'valid': ('valid', ''),
    'final_error': ('final error', ' m'),
}


def stamp_data(metadata, result, limit):
    """Flight settings and outcome, for the footer and the sidecar."""
    metadata = metadata or {}
    flight = metadata.get('flight') or {}
    parameters = {
        'speed': flight.get('speed'),
        'max_acceleration': flight.get('max_acceleration'),
        'dwell': flight.get('dwell'),
        'start_delay': flight.get('start_delay'),
        'simplify': metadata.get('simplify_tolerance'),
        'collision_grid': (metadata.get('collision_stats') or {}).get('cell'),
        'max_error_limit': limit,
    }
    facts = {
        'goal': metadata.get('goal'),
        'rows': result['rows'],
        'duration': f'{result["duration"]:.1f} s',
        'max_error': f'{result["max_error"]:.3f} m',
        'mean_error': f'{result["mean_error"]:.3f} m',
        'completed': result['completed'],
        'valid': result.get('valid'),
        'final_error': f'{result["final_error"]:.3f} m',
    }
    sources = {
        'scene_sha256': metadata.get('scene_sha256'),
        'surface_sha256': metadata.get('surface_sha256'),
        'route_sha256': (metadata.get('route_sha256')
                         or result.get('route_sha256')),
        'telemetry_sha256': result.get('telemetry_sha256'),
    }
    return parameters, facts, sources


def fail(message):
    raise SystemExit(f'validate: {message}')


def relative(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def read_rows(path):
    with Path(path).open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        fail(f'{relative(path)} has no telemetry rows')
    required = {'sim_time', 'x', 'y', 'z', 'error', 'vx', 'vy', 'vz', 'phase'}
    if not required.issubset(rows[0]):
        fail(f'{relative(path)} is missing columns: '
             f'{", ".join(sorted(required - set(rows[0])))}')
    return rows


def run_folder(args):
    if args.run:
        return args.run.resolve()
    return (args.root / f'{args.mission}-{args.goal}').resolve()


def analyse(rows, max_error):
    times = [float(row['sim_time']) for row in rows]
    errors = [float(row['error']) for row in rows]
    speeds = [math.hypot(float(row['vx']), float(row['vy']), float(row['vz']))
              for row in rows]
    accelerations = []
    for previous, current in zip(rows, rows[1:]):
        dt = float(current['sim_time']) - float(previous['sim_time'])
        if dt <= 0:
            continue
        dvx = float(current['vx']) - float(previous['vx'])
        dvy = float(current['vy']) - float(previous['vy'])
        dvz = float(current['vz']) - float(previous['vz'])
        accelerations.append(math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz) / dt)
    return {
        'rows': len(rows),
        'completed': rows[-1]['phase'] == 'complete',
        'duration': round(times[-1] - times[0], 3),
        'max_error': round(max(errors), 4),
        'mean_error': round(sum(errors) / len(errors), 4),
        'final_error': round(errors[-1], 4),
        'max_speed': round(max(speeds), 4),
        'max_acceleration': round(max(accelerations, default=0.), 4),
        'max_error_limit': max_error,
    }


def render(rows, folder, title, limit, metadata, result):
    times = [float(row['sim_time']) for row in rows]
    errors = [float(row['error']) for row in rows]
    xs = [float(row['x']) for row in rows]
    ys = [float(row['y']) for row in rows]
    route_path = folder / 'route.json'
    waypoints = []
    if route_path.is_file():
        waypoints = json.loads(route_path.read_text(encoding='utf-8')).get('waypoints') or []

    figure, (map_axes, error_axes) = plt.subplots(
        2, 1, figsize=(10, 9.5), gridspec_kw={'height_ratios': [1.25, 1]})
    if waypoints:
        px = [float(point[0]) for point in waypoints]
        py = [float(point[1]) for point in waypoints]
        map_axes.plot(px, py, color='#e67e22', linewidth=2.2, label='planned route')
        map_axes.scatter(px[1:-1], py[1:-1], color='#f1c40f', s=14, zorder=4,
                         label='waypoints')
        map_axes.scatter(px[0], py[0], color='#27ae60', s=70, zorder=5, label='start')
        map_axes.scatter(px[-1], py[-1], color='#e91e63', s=70, zorder=5, label='goal')
    map_axes.plot(xs, ys, color='#8e44ad', linewidth=1.6, label='flown path')
    map_axes.set_aspect('equal', adjustable='datalim')
    map_axes.set_xlabel('x (m)')
    map_axes.set_ylabel('y (m)')
    map_axes.set_title('planned route and flown path, top view')
    map_axes.grid(alpha=.3)
    map_axes.legend(loc='best', fontsize=9)

    error_axes.plot(times, errors, color='#c0392b', linewidth=1.4,
                    label='position error')
    error_axes.axhline(limit, color='#2c3e50', linestyle='--', linewidth=1.,
                       label=f'limit {limit:g} m')
    error_axes.set_xlabel('simulated time (s)')
    error_axes.set_ylabel('error (m)')
    error_axes.set_title(title)
    error_axes.grid(alpha=.3)
    error_axes.legend(loc='upper right')

    figure.tight_layout()
    output = folder / 'tracking.png'
    parameters, facts, sources = stamp_data(metadata, result, limit)
    image, sidecar = save_stamped(
        figure, output, parameters=parameters, facts=facts, sources=sources,
        labels=LABELS, script=__file__, subject=title)
    plt.close(figure)
    return image, sidecar


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path,
                        help='Run folder (default: generated/simulate/<mission>-<goal>)')
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--mission', default='city.standardized.triangulation')
    parser.add_argument('--goal', default='g1')
    parser.add_argument('--max-error', type=float, default=1.0, metavar='M',
                        help='Quality target: largest position error worth '
                             'reporting as on-route (default: 1.0). Missing it '
                             'does not fail the run')
    parser.add_argument('--arrival-tolerance', type=float, default=0.5,
                        metavar='M',
                        help='How close to the goal the last telemetry row must '
                             'end for the run to be valid (default: 0.5)')
    parser.add_argument('--no-png', action='store_true',
                        help='Do not write tracking.png')
    args = parser.parse_args()

    if not (args.max_error > 0 and math.isfinite(args.max_error)):
        parser.error('--max-error must be positive and finite')
    if not (args.arrival_tolerance > 0 and math.isfinite(args.arrival_tolerance)):
        parser.error('--arrival-tolerance must be positive and finite')
    folder = run_folder(args)
    telemetry = folder / 'physics_telemetry.csv'
    metadata_path = folder / 'telemetry_metadata.json'
    if not telemetry.is_file():
        fail(f'missing {relative(telemetry)}; run tools/simulate/run_simulate.sh first')
    rows = read_rows(telemetry)
    result = analyse(rows, args.max_error)
    metadata = {}
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    # The flight settings live in the world build, not in the telemetry record.
    world_path = folder / 'world_metadata.json'
    world = {}
    if world_path.is_file():
        world = json.loads(world_path.read_text(encoding='utf-8'))
    stamp_metadata = dict(world)
    for key, value in metadata.items():
        if value is not None:
            stamp_metadata[key] = value
    valid = (result['completed'] and
             result['final_error'] <= args.arrival_tolerance)
    result.update({
        'mission': metadata.get('mission'),
        'goal': metadata.get('goal'),
        'world': metadata.get('world'),
        'route_sha256': metadata.get('route_sha256'),
        'run_id': metadata.get('run_id'),
        'nominal_duration': metadata.get('nominal_duration'),
        'telemetry': str(relative(telemetry)),
        'telemetry_sha256': hashlib.sha256(telemetry.read_bytes()).hexdigest(),
        'arrival_tolerance': args.arrival_tolerance,
        'valid': valid,
        'passed': valid and result['max_error'] <= args.max_error,
    })
    output = folder / 'validation.json'
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

    title = (f'{args.mission}-{args.goal}: {result["rows"]} rows, '
             f'max error {result["max_error"]:.2f} m')
    if not args.no_png:
        image, sidecar = render(rows, folder, title, args.max_error,
                                stamp_metadata, result)
        print(f'Save at: {image}')
        print(f'Save at: {sidecar}')
    print(f'Rows {result["rows"]}, duration {result["duration"]:.1f} s, '
          f'max error {result["max_error"]:.3f} m, mean {result["mean_error"]:.3f} m')
    print(f'Max speed {result["max_speed"]:.2f} m/s, '
          f'max accel {result["max_acceleration"]:.2f} m/s², '
          f'completed {result["completed"]}, valid {result["valid"]}')
    print(f'Save at: {output}')
    if not result['valid']:
        reasons = []
        if not result['completed']:
            reasons.append('the last row is not in the complete phase')
        if result['final_error'] > args.arrival_tolerance:
            reasons.append(f'final error {result["final_error"]:.3f} m > '
                           f'{args.arrival_tolerance:g} m')
        raise SystemExit('validate: run is not valid: ' + '; '.join(reasons))
    if not result['passed']:
        print(f'    quality target missed: max error {result["max_error"]:.3f} m '
              f'> {args.max_error:g} m (mean {result["mean_error"]:.3f} m); '
              'the run is still valid')


if __name__ == '__main__':
    main()
