# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, hashlib, json, subprocess); host
# tools grim + hyprctl (Wayland/Hyprland) or ImageMagick import (X11).
"""Capture the Gazebo window while a simulated route is flying.

`run_simulate.sh` calls this at fixed simulation times, so the pictures in the
report come from a known run. The window is found through Hyprland's client
list and cropped with grim; on X11 the whole screen is captured with
ImageMagick import instead. A JSON file next to the PNG records the run id, the
simulation time, the window geometry and the command that produced the image.

This is a screenshot of the GUI, not a rendering produced by the simulation
itself; the telemetry and validation.json remain the measured results.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def gazebo_windows():
    """Return every Gazebo GUI window as (address, client, geometry) tuples."""
    if not shutil.which('hyprctl'):
        return []
    result = subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True,
                            text=True, check=False)
    if result.returncode != 0:
        return []
    windows = []
    for client in json.loads(result.stdout or '[]'):
        if client.get('class') == 'Gazebo GUI' or client.get('title') == 'Gazebo Sim':
            x, y = client['at']
            width, height = client['size']
            windows.append((client.get('address', ''), client,
                            int(x), int(y), int(width), int(height)))
    return windows


def hyprland_window():
    """Return the Gazebo GUI window: class first, title as a fallback.

    Matching the word "gazebo" in any title would pick the code editor, whose
    window title contains the repository name. When several Gazebo windows are
    open the largest one is used, so a leftover window cannot win.
    """
    if not shutil.which('hyprctl'):
        return None
    result = subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True,
                            text=True, check=False)
    if result.returncode != 0:
        return None
    ignored = {item for item in os.environ.get('FUNNEL_IGNORE_WINDOWS', '').split(',') if item}
    matches = []
    for address, client, x, y, width, height in gazebo_windows():
        if address in ignored:
            continue
        matches.append((int(width) * int(height), client, x, y, width, height))
    if not matches:
        return None
    _, client, x, y, width, height = max(matches, key=lambda item: item[0])
    return (client.get('class', ''), client.get('title', ''),
            x, y, width, height)


def capture_with_hyprland(output):
    window = hyprland_window()
    if window is None:
        return None
    if not shutil.which('grim'):
        return None
    _, _, x, y, width, height = window
    command = ['grim', '-g', f'{x},{y} {width}x{height}', str(output)]
    subprocess.run(command, check=True)
    return {'tool': 'grim', 'command': command[:-1] + ['<output>'],
            'window': {'class': window[0], 'title': window[1],
                       'at': [x, y], 'size': [width, height]}}


def capture_with_import(output):
    if not shutil.which('import'):
        return None
    command = ['import', '-window', 'root', str(output)]
    subprocess.run(command, check=True)
    return {'tool': 'import', 'command': command[:-1] + ['<output>'],
            'window': {'class': 'root', 'title': 'whole screen'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--sim-time', type=float, default=None)
    parser.add_argument('--phase', default=None)
    parser.add_argument('--log', type=Path, default=None,
                        help='gazebo.log of the run, recorded in the metadata')
    parser.add_argument('--list-gazebo', action='store_true',
                        help='Print the addresses of open Gazebo windows and exit')
    args = parser.parse_args()
    if args.list_gazebo:
        for address, client, x, y, width, height in gazebo_windows():
            print(address)
        return 0
    if args.output is None:
        parser.error('--output is required unless --list-gazebo is used')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    details = capture_with_hyprland(args.output) or capture_with_import(args.output)
    if details is None or not args.output.is_file():
        print('screenshot: no Gazebo window and no capture tool', file=sys.stderr)
        return 1

    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    metadata = {
        'image': args.output.name,
        'sha256': digest,
        'bytes': args.output.stat().st_size,
        'captured_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'run_id': args.run_id,
        'sim_time': args.sim_time,
        'phase': args.phase,
        'display': {'DISPLAY': None, 'WAYLAND_DISPLAY': None},
        'capture': details,
        'ignored_windows': [item for item in
                            os.environ.get('FUNNEL_IGNORE_WINDOWS', '').split(',') if item],
        'gazebo_log': str(args.log) if args.log else None,
        'note': 'Screenshot of the Gazebo window; measured results are in '
                'physics_telemetry.csv and validation.json.',
    }
    for key in ('DISPLAY', 'WAYLAND_DISPLAY'):
        metadata['display'][key] = os.environ.get(key)
    metadata_path = args.output.with_suffix('.json')
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'Save at: {args.output}')
    print(f'Save at: {metadata_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
