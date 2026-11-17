#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib; Python stdlib (hashlib, json, sys, datetime,
# pathlib).
"""Write the settings that produced a figure into the figure itself.

A run leaves many PNG files behind: fixtures, the navigation surface, the
routes and one tracking plot per goal. The same file name is reused when the
grid, the envelope or the flight speed changes, so a picture alone cannot say
which configuration it belongs to. This module puts that answer in three
places, all written by one call:

1. a footer drawn into the image, readable when the picture is pasted into a
   report;
2. PNG text metadata, readable by a script without the sidecar;
3. a sidecar next to the file, ``<name>.png.json``, with the full values, the
   SHA256 of every input and of the image itself.

The footer can only show what the caller knows: a fixture has no grid or
clearance, and a route image has no flight speed until a world is built. Pass
what exists and leave the rest out; the stamp never states a default that was
not actually used.

Examples (inside a tool that already has a Matplotlib figure):
  from figstamp import save
  save(figure, output, parameters={'cell': 5.}, sources={'surface_sha256': digest},
       labels={'cell': ('cell', 'm')}, script=__file__)
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOFTWARE = 'uav-funnel-tree-gazebo'
FOOTER_SIZE = 7
FOOTER_COLOUR = '#4d4d4d'
WRAP = 112
SHORT = 8
SOURCES = ('scene_sha256', 'surface_sha256', 'mesh_sha256', 'mission_sha256',
           'routes_sha256', 'route_sha256', 'output_sha256', 'telemetry_sha256',
           'module_sha256')


def relative(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    """Local time with its offset, so two machines can be compared."""
    return datetime.now().astimezone().isoformat(timespec='seconds')


def short(value):
    return value[:SHORT] if isinstance(value, str) and len(value) > SHORT else value


def value_text(value):
    if isinstance(value, bool):
        return 'Y' if value else 'N'
    if isinstance(value, float):
        return f'{value:.6g}'
    return str(value)


def pairs(values, labels):
    """'key value unit' for each entry, using the display name in labels."""
    items = []
    for key, value in (values or {}).items():
        if value is None:
            continue
        name, unit = labels.get(key, (key, ''))
        items.append(f'{name} {value_text(value)}{unit}'.rstrip())
    return items


def wrapped(items, width=WRAP):
    """Join items with ' · ', starting a new line before the width is passed."""
    lines, current = [], ''
    for item in items:
        piece = item if not current else f' · {item}'
        if current and len(current) + len(piece) > width:
            lines.append(current)
            current = item
        else:
            current += piece
    if current:
        lines.append(current)
    return lines


def footer_lines(parameters, facts, sources, labels, generated):
    lines = wrapped(pairs(parameters, labels))
    lines += wrapped(pairs(facts, labels))
    marks = [f'{key[:-7] if key.endswith("_sha256") else key} {short(value)}'
             for key, value in (sources or {}).items() if value]
    lines += wrapped(marks)
    if lines:
        lines[-1] = f'{lines[-1]} · {generated[:16].replace("T", " ")}'
    else:
        lines = [generated[:16].replace('T', ' ')]
    return lines


def draw_footer(figure, lines):
    """Put the lines under the axes; bbox_inches='tight' keeps them."""
    figure.text(0.004, -0.008, '\n'.join(lines), ha='left', va='top',
                fontsize=FOOTER_SIZE, family='monospace', color=FOOTER_COLOUR,
                linespacing=1.4)


def command():
    script = Path(sys.argv[0])
    try:
        shown = [str(relative(script))]
    except (OSError, ValueError):
        shown = [str(script)]
    return ' '.join(shown + [str(argument) for argument in sys.argv[1:]])


def save(figure, output, parameters=None, facts=None, sources=None,
         labels=None, script=None, subject=None, dpi=150):
    """Write one PNG with its footer, its metadata and its sidecar.

    Returns (image, sidecar). The caller closes the figure.
    """
    output = Path(output)
    generated = now()
    parameters = parameters or {}
    facts = facts or {}
    sources = {key: value for key, value in (sources or {}).items() if value}
    labels = labels or {}
    script = Path(script or sys.argv[0]).resolve()
    lines = footer_lines(parameters, facts, sources, labels, generated)
    draw_footer(figure, lines)

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output, dpi=dpi, bbox_inches='tight', pad_inches=0.1,
        metadata={
            'Software': SOFTWARE,
            'Title': str(subject or output.name),
            'Description': ' · '.join(lines),
            'Parameters': json.dumps(parameters, sort_keys=True),
            'Sources': json.dumps(sources, sort_keys=True),
            'Generated': generated,
        })

    sidecar = output.with_name(output.name + '.json')
    sidecar.write_text(json.dumps({
        'image': str(relative(output)),
        'image_sha256': sha256(output),
        'generated_at': generated,
        'parameters': parameters,
        'facts': facts,
        'sources': sources,
        'script': str(relative(script)),
        'script_sha256': sha256(script),
        'command': command(),
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return output, sidecar


def read_sidecar(image):
    """The sidecar of an image, or None when it was written by hand."""
    sidecar = Path(image).with_name(Path(image).name + '.json')
    if not sidecar.is_file():
        return None
    try:
        return json.loads(sidecar.read_text(encoding='utf-8'))
    except ValueError:
        return None


def index(values):
    """Compact one-line summary of a sidecar, for printing."""
    if not values:
        return 'không có sidecar'
    labels = {key: (key, '') for key in values.get('parameters') or {}}
    items = pairs(values.get('parameters'), labels)
    items += pairs(values.get('facts'), labels)
    return ' · '.join(items)
