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
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv/bin/python'
PYTHON = str(VENV) if VENV.is_file() else sys.executable
DEFAULT_MISSION = 'city.standardized.triangulation'
DEFAULT_GOAL = 'g1'

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
    'simulate': [
        [PYTHON, 'tools/simulate/build_world.py',
         '--mission', DEFAULT_MISSION, '--goal', DEFAULT_GOAL],
        ['bash', 'tools/simulate/run_simulate.sh',
         '--mission', DEFAULT_MISSION, '--goal', DEFAULT_GOAL, '--no-build'],
        [PYTHON, 'tools/simulate/validate.py',
         '--mission', DEFAULT_MISSION, '--goal', DEFAULT_GOAL,
         '--max-error', '1'],
    ],
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


def mission_goals(mission):
    """Goal ids of a planned route, for the default all-goal simulate run."""
    path = ROOT / 'generated/routes' / f'{mission}.json'
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return [DEFAULT_GOAL]
    goals = [route.get('id') for route in record.get('routes') or []
             if route.get('id')]
    return goals or [DEFAULT_GOAL]


def stage_commands(name, args):
    """Stage commands, with the simulate mission and goal(s) applied."""
    commands = [list(command) for command in STAGES[name]]
    if name == 'simulate':
        mission = args.mission or DEFAULT_MISSION
        goals = [args.goal] if args.goal else mission_goals(mission)
        expanded = []
        for goal in goals:
            pair = [list(command) for command in commands]
            for command in pair:
                command[command.index('--mission') + 1] = mission
                command[command.index('--goal') + 1] = goal
            if args.show_surface:
                pair[0].append('--surface')
            if args.headless:
                pair[1].append('--headless')
            if args.software:
                pair[1].append('--software')
            if args.container is True:
                pair[1].append('--container')
            elif args.container is False:
                pair[1].append('--native')
            if args.image:
                pair[1] += ['--image', args.image]
            if args.gpu:
                pair[1] += ['--gpu', args.gpu]
            if args.keep_open:
                pair[1].append('--keep-open')
            if args.pull:
                pair[1].append('--pull')
            if args.max_error is not None:
                pair[2][pair[2].index('--max-error') + 1] = f'{args.max_error:g}'
            if args.no_png:
                pair[2].append('--no-png')
            expanded.extend(pair)
        return expanded
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


def step_label(command):
    """Short form of a command, without the interpreter or the repo prefix."""
    shown = list(command)
    if shown and shown[0] == PYTHON:
        shown = shown[1:]
    text = ' '.join(shown)
    return text.replace(str(ROOT) + '/', '').replace(str(ROOT), '.')


def stream(command):
    """Run a tool and print its output indented, so steps stay distinct."""
    environment = dict(os.environ, PYTHONUNBUFFERED='1')
    process = subprocess.Popen(command, cwd=ROOT, env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    for line in process.stdout:
        text = line.rstrip('\n')
        text = text.replace(str(ROOT) + '/', '').replace(str(ROOT), '.')
        print('    ' + text, flush=True)
    return process.wait()


def capture(command):
    """Quiet mode: keep the output, but print it only when the step fails."""
    environment = dict(os.environ, PYTHONUNBUFFERED='1')
    process = subprocess.run(command, cwd=ROOT, env=environment,
                             capture_output=True, text=True)
    if process.returncode:
        sys.stdout.write(process.stdout)
        sys.stderr.write(process.stderr)
    return process.returncode


def run_stage(name, args, index, total):
    commands = stage_commands(name, args)
    line = '=' * 72
    print(f'\n{line}')
    print(f'Stage {index}/{total}: {name} — {DESCRIPTIONS[name]}')
    print(f'{len(commands)} step(s)' + (' — dry run' if args.dry_run else ''))
    print(line)
    started = time.monotonic()
    for step, command in enumerate(commands, 1):
        print(f'\n[{name} {step}/{len(commands)}] {step_label(command)}', flush=True)
        if args.dry_run:
            print('    $ ' + display(command), flush=True)
            continue
        step_started = time.monotonic()
        code = capture(command) if args.quiet else stream(command)
        if code:
            raise SystemExit(f'Stage {name} failed at step {step}: '
                             f'{step_label(command)}')
        print(f'    done in {time.monotonic() - step_started:.1f} s', flush=True)
    print(f'\n{name}: ok in {time.monotonic() - started:.1f} s', flush=True)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stages', nargs='*', metavar='stage',
                        help='data, plan, simulate or flow')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the commands without running them')
    parser.add_argument('--quiet', action='store_true',
                        help='Hide tool output unless a step fails')
    parser.add_argument('--all-meshes', action=argparse.BooleanOptionalAction,
                        default=True,
                        help='Bước mission: chọn START/GOAL cho mọi mesh .off '
                             '(mặc định). Dùng --no-all-meshes để chỉ chọn bề mặt '
                             'thành phố')
    parser.add_argument('--force-missions', action='store_true',
                        help='Bước mission: chọn lại cả khi đã có file mission')
    parser.add_argument('--mission', help='simulate: route stem '
                        '(default: city.standardized.triangulation)')
    parser.add_argument('--goal', help='simulate: fly one goal only '
                        '(default: every goal in the route)')
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
    parser.add_argument('--container', action=argparse.BooleanOptionalAction,
                        default=None,
                        help='simulate: fly in the Gazebo container (default) or, '
                             'with --no-container, with the gz on PATH')
    parser.add_argument('--image', default=None,
                        help='simulate: Gazebo container image '
                             '(default: ghcr.io/openrobotics/gazebo:jetty-full)')
    parser.add_argument('--gpu', choices=('auto', 'nvidia', 'intel', 'software'),
                        default=None,
                        help='simulate: GPU for the GUI (default: auto)')
    parser.add_argument('--keep-open', action='store_true',
                        help='simulate: leave the window open after the route, '
                             'instead of closing it at completion')
    parser.add_argument('--pull', action='store_true',
                        help='simulate: docker pull the Gazebo image first')
    args = parser.parse_args()
    if args.force_missions and not args.all_meshes:
        parser.error('--force-missions needs --all-meshes; for one mesh run '
                     'tools/data/set_start_goal.py --force')
    simulate_flags = (args.mission or args.goal or args.headless or args.software
                      or args.show_surface or args.max_error is not None
                      or args.no_png or args.container is not None or args.image
                      or args.gpu
                      or args.keep_open or args.pull)
    if simulate_flags and 'simulate' not in (args.stages or DEFAULT_STAGES):
        parser.error('--mission/--goal/--headless/--software/--show-surface/'
                     '--max-error/--no-png/--container/--image/--gpu/'
                     '--keep-open/--pull only apply to the simulate stage')
    if args.max_error is not None and not (args.max_error > 0):
        parser.error('--max-error must be positive')
    stages = args.stages or list(DEFAULT_STAGES)
    if 'flow' in stages:
        show_flow(args)
        stages = [stage for stage in stages if stage != 'flow']
    unknown = [stage for stage in stages if stage not in STAGES]
    if unknown:
        parser.error(f'Unknown stage(s): {", ".join(unknown)}')
    started = time.monotonic()
    for index, stage in enumerate(stages, 1):
        run_stage(stage, args, index, len(stages))
    if len(stages) > 1 and not args.dry_run:
        print(f'\nAll {len(stages)} stages finished in '
              f'{time.monotonic() - started:.1f} s')


if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:  # e.g. piping into head or less
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
