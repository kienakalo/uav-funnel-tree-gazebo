#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, subprocess, sys, pathlib).
"""Run the project pipeline from one entry point.

Stages:
  data      raw -> processed: copy fixtures, standardize the scene, convert
            fixtures to GLB, triangulate the navigation surface, render previews
  plan      rebuild the delivery plan, the surface plan and the MMP comparison
  simulate  open the force-feedback Gazebo run (needs a display)
  verify    geometry checks and artifact/hash consistency
  flow      print the stages and the commands they run

Examples:
  python3 main.py flow
  python3 main.py data
  python3 main.py data verify
  python3 main.py verify
  python3 main.py all          # data + verify, no Gazebo
  python3 main.py simulate     # runs scripts/run_funnel_physics.sh

`data` and `verify` only need NumPy (and Shapely for triangulation). `plan`
rewrites generated artifacts and therefore changes their fingerprints; run it
only when the city asset or the planning code changed. `simulate` needs Gazebo
and must run in a terminal with a display.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv/bin/python'
PYTHON = str(VENV) if VENV.is_file() else sys.executable

STAGES = {
    'data': [
        [PYTHON, 'tools/copy_meshes.py', '--write'],
        [PYTHON, 'tools/standardize.py'],
        [PYTHON, 'tools/off2glb.py'],
        [PYTHON, 'tools/triangulation.py', '--force'],
        [PYTHON, 'tools/data_viz.py', '--all'],
    ],
    'plan': [
        [PYTHON, 'tools/plan_funnel_delivery.py'],
        [PYTHON, 'tools/plan_surface_delivery.py', '--cell', '5', '--coverage', 'city'],
        [PYTHON, 'tools/compare_surface_geodesic.py'],
    ],
    'simulate': [
        ['bash', 'scripts/run_funnel_physics.sh', 'surface_delivery'],
    ],
    'verify': [
        [PYTHON, 'check.py'],
        [PYTHON, 'tools/verify_project_results.py'],
    ],
}

DESCRIPTIONS = {
    'data': 'raw -> processed (fixtures, scene, GLB, surface, previews)',
    'plan': 'rebuild delivery/surface plan and the MMP comparison',
    'simulate': 'Gazebo force-feedback run (needs a display)',
    'verify': 'geometry checks and artifact/hash consistency',
}

ALIASES = {'all': ['data', 'verify']}


def display(command):
    shown = list(command)
    if shown and shown[0] == PYTHON:
        shown[0] = '.venv/bin/python' if VENV.is_file() else 'python3'
    return ' '.join(shown)


def expand(names):
    result = []
    for name in names:
        for stage in ALIASES.get(name, [name]):
            if stage not in result:
                result.append(stage)
    return result


def show_flow():
    print('Stages:')
    for name, description in DESCRIPTIONS.items():
        print(f'  {name:9s} {description}')
        for command in STAGES[name]:
            print('            ' + display(command))
    print('\nAliases:')
    print('  all       data + verify (no Gazebo)')


def run_stage(name, dry_run):
    commands = STAGES[name]
    print(f'\n== {name}: {DESCRIPTIONS[name]} ==')
    for index, command in enumerate(commands, 1):
        printable = display(command)
        print(f'[{index}/{len(commands)}] {printable}', flush=True)
        if dry_run:
            continue
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode:
            raise SystemExit(f'Stage {name} failed: {printable}')
    return True


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stages', nargs='*', metavar='stage',
                        help='data, plan, simulate, verify, flow, or all')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the commands without running them')
    args = parser.parse_args()
    stages = args.stages or ['flow']
    if 'flow' in stages:
        show_flow()
        stages = [stage for stage in stages if stage != 'flow']
    unknown = [stage for stage in stages if stage not in STAGES and stage not in ALIASES]
    if unknown:
        parser.error(f'Unknown stage(s): {", ".join(unknown)}')
    for stage in expand(stages):
        run_stage(stage, args.dry_run)


if __name__ == '__main__':
    main()
