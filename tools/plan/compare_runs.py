#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, json, shutil, sys, pathlib).
"""Compare archived runs side by side.

``main.py --label NAME`` copies the numbers and the pictures of a finished run
to results/runs/NAME/, which no stage clears. A run with a 5 m grid and a run
with a 4 m grid can therefore be compared after the fact, even though both
wrote the same file names in generated/.

This tool reads the manifests of those archives, prints one table with a
column per run and writes it as Markdown for the report. The route and
tracking pictures are copied next to it with the label in the file name, so two
pictures cannot be confused.

Switching the grid changes the surface, so the planned routes and the flights
are compared with their own geometry; the table shows the surface SHA next to
the parameters for that reason.

Examples:
  .venv/bin/python tools/plan/compare_runs.py
  .venv/bin/python tools/plan/compare_runs.py cell5 cell4
  .venv/bin/python tools/plan/compare_runs.py --output results/cell-grid
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS = ROOT / 'results/runs'
DEFAULT_OUTPUT = ROOT / 'results/comparison'


def fail(message):
    raise SystemExit(f'compare_runs: {message}')


def relative(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def flatten(manifest):
    """Parameters of a manifest, with the files they came from as fallback.

    A run that only flew the world asked for the flight settings and logged
    those; the surface grid lives in the surface sidecar and the solver limits
    in the route file. Merging them keeps one column comparable even when the
    two runs went through different stages.
    """
    values = {}
    for group in (manifest.get('parameters') or {}).values():
        if isinstance(group, dict):
            values.update(group)
    surface = (manifest.get('surface') or {}).get('parameters') or {}
    for key, alias in (('cell', 'cell'), ('clearance', 'vertical_clearance'),
                       ('half_width', 'horizontal_half_width'),
                       ('max_slope', 'max_axis_slope')):
        if values.get(key) is None and surface.get(alias) is not None:
            values[key] = surface[alias]
    solver = (manifest.get('routes') or {}).get('solver') or {}
    for key, alias in (('seconds', 'timeout_seconds'),
                       ('max_nodes', 'max_nodes'), ('clipping', 'clipping')):
        if values.get(key) is None and solver.get(alias) is not None:
            values[key] = solver[alias]
    flight = manifest.get('flight_parameters') or {}
    for key, alias in (('speed', 'speed'), ('max_accel', 'max_acceleration'),
                       ('dwell', 'dwell'), ('start_delay', 'start_delay')):
        if values.get(key) is None and flight.get(alias) is not None:
            values[key] = flight[alias]
    if values.get('simplify') is None:
        values['simplify'] = manifest.get('simplify_tolerance')
    return values


def labels_in(runs):
    found = [path.parent.name for path in sorted(runs.glob('*/manifest.json'))]
    if not found:
        fail(f'không có archive nào trong {relative(runs)}; chạy '
             'main.py --label <tên> trước')
    return found


def read_manifest(runs, label):
    path = runs / label / 'manifest.json'
    if not path.is_file():
        fail(f'không có {relative(path)}; các label đang có: '
             + ', '.join(labels_in(runs)))
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        fail(f'{relative(path)} không phải JSON hợp lệ')


def rows_of(manifest):
    """Ordered (label, value) rows of one archive."""
    values = flatten(manifest)
    surface = manifest.get('surface') or {}
    routes = manifest.get('routes') or {}
    flight = manifest.get('flight') or {}
    rows = [
        ('commit', manifest.get('commit')),
        ('ghi lúc', (manifest.get('created_at') or '')[:16].replace('T', ' ')),
        ('cell (m)', values.get('cell')),
        ('clearance (m)', values.get('clearance')),
        ('half-width (m)', values.get('half_width')),
        ('max-slope (m/m)', values.get('max_slope')),
        ('SHA bề mặt', (surface.get('sha256') or '')[:8] or None),
        ('solver (s)', values.get('seconds')),
        ('max nodes', values.get('max_nodes')),
        ('clipping', values.get('clipping')),
        ('planning (s)', routes.get('planning_seconds')),
        ('speed (m/s)', values.get('speed')),
        ('max accel (m/s²)', values.get('max_accel')),
        ('dwell (s)', values.get('dwell')),
        ('start delay (s)', values.get('start_delay')),
        ('simplify (m)', values.get('simplify')),
        ('collision grid (m)', values.get('collision_grid')),
    ]
    for goal in manifest.get('goals') or []:
        route = routes.get(goal) or {}
        result = flight.get(goal) or {}
        rows += [
            (f'route {goal} (m)', route.get('length')),
            (f'waypoints {goal}', route.get('waypoints')),
            (f'flight {goal} (s)', result.get('duration')),
            (f'max error {goal} (m)', result.get('max_error')),
            (f'mean error {goal} (m)', result.get('mean_error')),
            # The target is a quality mark, not a condition for the flight to
            # count: a run can be valid and still miss it at one corner.
            (f'mốc bám {goal}', None if result.get('passed') is None
             else ('đạt' if result['passed'] else 'trượt')),
        ]
    return rows


def text(value):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'Y' if value else 'N'
    if isinstance(value, float):
        return f'{value:.4g}'
    return str(value)


def collect(runs, labels):
    table, order = {}, []
    for label in labels:
        manifest = read_manifest(runs, label)
        table[label] = dict(rows_of(manifest))
        for key in table[label]:
            if key not in order:
                order.append(key)
    return table, order


def markdown(labels, table, order):
    lines = ['| Thông số | ' + ' | '.join(labels) + ' |',
             '| --- | ' + ' | '.join('---' for _ in labels) + ' |']
    for key in order:
        cells = [text(table[label].get(key)) for label in labels]
        lines.append(f'| {key} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


def aligned(labels, table, order):
    width = max(len(key) for key in order + ['Thông số'])
    columns = []
    for label in labels:
        cells = [text(table[label].get(key)) for key in order]
        columns.append(max([len(label)] + [len(cell) for cell in cells]))
    lines = ['  '.join(['Thông số'.ljust(width)]
                       + [label.ljust(size) for label, size in zip(labels, columns)]),
             '  '.join(['-' * width] + ['-' * size for size in columns])]
    for number, key in enumerate(order):
        cells = [text(table[label].get(key)).ljust(size)
                 for label, size in zip(labels, columns)]
        lines.append('  '.join([key.ljust(width)] + cells))
    return '\n'.join(lines)


def copy_images(runs, labels, output):
    copied = []
    for label in labels:
        source = runs / label / 'route.png'
        if source.is_file():
            copied.append((source, output / f'{label}-route.png'))
        for folder in sorted(path for path in (runs / label).iterdir()
                             if path.is_dir()):
            picture = folder / 'tracking.png'
            if picture.is_file():
                copied.append((picture,
                               output / f'{label}-{folder.name}-tracking.png'))
    return copied


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('labels', nargs='*', metavar='label',
                        help='Archive labels (mặc định: mọi archive, theo tên)')
    parser.add_argument('--runs', type=Path, default=DEFAULT_RUNS,
                        help='Thư mục archive (mặc định: results/runs)')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                        help='Thư mục ghi bảng và ảnh (mặc định: results/comparison)')
    args = parser.parse_args()

    runs = args.runs.resolve()
    labels = args.labels or labels_in(runs)
    table, order = collect(runs, labels)
    print(aligned(labels, table, order))

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = output / 'comparison.md'
    report.write_text(markdown(labels, table, order), encoding='utf-8')
    print(f'Save at: {relative(report)}')
    payload = output / 'comparison.json'
    payload.write_text(json.dumps({
        'labels': labels,
        'rows': order,
        'values': {label: {key: table[label].get(key) for key in order}
                   for label in labels},
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Save at: {relative(payload)}')
    pictures = copy_images(runs, labels, output)
    for source, destination in pictures:
        shutil.copy2(source, destination)
        print(f'Save at: {relative(destination)}')
    if pictures:
        print(f'{len(pictures)} ảnh của {len(labels)} lần chạy nằm cạnh bảng.')


if __name__ == '__main__':
    main()
