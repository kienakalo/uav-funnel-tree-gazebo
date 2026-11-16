#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, subprocess, sys, pathlib).
"""Run the data pipeline from one entry point.

Stages:
  data      raw -> processed: copy fixtures, standardize the scene, convert
            fixtures to GLB, triangulate the navigation surface, render previews,
            then record a START/GOAL mission
  flow      print the stage and the commands it runs

Examples:
  python3 main.py                        # same as: python3 main.py data
  python3 main.py flow
  python3 main.py data
  python3 main.py data --dry-run
  python3 main.py data --no-all-meshes   # chỉ bề mặt thành phố
  python3 main.py data --force-missions  # chọn lại cả mesh đã có

The last step records a START/GOAL mission for every .off in
data/processed/meshes. --no-all-meshes limits it to the navigation surface,
and --force-missions replaces missions that already exist. The step is
interactive: run it in a terminal, or commit the mission files for a
non-interactive run.

The data stage needs NumPy, Matplotlib (previews) and Shapely (triangulation).
It rewrites data/processed/ and generated/data_viz/, and writes the missions to
data/processed/missions/.
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
        [PYTHON, 'tools/data/copy_meshes.py', '--write'],
        [PYTHON, 'tools/data/standardize.py'],
        [PYTHON, 'tools/data/off2glb.py'],
        [PYTHON, 'tools/data/triangulation.py', '--force'],
        [PYTHON, 'tools/data/data_viz.py', '--all'],
        [PYTHON, 'tools/data/set_start_goal.py'],
    ],
}

DESCRIPTIONS = {
    'data': 'raw -> processed (fixtures, scene, GLB, surface, previews, mission)',
}


def display(command):
    shown = list(command)
    if shown and shown[0] == PYTHON:
        shown[0] = '.venv/bin/python' if VENV.is_file() else 'python3'
    return ' '.join(shown)


def stage_commands(name, args):
    """Stage commands, with the mission flags appended to the last step."""
    commands = [list(command) for command in STAGES[name]]
    if name == 'data':
        if args.all_meshes:
            commands[-1].append('--all-meshes')
        if args.force_missions:
            commands[-1].append('--force')
    return commands


def show_flow(args):
    print('Stages:')
    for name, description in DESCRIPTIONS.items():
        print(f'  {name:9s} {description}')
        for command in stage_commands(name, args):
            print('            ' + display(command))
    print('\nNo stage given: data is executed. Use "flow" to only print this list.')


def run_stage(name, args):
    commands = stage_commands(name, args)
    print(f'\n== {name}: {DESCRIPTIONS[name]} ==')
    for index, command in enumerate(commands, 1):
        printable = display(command)
        print(f'[{index}/{len(commands)}] {printable}', flush=True)
        if args.dry_run:
            continue
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode:
            raise SystemExit(f'Stage {name} failed: {printable}')
    return True


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stages', nargs='*', metavar='stage',
                        help='data or flow')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the commands without running them')
    parser.add_argument('--all-meshes', action=argparse.BooleanOptionalAction,
                        default=True,
                        help='Bước mission: chọn START/GOAL cho mọi mesh .off '
                             '(mặc định). Dùng --no-all-meshes để chỉ chọn bề mặt '
                             'thành phố')
    parser.add_argument('--force-missions', action='store_true',
                        help='Bước mission: chọn lại cả khi đã có file mission')
    args = parser.parse_args()
    if args.force_missions and not args.all_meshes:
        parser.error('--force-missions needs --all-meshes; for one mesh run '
                     'tools/data/set_start_goal.py --force')
    stages = args.stages or ['data']
    if 'flow' in stages:
        show_flow(args)
        stages = [stage for stage in stages if stage != 'flow']
    unknown = [stage for stage in stages if stage not in STAGES]
    if unknown:
        parser.error(f'Unknown stage(s): {", ".join(unknown)}')
    for stage in stages:
        run_stage(stage, args)


if __name__ == '__main__':
    main()
