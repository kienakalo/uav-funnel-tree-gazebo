#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Matplotlib (chỉ khi dùng --pick); Python stdlib
# (argparse, hashlib, json, math, pathlib, sys); local modules (mesh_off,
# plotting).
"""Choose START and GOAL vertices on an OFF mesh and save them as JSON.

Input:  data/processed/meshes/city.standardized.triangulation.off (or --mesh)
Output: data/processed/missions/<mesh-stem>.json

The tool reads the mesh first and prints its size, bounds and grid spacing.
Then it takes the choice from the saved JSON, from the command line, or from an
interactive prompt (-pick for a 3D point-and-click window). The choice is saved
once; later runs reuse it and never ask again. `--force` replaces the saved
choice.

Examples:
  # lần đầu: chọn tay trên bề mặt thành phố
  .venv/bin/python tools/data/set_start_goal.py

  # chọn bằng chuột
  .venv/bin/python tools/data/set_start_goal.py --pick

  # một mesh khác
  .venv/bin/python tools/data/set_start_goal.py --mesh data/processed/meshes/cliff.off

  # xem mesh nào đã có lựa chọn
  .venv/bin/python tools/data/set_start_goal.py --list-meshes

  # chọn cho mọi mesh còn thiếu (bỏ qua mesh đã có mission)
  .venv/bin/python tools/data/set_start_goal.py --all-meshes

  # mesh nhỏ: mọi đỉnh còn lại là goal
  .venv/bin/python tools/data/set_start_goal.py \\
      --mesh data/processed/meshes/cliff.off --start-vertex 1 --all-goals

  # lần sau: chỉ cần đọc lại lựa chọn đã lưu
  .venv/bin/python tools/data/set_start_goal.py
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
from mesh_off import inspect_mesh, read_off
from plotting import unavailable_message, use_interactive

DEFAULT_MESH = ROOT / 'data/processed/meshes/city.standardized.triangulation.off'
DEFAULT_OUTPUT = ROOT / 'data/processed/missions'
MAX_ALL_GOALS = 300
TABLE_LIMIT = 200


def fail(message):
    raise SystemExit(f'set_start_goal: {message}')


def relative(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


# --------------------------------------------------------------------------
# Mesh


def read_mesh(path):
    """Read an OFF mesh and check the topology a mission needs."""
    points, faces = read_off(path)
    if len(np.unique(points, axis=0)) != len(points):
        fail(f'{path}: two vertices share coordinates')
    stats = inspect_mesh(points, faces)
    if stats['degenerate_triangles']:
        fail(f'{path}: {stats["degenerate_triangles"]} degenerate triangles')
    if stats['nonmanifold_edges']:
        fail(f'{path}: an edge borders more than two faces')
    return points, faces, stats['boundary_edges']


def vertex_spacing(points):
    """Median distance between neighbouring grid columns, in metres."""
    xs = np.unique(np.round(points[:, 0], 6))
    spacing = np.diff(xs)
    spacing = spacing[spacing > 1e-6]
    return float(np.median(spacing)) if len(spacing) else 5.


def snap(points, target, mode, max_snap, label):
    delta = points - np.array(target, dtype=float)
    planar = np.linalg.norm(delta[:, :2], axis=1)
    total = np.linalg.norm(delta, axis=1)
    metric = planar if mode == 'xy' else total
    index = int(metric.argmin())
    if metric[index] > max_snap + 1e-9:
        fail(f'{label} is {metric[index]:.3f} from the nearest vertex, more than '
             f'--max-snap {max_snap:.3f}; pass a larger value if intended')
    return index, float(metric[index])


def describe(points, vertex, target=None, distance=0.):
    record = {'vertex': int(vertex),
              'xyz': [round(float(value), 6) for value in points[vertex]]}
    if target is not None:
        record['input'] = [round(float(value), 6) for value in target]
        record['snap'] = round(float(distance), 6)
    return record


# --------------------------------------------------------------------------
# Selection


def parse_index(text, count, label):
    try:
        index = int(text)
    except ValueError:
        fail(f'{label}: "{text}" is not a vertex index')
    if not 0 <= index < count:
        fail(f'{label}: {index} is outside 0..{count - 1}')
    return index


def parse_point(text, label):
    try:
        values = [float(value) for value in text.replace(',', ' ').split()]
    except ValueError:
        fail(f'{label}: "{text}" is neither a vertex index nor "x y z"')
    if len(values) != 3:
        fail(f'{label}: need three coordinates')
    if not all(math.isfinite(value) for value in values):
        fail(f'{label}: non-finite coordinate')
    return values


def resolve(text, points, mode, max_snap, label):
    """Turn 'N' or 'x y z' into a vertex index and a snap record."""
    text = text.strip()
    if not text:
        fail(f'{label}: empty choice')
    tokens = text.replace(',', ' ').split()
    if len(tokens) == 1:
        index = parse_index(tokens[0], len(points), label)
        return index, describe(points, index)
    if len(tokens) != 3:
        fail(f'{label}: enter one vertex index, or three coordinates "x y z"')
    target = parse_point(text, label)
    index, distance = snap(points, target, mode, max_snap, label)
    return index, describe(points, index, target, distance)


def terminal_streams():
    """Return (read_line, write) for the terminal, even when stdin is piped."""
    if sys.stdin.isatty():
        def read_line(prompt=''):
            return input(prompt)
        return read_line, print
    try:
        reader = open('/dev/tty', 'r', encoding='utf-8')
        writer = open('/dev/tty', 'w', encoding='utf-8')
    except OSError:
        return None

    def read_line(prompt=''):
        writer.write(prompt)
        writer.flush()
        line = reader.readline()
        if not line:
            raise EOFError
        return line.rstrip('\n')

    def write(*args, **kwargs):
        kwargs.pop('flush', None)
        print(*args, file=writer, **kwargs)
        writer.flush()
    return read_line, write


def print_vertices(points, faces, limit=TABLE_LIMIT, write=print):
    degree = np.zeros(len(points), dtype=int)
    np.add.at(degree, faces.ravel(), 1)
    if len(points) > limit:
        write(f'  {len(points)} đỉnh — bảng chỉ in {limit} đỉnh đầu. Dùng --pick, '
              'hoặc xem tools/data/data_viz.py rồi nhập chỉ số/toạ độ.')
        count = limit
    else:
        count = len(points)
    write(f'  {"#":>5}  {"x":>10} {"y":>10} {"z":>10}  {"faces":>5}')
    for index in range(count):
        x, y, z = points[index]
        write(f'  {index:5d}  {x:10.3f} {y:10.3f} {z:10.3f}  {degree[index]:5d}')


def ask_console(read_line, write, points, faces, mode, max_snap):
    """Prompt for one START and n GOALs; 'all' takes every other vertex."""
    start = None
    while start is None:
        answer = read_line('START — chỉ số đỉnh hoặc "x y z": ').strip()
        if not answer:
            continue
        index, record = resolve(answer, points, mode, max_snap, 'START')
        start = record
    goals = []
    while True:
        answer = read_line('GOAL — chỉ số/«x y z», "all" cho mọi đỉnh còn lại, '
                           'dòng trống để xong: ').strip()
        if not answer:
            break
        if answer.lower() == 'all':
            if len(points) > MAX_ALL_GOALS:
                write(f'  "all" chỉ dùng cho mesh tối đa {MAX_ALL_GOALS} đỉnh.')
                continue
            goals = [describe(points, index) for index in range(len(points))
                     if index != start['vertex']]
            break
        index, record = resolve(answer, points, mode, max_snap, 'GOAL')
        if index == start['vertex']:
            write('  GOAL trùng START, bỏ qua.')
            continue
        if any(goal['vertex'] == index for goal in goals):
            write('  GOAL đã chọn, bỏ qua.')
            continue
        goals.append(record)
    if not goals:
        fail('need at least one GOAL')
    return start, goals, len(goals) == len(points) - 1


def gui_backend():
    """Name of an interactive matplotlib backend, or None without one."""
    return use_interactive()


def ask_pick(points, faces):
    """Pick START/GOAL by clicking; None when the window cannot be used."""
    try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers projection)
    except Exception as error:  # pragma: no cover - depends on the display
        print(f'  không nạp được Matplotlib: {error}', flush=True)
        return None

    figure = plt.figure(figsize=(11, 9))
    axes = figure.add_subplot(111, projection='3d')
    axes.plot_trisurf(points[:, 0], points[:, 1], points[:, 2], triangles=faces,
                      cmap='viridis', linewidth=0., alpha=0.45)
    scatter = axes.scatter(points[:, 0], points[:, 1], points[:, 2], s=14,
                           c='#2c3e50', depthshade=False, picker=5)
    state = {'start': None, 'goals': [], 'picked': None}
    marks = []

    def redraw():
        for mark in marks:
            mark.remove()
        marks.clear()
        if state['start'] is not None:
            mark, = axes.plot(*points[state['start']][None].T, 'o', color='#167a40',
                              markersize=10, label='START')
            marks.append(mark)
        for number, goal in enumerate(state['goals'], 1):
            mark, = axes.plot(*points[goal][None].T, '*', color='#b51f41',
                              markersize=13)
            marks.append(mark)
            text = axes.text(*points[goal], f' {number}', color='#b51f41')
            marks.append(text)
        axes.set_title('s: START   g: GOAL   u: bỏ GOAL cuối   Enter: lưu   '
                       f'| {len(state["goals"])} goal')
        figure.canvas.draw_idle()

    def on_pick(event):
        if event.artist is scatter and len(event.ind):
            state['picked'] = int(event.ind[0])
            axes.set_title(f'đang chọn đỉnh {state["picked"]} — s/g để gán, '
                           f'{len(state["goals"])} goal')
            figure.canvas.draw_idle()

    def on_key(event):
        if event.key in ('s', 'g') and state['picked'] is not None:
            if event.key == 's':
                state['start'] = state['picked']
            elif state['picked'] != state['start'] and state['picked'] not in state['goals']:
                state['goals'].append(state['picked'])
            redraw()
        elif event.key == 'u' and state['goals']:
            state['goals'].pop()
            redraw()
        elif event.key in ('enter', 'escape'):
            plt.close(figure)

    figure.canvas.mpl_connect('pick_event', on_pick)
    figure.canvas.mpl_connect('key_press_event', on_key)
    try:
        redraw()
        plt.show()
    except Exception as error:  # pragma: no cover - depends on the display
        print(f'  không mở được cửa sổ 3D: {error}', flush=True)
        return None
    if state['start'] is None or not state['goals']:
        print('  cửa sổ đã đóng mà chưa chọn đủ START và GOAL', flush=True)
        return None
    start = describe(points, state['start'])
    goals = [describe(points, index) for index in state['goals']]
    return start, goals, len(goals) == len(points) - 1


# --------------------------------------------------------------------------
# Mission file


def mission_path(mesh, output, explicit):
    return (explicit or (output / f'{mesh.stem}.json')).resolve()


def mission_record(mesh_path, points, faces, boundary, spacing, start, goals,
                   all_goals, mode, max_snap, selected_by):
    return {
        'mesh': str(relative(mesh_path)),
        'mesh_sha256': hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        'mesh_vertices': int(len(points)),
        'mesh_faces': int(len(faces)),
        'boundary_edges': int(boundary),
        'vertex_spacing': round(spacing, 6),
        'snap_mode': mode,
        'max_snap': round(max_snap, 6),
        'mode': 'all-goals' if all_goals else 'explicit',
        'selected_by': selected_by,
        'start': start,
        'goals': goals,
    }


def check_saved(record, mesh_path, points, faces):
    if record.get('mesh_sha256') != hashlib.sha256(mesh_path.read_bytes()).hexdigest():
        fail(f'{mesh_path} changed since the mission was saved; run with --force')
    if (record.get('mesh_vertices') != len(points) or
            record.get('mesh_faces') != len(faces)):
        fail('the saved mission does not match this mesh; run with --force')
    start = record.get('start') or {}
    if not isinstance(start.get('vertex'), int) or not 0 <= start['vertex'] < len(points):
        fail('the saved START vertex is invalid; run with --force')
    for goal in record.get('goals') or []:
        if not isinstance(goal.get('vertex'), int) or not 0 <= goal['vertex'] < len(points):
            fail('a saved GOAL vertex is invalid; run with --force')
    if record.get('mode') not in ('explicit', 'all-goals'):
        fail('the saved mission mode is invalid; run with --force')
    if record['mode'] == 'explicit' and not record.get('goals'):
        fail('the saved mission has no GOAL; run with --force')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n',
                         encoding='utf-8')
    temporary.replace(path)


def summary(record, path):
    goals = record['goals']
    print(f'Mission: {relative(path)}')
    print(f'Mesh:    {record["mesh"]} — {record["mesh_vertices"]} đỉnh, '
          f'{record["mesh_faces"]} mặt, lưới {record["vertex_spacing"]:g}')
    start = record['start']
    print(f'START:   đỉnh {start["vertex"]} {start["xyz"]}'
          + (f' (snap {start["snap"]:.3f})' if start.get('snap') else ''))
    if record['mode'] == 'all-goals':
        print(f'GOAL:    mọi đỉnh còn lại ({record["mesh_vertices"] - 1} goal)')
    else:
        for goal in goals:
            print(f'GOAL {goal.get("id", "")}: đỉnh {goal["vertex"]} {goal["xyz"]}'
                  + (f' (snap {goal["snap"]:.3f})' if goal.get('snap') else ''))


def choose_console(path, points, faces, mode, max_snap):
    """Ask on the terminal, using /dev/tty when stdin is piped."""
    streams = terminal_streams()
    if streams is None:
        fail('no saved mission and no terminal to ask on: pass --start X Y Z / '
             '--goal X Y Z, --start-vertex/--goal-vertex or --all-goals')
    read_line, write = streams
    write(f'Chưa có {relative(path)} — chọn START/GOAL:')
    print_vertices(points, faces, write=write)
    try:
        return ask_console(read_line, write, points, faces, mode, max_snap)
    except EOFError:
        fail('input ended before START and GOAL were chosen')


# --------------------------------------------------------------------------


def mesh_list(folder):
    """Navigation meshes in name order; skip the viewer export.

    `*.glb2off.off` is the whole scene as one file: its shells repeat vertex
    coordinates, so it is not a surface a mission can be chosen on.
    """
    return sorted(path for path in Path(folder).glob('*.off')
                  if not path.name.endswith('.glb2off.off'))


def show_meshes(args):
    """Print the available meshes and whether they already have a mission."""
    folder = DEFAULT_MESH.parent
    meshes = mesh_list(folder)
    if not meshes:
        fail(f'no .off mesh in {folder}; run "python3 main.py data" first')
    print(f'{len(meshes)} mesh trong {relative(folder)}:')
    for mesh in meshes:
        header = mesh.read_text(encoding='utf-8').splitlines()[1].split()
        path = mission_path(mesh, args.output, None)
        state = 'đã có mission' if path.is_file() else 'chưa có mission'
        print(f'  {mesh.stem:38s} {header[0]:>6} đỉnh {header[1]:>6} mặt  {state}')


def process_mesh(mesh_path, args):
    """Read one mesh, take the choice from JSON/CLI/terminal, save the mission."""
    if not mesh_path.is_file():
        fail(f'missing mesh {mesh_path}; run "python3 main.py data" first')
    points, faces, boundary = read_mesh(mesh_path)
    spacing = vertex_spacing(points)
    max_snap = args.max_snap if args.max_snap is not None else spacing * math.sqrt(2.) / 2.
    if not (max_snap > 0 and math.isfinite(max_snap)):
        fail('--max-snap must be positive and finite')

    path = mission_path(mesh_path, args.output, args.mission)
    low, high = points.min(axis=0), points.max(axis=0)
    print(f'Mesh: {relative(mesh_path)} — {len(points)} đỉnh, {len(faces)} mặt, '
          f'{boundary} cạnh biên, lưới {spacing:g}', flush=True)
    print(f'Bounds: x [{low[0]:.2f}, {high[0]:.2f}] y [{low[1]:.2f}, {high[1]:.2f}] '
          f'z [{low[2]:.2f}, {high[2]:.2f}]', flush=True)

    if path.is_file() and not args.force:
        record = json.loads(path.read_text(encoding='utf-8'))
        check_saved(record, mesh_path, points, faces)
        if args.start is not None or args.start_vertex is not None or args.goal \
                or args.goal_vertex or args.all_goals or args.pick:
            print('Đã có lựa chọn đã lưu; dùng --force nếu muốn chọn lại.', flush=True)
        summary(record, path)
        print(f'Read at: {path}')
        return

    chosen = args.start is not None or args.start_vertex is not None or args.goal \
        or args.goal_vertex or args.all_goals
    if chosen:
        selected_by = 'cli'
        if args.all_goals:
            if len(points) > MAX_ALL_GOALS:
                fail(f'--all-goals is meant for small meshes; {len(points)} vertices '
                     f'exceeds {MAX_ALL_GOALS}')
            if args.start_vertex is None:
                fail('--all-goals needs --start-vertex')
            start = describe(points, parse_index(str(args.start_vertex),
                                                 len(points), 'START'))
            goals, all_goals = [], True
        else:
            if args.start_vertex is not None:
                start = describe(points, parse_index(str(args.start_vertex),
                                                      len(points), 'START'))
            elif args.start is not None:
                index, distance = snap(points, args.start, args.snap, max_snap, 'START')
                start = describe(points, index, args.start, distance)
            else:
                fail('pass --start X Y Z or --start-vertex N')
            goals, all_goals = [], False
            for number, target in enumerate(args.goal or [], 1):
                index, distance = snap(points, target, args.snap, max_snap,
                                       f'GOAL {number}')
                goals.append(describe(points, index, target, distance))
            for index in args.goal_vertex or []:
                goals.append(describe(points, parse_index(str(index), len(points),
                                                          'GOAL')))
            if not goals:
                fail('pass --goal, --goal-vertex or --all-goals')
    elif args.pick:
        backend = gui_backend()
        if backend is None:
            print(f'  --pick: {unavailable_message()}', flush=True)
            print('  Chuyển sang chọn bằng bàn phím.', flush=True)
            start, goals, all_goals = choose_console(path, points, faces, args.snap,
                                                     max_snap)
            selected_by = 'console'
        else:
            print(f'  cửa sổ 3D (backend {backend}): click đỉnh, s=START, '
                  'g=GOAL, u=bỏ, Enter=lưu.', flush=True)
            picked = ask_pick(points, faces)
            if picked is not None:
                start, goals, all_goals = picked
                selected_by = 'pick'
            else:
                print('  chuyển sang chọn bằng bàn phím.', flush=True)
                start, goals, all_goals = choose_console(path, points, faces,
                                                         args.snap, max_snap)
                selected_by = 'console'
    else:
        start, goals, all_goals = choose_console(path, points, faces, args.snap,
                                                 max_snap)
        selected_by = 'console'

    if all_goals and len(points) > MAX_ALL_GOALS:
        fail(f'--all-goals is meant for small meshes; {len(points)} vertices '
             f'exceeds {MAX_ALL_GOALS}')
    if not all_goals:
        for number, goal in enumerate(goals, 1):
            if goal['vertex'] == start['vertex']:
                fail(f'GOAL g{number} is the START vertex')
            if any(goal['vertex'] == other['vertex'] for other in goals[:number - 1]):
                fail(f'GOAL g{number} repeats another goal vertex')
        goals = [{'id': f'g{number}', **goal} for number, goal in enumerate(goals, 1)]

    record = mission_record(mesh_path, points, faces, boundary, spacing, start, goals,
                            all_goals, args.snap, max_snap, selected_by)
    if path.exists() and not args.force:
        fail(f'{path} already exists; pass --force to replace it')
    write_json(path, record)
    summary(record, path)
    print(f'Save at: {path}')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mesh', type=Path,
                        help='Navigation surface (.off); default: '
                             f'{DEFAULT_MESH.relative_to(ROOT)}')
    parser.add_argument('--all-meshes', action='store_true',
                        help='Handle every .off in data/processed/meshes')
    parser.add_argument('--list-meshes', action='store_true',
                        help='List the meshes and their mission state, then exit')
    parser.add_argument('--mission', type=Path,
                        help='Mission file (default: data/processed/missions/<mesh>.json)')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                        help='Folder for the default mission file')
    parser.add_argument('--start', nargs=3, type=float, metavar=('X', 'Y', 'Z'),
                        help='START point; snapped to the nearest vertex')
    parser.add_argument('--start-vertex', type=int, metavar='N',
                        help='START vertex index')
    parser.add_argument('--goal', nargs=3, type=float, action='append',
                        metavar=('X', 'Y', 'Z'), help='GOAL point; repeat for several')
    parser.add_argument('--goal-vertex', type=int, action='append', metavar='N',
                        help='GOAL vertex index; repeat for several')
    parser.add_argument('--all-goals', action='store_true',
                        help=f'Every other vertex is a GOAL (max {MAX_ALL_GOALS} vertices)')
    parser.add_argument('--pick', action='store_true',
                        help='Choose by clicking vertices in a 3D window')
    parser.add_argument('--snap', choices=('xy', '3d'), default='xy',
                        help='Snap coordinates in the XY plane (default) or in 3D')
    parser.add_argument('--max-snap', type=float,
                        help='Reject points farther than this from a vertex '
                             '(default: half a grid diagonal)')
    parser.add_argument('--force', action='store_true',
                        help='Replace an existing mission file')
    args = parser.parse_args()

    if args.start is not None and args.start_vertex is not None:
        fail('use either --start or --start-vertex, not both')
    if args.all_goals and (args.goal or args.goal_vertex):
        fail('--all-goals cannot be combined with --goal or --goal-vertex')
    if args.all_meshes and (args.mesh or args.mission):
        fail('--all-meshes cannot be combined with --mesh or --mission')
    if args.all_meshes and (args.start is not None or args.start_vertex is not None
                            or args.goal or args.goal_vertex or args.all_goals):
        fail('--all-meshes chooses interactively; drop --start/--goal/--all-goals')

    if args.list_meshes:
        show_meshes(args)
        return

    if args.all_meshes:
        meshes = mesh_list(DEFAULT_MESH.parent)
        if not meshes:
            fail(f'no .off mesh in {DEFAULT_MESH.parent}; run "python3 main.py data" first')
        pending = [mesh for mesh in meshes
                   if args.force or not mission_path(mesh, args.output, None).is_file()]
        if not pending:
            print(f'All {len(meshes)} meshes already have missions; '
                  'use --force to choose again.', flush=True)
            return
        for index, mesh in enumerate(pending, 1):
            print(f'\n[{index}/{len(pending)}] {relative(mesh)}', flush=True)
            process_mesh(mesh, args)
        return

    process_mesh((args.mesh or DEFAULT_MESH).resolve(), args)


if __name__ == '__main__':
    main()
