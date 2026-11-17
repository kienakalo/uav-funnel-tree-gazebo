#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, json, math, os, shutil, subprocess,
# sys, time, dataclasses, pathlib).
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
  python3 main.py --fresh                # clear old results, then run everything
  python3 main.py --no-ask               # keep every default, ask nothing
  python3 main.py data --dry-run
  python3 main.py data --no-all-meshes   # chỉ bề mặt thành phố
  python3 main.py data --force-missions  # chọn lại cả mesh đã có
  python3 main.py plan                   # lập tuyến + ảnh + đối chiếu
  python3 main.py simulate --goal g2     # dựng world, bay, kiểm kết quả
  python3 main.py simulate --headless    # chạy server, không mở GUI

A bare run executes data, plan and simulate in that order. Before the first
stage it asks whether to clear the old results; at each step that has
parameters it asks for them, showing the default in brackets, so pressing
Enter keeps the value the documentation and the report use. Answers are
remembered for the whole run, and every value is written to
generated/parameters.json so a result can be traced back to its settings.
--no-ask skips the questions (a pipe or a cron job does the same
automatically).

The last data step records a START/GOAL mission for every .off in
data/processed/meshes. --no-all-meshes limits it to the navigation surface,
and --force-missions replaces missions that already exist. The step is
interactive: run it in a terminal, or commit the mission files for a
non-interactive run. When a surface is rebuilt with other geometry settings,
--refresh-changed keeps each mission's START/GOAL and snaps them onto the new
surface.

