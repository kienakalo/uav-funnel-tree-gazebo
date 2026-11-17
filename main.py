#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, subprocess, sys, pathlib).
"""Run the data pipeline from one entry point.

Stages:
  data      raw -> processed: copy fixtures, standardize the scene, convert
            fixtures to GLB, triangulate the navigation surface, render previews,
            then record a START/GOAL mission
  plan      run Funnel for the saved missions, render the routes and compare
            their lengths with data/expected
  simulate  build one Gazebo world, fly the route, then validate the run
            (needs Gazebo Jetty and a display unless --headless)
  flow      print the stages and the commands they run

Examples:
  python3 main.py                        # data, then plan, then simulate
  python3 main.py data                   # only the data stage
  python3 main.py flow
  python3 main.py data
  python3 main.py data --dry-run
  python3 main.py data --no-all-meshes   # chỉ bề mặt thành phố
  python3 main.py data --force-missions  # chọn lại cả mesh đã có
  python3 main.py plan                   # lập tuyến + ảnh + đối chiếu
  python3 main.py simulate --goal g2     # dựng world, bay, kiểm kết quả
  python3 main.py simulate --headless    # chạy server, không mở GUI

The last step records a START/GOAL mission for every .off in
data/processed/meshes. --no-all-meshes limits it to the navigation surface,
and --force-missions replaces missions that already exist. The step is
interactive: run it in a terminal, or commit the mission files for a
non-interactive run.

A bare run executes data, plan and simulate in that order, so the simulate
stage needs Gazebo Jetty and a display unless --headless is passed; use
"python3 main.py data" and "python3 main.py plan" to run one stage only.

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
    'plan': [
        [PYTHON, 'tools/plan/run_funnel.py'],
        [PYTHON, 'tools/plan/route_viz.py'],
        [PYTHON, 'tools/plan/compare.py'],
    ],
    # Built by stage_commands because it takes a mission and a goal.
    'simulate': [],
}

DEFAULT_STAGES = ['data', 'plan', 'simulate']

DESCRIPTIONS = {
    'data': 'raw -> processed (fixtures, scene, GLB, surface, previews, mission)',
    'plan': 'funnel routes, route images and the reference comparison',
    'simulate': 'one Gazebo world, the flight and its validation',
}


def display(command):
    shown = list(command)
    if shown and shown[0] == PYTHON:
        shown[0] = '.venv/bin/python' if VENV.is_file() else 'python3'
    return ' '.join(shown)


def stage_commands(name, args):
    """Stage commands; the simulate stage is built from the mission and goal."""
    if name == 'simulate':
        mission = args.mission or 'city.standardized.triangulation'
        goal = args.goal or 'g1'
        # run_simulate.sh builds the world itself, so the stage only calls it
        # once and then validates the telemetry it leaves behind.
        run = ['bash', 'tools/simulate/run_simulate.sh',
               '--mission', mission, '--goal', goal]
        if args.headless:
            run.append('--headless')
        if args.software:
            run.append('--software')
        if args.show_surface:
            run.append('--show-surface')
        validate = [PYTHON, 'tools/simulate/validate.py',
                    '--mission', mission, '--goal', goal,
                    '--max-error', f'{args.max_error or 1.0:g}']
        if args.no_png:
            validate.append('--no-png')
        return [run, validate]
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
    print('\nNo stage given: data, plan and simulate are executed in that order. '
          'Use "flow" to only print this list.')


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
                        help='data, plan, simulate or flow')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the commands without running them')
    parser.add_argument('--all-meshes', action=argparse.BooleanOptionalAction,
                        default=True,
                        help='Bước mission: chọn START/GOAL cho mọi mesh .off '
                             '(mặc định). Dùng --no-all-meshes để chỉ chọn bề mặt '
                             'thành phố')
    parser.add_argument('--force-missions', action='store_true',
                        help='Bước mission: chọn lại cả khi đã có file mission')
    parser.add_argument('--mission', help='simulate: route stem '
                        '(default: city.standardized.triangulation)')
    parser.add_argument('--goal', help='simulate: goal id (default: g1)')
    parser.add_argument('--headless', action='store_true',
                        help='simulate: run the Gazebo server without the GUI')
    parser.add_argument('--software', action='store_true',
                        help='simulate: force software rendering')
    parser.add_argument('--show-surface', action='store_true',
                        help='simulate: draw the navigation surface as well')
    parser.add_argument('--max-error', type=float, default=None, metavar='M',
                        help='simulate: largest allowed tracking error (default: 1.0 m)')
    parser.add_argument('--no-png', action='store_true',
                        help='simulate: skip tracking.png')
    args = parser.parse_args()
    if args.force_missions and not args.all_meshes:
        parser.error('--force-missions needs --all-meshes; for one mesh run '
                     'tools/data/set_start_goal.py --force')
    simulate_flags = (args.mission or args.goal or args.headless or args.software
                      or args.show_surface or args.max_error is not None
                      or args.no_png)
    if simulate_flags and 'simulate' not in (args.stages or DEFAULT_STAGES):
        parser.error('--mission/--goal/--headless/--software/--show-surface/'
                     '--max-error/--no-png only apply to the simulate stage')
    if args.max_error is not None and not (args.max_error > 0):
        parser.error('--max-error must be positive')
    stages = args.stages or list(DEFAULT_STAGES)
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
