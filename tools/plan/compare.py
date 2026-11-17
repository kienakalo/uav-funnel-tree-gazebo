#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (argparse, json, math, sys, pathlib);
# local modules (funnel_tree, mesh_off).
"""Compare Funnel route lengths with the saved reference paths.

Input:  data/expected/*.paths.json   (5 fixtures; source vertex and one path
        per vertex, coordinates rounded to four decimals)
        data/processed/meshes/<mesh>.off
Output: generated/compare/<mesh>.json  (per-vertex lengths and differences)
        generated/compare/summary.json (which meshes passed, failed, skipped)

Meshes without a reference file are listed as skipped: the project does not
ship a second solver, and an edge-graph baseline would only bound the surface
distance, not reproduce it. No new dependency is used.

The reference coordinates are rounded to four decimals, so a route built from
the exact vertex positions differs by about 1e-5 in length; --tolerance
defaults to 1e-4 relative to absorb that rounding.

Examples:
  .venv/bin/python tools/plan/compare.py
  .venv/bin/python tools/plan/compare.py --tolerance 1e-5
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT / 'algo'))
from funnel_tree import solve
from mesh_off import read_mesh

DEFAULT_EXPECTED = ROOT / 'data/expected'
DEFAULT_MESHES = ROOT / 'data/processed/meshes'
DEFAULT_OUTPUT = ROOT / 'generated/compare'


def relative(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def route_length(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def compare(mesh_stem, expected_path, mesh_dir, seconds, tolerance):
    record = json.loads(expected_path.read_text(encoding='utf-8'))
    source = record['source']
    mesh_path = mesh_dir / f'{mesh_stem}.off'
    if not mesh_path.is_file():
        raise SystemExit(f'compare: missing mesh {relative(mesh_path)}')
    mesh = read_mesh(mesh_path)
    paths, stats = solve(mesh, source, timeout=seconds)
    reference = record['paths']
    if len(reference) != len(mesh.points):
        raise SystemExit(f'compare: {relative(expected_path)} has {len(reference)} '
                         f'paths for {len(mesh.points)} vertices')
    rows, failures = [], []
    for vertex, expected in enumerate(reference):
        expected_length = route_length(expected)
        funnel_length = route_length(paths[vertex])
        if expected_length == 0:
            error = abs(funnel_length)
        else:
            error = abs(funnel_length - expected_length) / expected_length
        rows.append({'vertex': vertex,
                     'reference_length': round(expected_length, 9),
                     'funnel_length': round(funnel_length, 9),
                     'relative_error': float(f'{error:.3e}')})
        if error > tolerance:
            failures.append(vertex)
    return {
        'mesh': mesh_stem,
        'mesh_sha256': hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        'reference': str(relative(expected_path)),
        'source': source,
        'tolerance': tolerance,
        'vertices': len(rows),
        'max_relative_error': max(row['relative_error'] for row in rows),
        'mean_relative_error': sum(row['relative_error'] for row in rows) / len(rows),
        'failures': failures,
        'stats': stats,
        'paths': rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--expected', type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument('--meshes', type=Path, default=DEFAULT_MESHES)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--seconds', type=float, default=300.,
                        help='Time limit for one solve (default: 300)')
    parser.add_argument('--tolerance', type=float, default=1e-4,
                        help='Relative length tolerance (default: 1e-4)')
    args = parser.parse_args()
    if args.tolerance <= 0:
        parser.error('--tolerance must be positive')
    references = sorted(args.expected.glob('*.paths.json'))
    if not references:
        raise SystemExit(f'compare: no reference in {relative(args.expected)}')
    args.output.mkdir(parents=True, exist_ok=True)

    passed, failed, skipped = [], [], []
    for expected_path in references:
        mesh_stem = expected_path.name.replace('.paths.json', '')
        print(f'\n{mesh_stem}:', flush=True)
        report = compare(mesh_stem, expected_path, args.meshes, args.seconds,
                         args.tolerance)
        output = args.output / f'{mesh_stem}.json'
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')
        temporary.replace(output)
        verdict = 'failed' if report['failures'] else 'passed'
        (failed if report['failures'] else passed).append(mesh_stem)
        print(f'  {report["vertices"]} đỉnh, sai lệch lớn nhất '
              f'{report["max_relative_error"]:.2e}, trung bình '
              f'{report["mean_relative_error"]:.2e} — {verdict}', flush=True)
        print(f'  Save at: {output}')

    # *.glb2off.off is the whole scene exported for viewing and for the report,
    # not a navigation mesh: no expected path can exist for it.
    known = {path.stem for path in args.meshes.glob('*.off')
             if not path.name.endswith('.glb2off.off')}
    compared = {path.name.replace('.paths.json', '') for path in references}
    skipped = sorted(known - compared)
    summary = {
        'passed': passed,
        'failed': failed,
        'skipped': skipped,
        'tolerance': args.tolerance,
        'note': 'skipped meshes have no data/expected reference; the project does '
                'not ship a second solver and an edge-graph baseline would only '
                'bound the surface distance',
    }
    summary_path = args.output / 'summary.json'
    summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'\n{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped: '
          f'{", ".join(skipped)}')
    print(f'Save at: {summary_path}')
    if failed:
        raise SystemExit(f'compare: route lengths differ from the reference on '
                         f'{", ".join(failed)}')


if __name__ == '__main__':
    main()