The data stage needs NumPy, Matplotlib (previews) and Shapely (triangulation).
It rewrites data/processed/ and generated/data_viz/, and writes the missions to
data/processed/missions/.
"""
import argparse
from dataclasses import dataclass
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv/bin/python'
PYTHON = str(VENV) if VENV.is_file() else sys.executable
DEFAULT_MISSION = 'city.standardized.triangulation'
DEFAULT_GOAL = 'g1'


@dataclass(frozen=True)
class Param:
    """One value the run asks for, and the flag it becomes."""

    key: str
    question: str
    default: object
    kind: str                 # 'float', 'int' or 'bool'
    flag: str = ''            # appended with the value (numbers and true bools)
    false_flag: str = ''      # appended when a bool is false
    minimum: float = None     # rejected below this
    maximum: float = None     # rejected above this
    note: str = ''            # what it does, and the range worth using
    advice: tuple = None      # (low, high) that is warned about, not rejected


PARAM_GROUPS = {
    'triangulation': [
        Param('cell', 'cell (m)', 5., 'float', '--cell', minimum=.05,
              note='cạnh ô lưới, nên 3–10; dưới 5 thì plan rất chậm',
              advice=(3., 10.)),
        Param('clearance', 'clearance (m)', 1.5, 'float', '--clearance',
              minimum=0.,
              note='khe hở dọc trên nóc công trình, nên 0,5–3',
              advice=(.5, 3.)),
        Param('half_width', 'half-width (m)', 1.6, 'float', '--half-width',
              minimum=0.,
              note='nới ngang khi truy vấn, nên 0,2–1,6; nhỏ = bám footprint',
              advice=(.2, 1.6)),
        Param('max_slope', 'max-slope (m/m)', .5, 'float', '--max-slope',
              minimum=.001,
              note='độ dốc ramp, nên 0,5–2; lớn thì lên/xuống dốc hơn',
              advice=(.5, 2.)),
    ],
    'solver': [
        Param('seconds', 'thời gian tối đa mỗi goal (s)', 300., 'float',
              '--seconds', minimum=1.,
              note='chặn tìm kiếm, nên 60–900; city g2 cần khoảng 190',
              advice=(60., 900.)),
        Param('max_nodes', 'số node tối đa', 200000, 'int', '--max-nodes',
              minimum=1,
              note='giới hạn bộ nhớ, nên 50 000–1 000 000',
              advice=(50000, 1000000)),
        Param('clipping', 'clipping (Y/n)', True, 'bool',
              false_flag='--no-clipping',
              note='Procedure 2; Y cho route ngắn hơn, N để so sánh'),
    ],
    'world': [
        Param('simplify', 'simplify (m)', .1, 'float', '--simplify',
              minimum=0.,
              note='dung sai rút gọn waypoint, nên 0–1; 0 giữ mọi điểm',
              advice=(0., 1.)),
        Param('collision_grid', 'collision grid (m)', 1., 'float',
              '--collision-grid', minimum=.001,
              note='ô gom đỉnh cho collision, nên 0,5–2; lớn = nhẹ hơn',
              advice=(.5, 2.)),
    ],
    'flight': [
        Param('speed', 'tốc độ (m/s)', 5., 'float', '--speed', minimum=.001,
              note='cruise speed; nên 2–8, cao quá dễ vượt sai số cho phép',
              advice=(2., 8.)),
        Param('max_accel', 'gia tốc tối đa (m/s²)', 3., 'float',
              '--max-accel', minimum=.001,
              note='giới hạn của profile, nên 1–6',
              advice=(1., 6.)),
        Param('dwell', 'dừng tại waypoint (s)', 0., 'float', '--dwell',
              minimum=0.,
              note='dừng ở mỗi waypoint, nên 0–2; 0 là bay xuyên qua',
              advice=(0., 2.)),
        Param('start_delay', 'trễ khởi động (s)', 2., 'float',
              '--start-delay', minimum=0.,
              note='chờ trước khi bay, nên 0–5',
              advice=(0., 5.)),
    ],
    'gazebo': [
        Param('timeout', 'timeout (s)', 900., 'float', '--timeout',
              minimum=1.,
              note='chặn Gazebo treo, nên 300–1800; route city bay 40–70 s',
              advice=(300., 1800.)),
    ],
    'validate': [
        Param('max_error', 'sai số cho phép (m)', 1., 'float', '--max-error',
              minimum=.000001,
              note='ngưỡng bám quỹ đạo, nên 0,2–2; 1 m là ngưỡng đã dùng',
              advice=(.2, 2.)),
    ],
}

GROUP_TITLES = {
    'triangulation': 'Tham số triangulation',
    'solver': 'Tham số solver',
    'world': 'Tham số dựng world',
    'flight': 'Tham số bay',
    'gazebo': 'Tham số Gazebo',
    'validate': 'Tham số chấm điểm',
}

STAGES = {
    'data': [
        {'run': [PYTHON, 'tools/data/copy_meshes.py', '--write']},
        {'run': [PYTHON, 'tools/data/standardize.py']},
        {'run': [PYTHON, 'tools/data/off2glb.py']},
        {'run': [PYTHON, 'tools/data/triangulation.py', '--force'],
         'params': ['triangulation']},
        {'run': [PYTHON, 'tools/data/data_viz.py', '--all']},
        {'run': [PYTHON, 'tools/data/set_start_goal.py']},
    ],
    'plan': [
        {'run': [PYTHON, 'tools/plan/run_funnel.py'], 'params': ['solver']},
        {'run': [PYTHON, 'tools/plan/route_viz.py']},
        {'run': [PYTHON, 'tools/plan/compare.py']},
    ],
    'simulate': [
        {'run': [PYTHON, 'tools/simulate/build_world.py',
                 '--mission', DEFAULT_MISSION, '--goal', DEFAULT_GOAL],
         'params': ['world', 'flight']},
        {'run': ['bash', 'tools/simulate/run_simulate.sh',
                 '--mission', DEFAULT_MISSION, '--goal', DEFAULT_GOAL,
                 '--no-build'],
         'params': ['gazebo']},
        {'run': [PYTHON, 'tools/simulate/validate.py',
                 '--mission', DEFAULT_MISSION, '--goal', DEFAULT_GOAL],
         'params': ['validate']},
    ],
}

DEFAULT_STAGES = ['data', 'plan', 'simulate']

DESCRIPTIONS = {
    'data': 'raw -> processed (fixtures, scene, GLB, surface, previews, mission)',
    'plan': 'funnel routes, route images and the reference comparison',
    'simulate': 'one Gazebo world, the flight and its validation',
}

# Results rebuilt by the pipeline. data/processed/missions/ is not here: a
# mission records the START/GOAL somebody chose, and it is not reproducible.
CLEARED = [
    ROOT / 'generated',
    ROOT / 'data/processed/meshes',
    ROOT / 'data/processed/scenes',
]


def display(command):
    shown = list(command)
    if shown and shown[0] == PYTHON:
        shown[0] = '.venv/bin/python' if VENV.is_file() else 'python3'
    return ' '.join(shown)


def short(path):
    """Repo-relative path for printing."""
    path = Path(path)
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


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


def copy_step(step):
    return {'run': list(step['run']), 'params': list(step.get('params') or [])}


def stage_commands(name, args):
    """Steps of a stage, with the simulate mission, goal(s) and flags applied."""
    steps = [copy_step(step) for step in STAGES[name]]
    if name == 'simulate':
        mission = args.mission or DEFAULT_MISSION
        goals = [args.goal] if args.goal else mission_goals(mission)
        expanded = []
        for goal in goals:
            pair = [copy_step(step) for step in steps]
            for step in pair:
                command = step['run']
                command[command.index('--mission') + 1] = mission
                command[command.index('--goal') + 1] = goal
            if args.show_surface:
                pair[0]['run'].append('--surface')
            if args.headless:
                pair[1]['run'].append('--headless')
            if args.software:
                pair[1]['run'].append('--software')
            if args.container is True:
                pair[1]['run'].append('--container')
            elif args.container is False:
                pair[1]['run'].append('--native')
            if args.image:
                pair[1]['run'] += ['--image', args.image]
            if args.gpu:
                pair[1]['run'] += ['--gpu', args.gpu]
            if args.keep_open:
                pair[1]['run'].append('--keep-open')
            if args.pull:
                pair[1]['run'].append('--pull')
            if args.no_png:
                pair[2]['run'].append('--no-png')
            expanded.extend(pair)
        return expanded
    if name == 'data':
        if args.all_meshes:
            steps[-1]['run'].append('--all-meshes')
            if not args.force_missions:
                steps[-1]['run'].append('--refresh-changed')
        if args.force_missions:
            steps[-1]['run'].append('--force')
    return steps


def show_flow(args):
    print('Stages:')
    for name, description in DESCRIPTIONS.items():
        print(f'  {name:9s} {description}')
        for step in stage_commands(name, args):
            print('            ' + display(step['run']))
            if step['params']:
                asked = ', '.join(item.key for group in step['params']
                                  for item in PARAM_GROUPS[group])
                print(f'            (hỏi khi chạy: {asked})')
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


# --------------------------------------------------------------------------
# Parameters


def default_value(item, group, args):
    """Default of a parameter, honouring the one flag that sets one."""
    if group == 'validate' and item.key == 'max_error' and args.max_error is not None:
        return args.max_error
    return item.default


def format_default(item, value):
    if item.kind == 'bool':
        return 'Y' if value else 'N'
    return f'{value:g}' if item.kind == 'float' else str(value)


def format_group(group, values):
    return ' '.join(f'{item.key}={format_default(item, values[item.key])}'
                    for item in PARAM_GROUPS[group])


def prompt_text(item, default):
    """Question line: what the value does, then the default."""
    note = f' — {item.note}' if item.note else ''
    return f'      {item.question}{note} [{format_default(item, default)}]: '


def warn_outside(item, value):
    """Say when a value is outside the range worth using, but keep it."""
    if not item.advice or item.kind == 'bool':
        return
    low, high = item.advice
    if low <= value <= high:
        return
    print(f'      (!) {item.key}={format_default(item, value)} ngoài khoảng nên '
          f'dùng {low:g}–{high:g}; vẫn dùng giá trị này.')


def ask_value(item, default):
    """Ask for one value; Enter keeps the default, bad input is asked again."""
    while True:
        try:
            text = input(prompt_text(item, default))
        except EOFError:
            print()
            return default
        text = text.strip()
        if not text:
            return default
        if item.kind == 'bool':
            lowered = text.lower()
            if lowered in ('y', 'yes', 'c', 'có', 'co'):
                return True
            if lowered in ('n', 'no', 'k', 'không', 'khong'):
                return False
            print('      (y hoặc n)')
            continue
        try:
            value = int(text) if item.kind == 'int' else float(text)
        except ValueError:
            print('      (cần một số)')
            continue
        if item.kind == 'float' and not math.isfinite(value):
            print('      (cần một số hữu hạn)')
            continue
        if item.minimum is not None and value < item.minimum:
            print(f'      (phải ≥ {item.minimum:g})')
            continue
        if item.maximum is not None and value > item.maximum:
            print(f'      (phải ≤ {item.maximum:g})')
            continue
        warn_outside(item, value)
        return value


def choose_group(group, args, state):
    """Ask for a group once, then reuse the answers for the rest of the run."""
    if group in state['values']:
        return state['values'][group]
    items = PARAM_GROUPS[group]
    defaults = {item.key: default_value(item, group, args) for item in items}
    chosen, origins = {}, {}
    if state['mode'] == 'ask':
        print(f'    {GROUP_TITLES[group]} — Enter để giữ mặc định:', flush=True)
        for item in items:
            value = ask_value(item, defaults[item.key])
            chosen[item.key] = value
            origins[item.key] = ('default' if value == defaults[item.key]
                                 else 'answer')
        suffix = '' if all(origin == 'default' for origin in origins.values()) \
            else '  (đã đổi)'
        print(f'      → {format_group(group, chosen)}{suffix}', flush=True)
    else:
        for item in items:
            chosen[item.key] = defaults[item.key]
            origins[item.key] = ('flag' if (group == 'validate'
                                            and item.key == 'max_error'
                                            and args.max_error is not None)
                                 else 'default')
            if state['mode'] == 'dry':
                print(prompt_text(item, defaults[item.key]).rstrip())
    state['values'][group] = chosen
    state['sources'][group] = origins
    return chosen


def group_flags(group, values):
    """Flags for the answers of one group."""
    flags = []
    for item in PARAM_GROUPS[group]:
        value = values[item.key]
        if item.kind == 'bool':
            if value and item.flag:
                flags.append(item.flag)
            elif not value and item.false_flag:
                flags.append(item.false_flag)
            continue
        if not item.flag:
            continue
        flags += [item.flag,
                  f'{value:g}' if item.kind == 'float' else str(value)]
    return flags


# --------------------------------------------------------------------------
# Clearing old results


def folder_stats(folder):
    if not folder.is_dir():
        return 0, 0
    files = [path for path in folder.rglob('*') if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def stale_containers():
    """Gazebo containers left behind by an interrupted run."""
    try:
        shown = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}'],
                               capture_output=True, text=True).stdout.split()
    except (FileNotFoundError, OSError):
        return []
    return [name for name in shown if name.startswith('funnel-')]


def print_manifest():
    files = size = 0
    for folder in CLEARED:
        count, octets = folder_stats(folder)
        files += count
        size += octets
        print(f'    {short(folder)}/  {count} file · {octets / 1e6:.1f} MB')
    print('    Giữ lại: data/processed/missions/ (START/GOAL), data/raw/, '
          'data/expected/')
    containers = stale_containers()
    if containers:
        print('    Container Gazebo còn sót: ' + ', '.join(containers))
    return files, size, containers


def clear_artifacts(args):
    """Print what will go, then delete it unless this is a dry run."""
    print('\nTrả lời y sẽ xoá và sinh lại:', flush=True)
    files, size, containers = print_manifest()
    if args.dry_run:
        for folder in CLEARED:
            print(f'    $ rm -rf {short(folder)}')
        if containers:
            print('    $ docker rm -f ' + ' '.join(containers))
        return False
    for folder in CLEARED:
        shutil.rmtree(folder, ignore_errors=True)
    for name in containers:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    print(f'\nĐã xoá {files} file · {size / 1e6:.1f} MB', flush=True)
    print('Khôi phục từ Git nếu cần: git checkout -- generated data', flush=True)
    return True


def ask_fresh(args):
    """Return True when the old results were cleared."""
    if args.fresh:
        return clear_artifacts(args)
    if not sys.stdin.isatty() or args.no_ask:
        if not args.no_ask and not args.dry_run:
            print('Không có terminal để hỏi; giữ kết quả cũ '
                  '(dùng --fresh để xoá).', flush=True)
        return False
    print('\nTrả lời y sẽ xoá và sinh lại:', flush=True)
    files, size, containers = print_manifest()
    try:
        answer = input('Chạy lại từ đầu? (y/N): ').strip().lower()
    except EOFError:
        print()
        answer = ''
    if answer not in ('y', 'yes', 'c', 'có', 'co'):
        print('Giữ kết quả cũ; chạy tiếp.', flush=True)
        return False
    for folder in CLEARED:
        shutil.rmtree(folder, ignore_errors=True)
    for name in containers:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    print(f'\nĐã xoá {files} file · {size / 1e6:.1f} MB', flush=True)
    print('Khôi phục từ Git nếu cần: git checkout -- generated data', flush=True)
    return True


# --------------------------------------------------------------------------
# Running


def run_stage(name, args, index, total, state):
    commands = stage_commands(name, args)
    line = '=' * 72
    print(f'\n{line}')
    print(f'Stage {index}/{total}: {name} — {DESCRIPTIONS[name]}')
    print(f'{len(commands)} step(s)' + (' — dry run' if args.dry_run else ''))
    print(line)
    started = time.monotonic()
    for step_number, entry in enumerate(commands, 1):
        command = list(entry['run'])
        print(f'\n[{name} {step_number}/{len(commands)}] '
              f'{step_label(command)}', flush=True)
        asked = False
        for group in entry['params']:
            choose_group(group, args, state)
            command += group_flags(group, state['values'][group])
            asked = True
        if asked:
            print('    $ ' + display(command), flush=True)
        if args.dry_run:
            if not asked:
                print('    $ ' + display(command), flush=True)
            continue
        step_started = time.monotonic()
        code = capture(command) if args.quiet else stream(command)
        if code:
            raise SystemExit(f'Stage {name} failed at step {step_number}: '
                             f'{step_label(command)}')
        print(f'    done in {time.monotonic() - step_started:.1f} s', flush=True)
    print(f'\n{name}: ok in {time.monotonic() - started:.1f} s', flush=True)


def write_parameters(args, stages, state, cleared, started):
    """Record every value the run used, next to the results it produced."""
    path = ROOT / 'generated/parameters.json'
    try:
        commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                cwd=ROOT, capture_output=True, text=True,
                                timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        commit = None
    record = {
        'command': ' '.join([short(Path(sys.argv[0]))] + sys.argv[1:]),
        'stages': stages,
        'cleared': cleared,
        'interactive': state['mode'] == 'ask',
        'parameters': state['values'],
        'sources': state['sources'],
        'commit': commit,
        'seconds': round(time.monotonic() - started, 3),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f'Save at: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stages', nargs='*', metavar='stage',
                        help='data, plan, simulate or flow')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the commands and the questions without '
                             'running or asking anything')
    parser.add_argument('--quiet', action='store_true',
                        help='Hide tool output unless a step fails')
    parser.add_argument('--fresh', action='store_true',
                        help='Clear the old results without asking, then run '
                             'data, plan and simulate')
    parser.add_argument('--no-ask', action='store_true',
                        help='Ask nothing: keep every parameter default')
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
                        help='simulate: largest allowed tracking error; becomes '
                             'the default of the validation question')
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
    if args.fresh and args.stages:
        parser.error('--fresh chỉ dùng khi chạy cả data, plan và simulate; '
                     'chạy một stage thì không xoá gì')
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

    state = {'values': {}, 'sources': {},
             'mode': ('dry' if args.dry_run else
                      'ask' if (sys.stdin.isatty() and not args.no_ask)
                      else 'default')}
    full_run = stages == DEFAULT_STAGES
    cleared = False
    if full_run and not args.dry_run:
        cleared = ask_fresh(args)
    elif full_run:
        print('\nChạy lại từ đầu? (y/N): N — dry run, không xoá', flush=True)
        print_manifest()

    started = time.monotonic()
    try:
        for index, stage in enumerate(stages, 1):
            run_stage(stage, args, index, len(stages), state)
    finally:
        if not args.dry_run and state['values']:
            write_parameters(args, stages, state, cleared, started)
    if len(stages) > 1 and not args.dry_run:
        print(f'\nAll {len(stages)} stages finished in '
              f'{time.monotonic() - started:.1f} s')


if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:  # e.g. piping into head or less
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
