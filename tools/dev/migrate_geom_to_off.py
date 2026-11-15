# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (json, pathlib, sys).
"""Convert the legacy .off fixtures and meshes to OFF and .paths.json.

The mesh conversion only prepends the OFF magic line, so every vertex and
face line is preserved byte for byte. The path conversion parses the legacy
'bracketed path' records and stores the same floats in JSON.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_legacy_mesh(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    nv, nf, ne = map(int, lines[0].split())
    if len(lines) != 1 + nv + nf:
        raise ValueError('Mesh line count does not match header')
    points = [tuple(map(float, line.split())) for line in lines[1:1 + nv]]
    faces = []
    for line in lines[1 + nv:]:
        record = list(map(int, line.split()))
        if len(record) != 4 or record[0] != 3:
            raise ValueError(f'Expected triangular face record, got: {line}')
        faces.append(tuple(record[1:]))
    return points, faces, ne


def read_off(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != 'OFF':
        raise ValueError('Missing OFF magic line')
    nv, nf, ne = map(int, lines[1].split())
    if len(lines) != 2 + nv + nf:
        raise ValueError('OFF line count does not match header')
    points = [tuple(map(float, line.split())) for line in lines[2:2 + nv]]
    faces = []
    for line in lines[2 + nv:]:
        record = list(map(int, line.split()))
        if len(record) != 4 or record[0] != 3:
            raise ValueError(f'Expected triangular face record, got: {line}')
        faces.append(tuple(record[1:]))
    return points, faces, ne


def read_legacy_paths(text):
    paths = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        tokens = line.replace('[', ' ').replace(']', ' ').split()
        count, *coords = tokens
        count = int(count)
        coords = list(map(float, coords))
        if count < 2 or len(coords) != 3 * count:
            raise ValueError(f'Invalid path at line {number}')
        paths.append([tuple(coords[i:i + 3]) for i in range(0, len(coords), 3)])
    return paths


MESH_FILES = [
    ('data/input/cliff.geom', 'data/input/cliff.off'),
    ('data/input/demo_mesh.geom', 'data/input/demo_mesh.off'),
    ('data/input/J17.geom', 'data/input/J17.off'),
    ('data/input/L.geom', 'data/input/L.off'),
    ('data/input/star.geom', 'data/input/star.off'),
    ('generated/funnel_input_y2p00.geom', 'generated/funnel_input_y2p00.off'),
    ('generated/city_three_goals/g1/surface.geom', 'generated/city_three_goals/g1/surface.off'),
    ('generated/city_three_goals/g2/surface.geom', 'generated/city_three_goals/g2/surface.off'),
    ('generated/city_three_goals/g3/surface.geom', 'generated/city_three_goals/g3/surface.off'),
    ('generated/funnel_physics/surface_delivery/surface.geom',
     'generated/funnel_physics/surface_delivery/surface.off'),
    ('generated/surface_sensitivity/cell_15/surface.geom',
     'generated/surface_sensitivity/cell_15/surface.off'),
    ('generated/surface_sensitivity/cell_5/surface.geom',
     'generated/surface_sensitivity/cell_5/surface.off'),
    ('generated/surface_sensitivity/cell_7.5/surface.geom',
     'generated/surface_sensitivity/cell_7.5/surface.off'),
]

PATH_FILES = [
    ('data/expected/cliff.geom', 'data/expected/cliff.paths.json', 1),
    ('data/expected/demo_mesh.geom', 'data/expected/demo_mesh.paths.json', 1),
    ('data/expected/J17.geom', 'data/expected/J17.paths.json', 1),
    ('data/expected/L.geom', 'data/expected/L.paths.json', 1),
    ('data/expected/star.geom', 'data/expected/star.paths.json', 0),
]


def convert_mesh(source, target, apply):
    raw = (ROOT / source).read_bytes()
    text = raw.decode('utf-8')
    points_before, faces_before, edges = read_legacy_mesh(text)
    raw = raw.replace(b'\r\n', b'\n')
    raw = b'\n'.join(line.rstrip() for line in raw.split(b'\n'))
    header = b'OFF\n'
    if apply:
        (ROOT / target).write_bytes(header + raw)
    converted = (ROOT / target).read_bytes().decode('utf-8') if apply else 'OFF\n' + text
    points_after, faces_after, edges_after = read_off(converted)
    if points_before != points_after or faces_before != faces_after or edges != edges_after:
        raise ValueError(f'Geometry changed while converting {source}')
    return dict(source=source, target=target, vertices=len(points_before),
                faces=len(faces_before), edges=edges,
                bytes_before=len(raw), bytes_after=len(raw) + len(header))


def convert_paths(source, target, declared_source, apply):
    text = (ROOT / source).read_text(encoding='utf-8')
    paths = read_legacy_paths(text)
    payload = {
        'mesh': Path(target).name.split('.')[0],
        'source': declared_source,
        'coordinate_system': 'model units; values carried over from the legacy .off fixtures',
        'paths': paths,
    }
    if apply:
        (ROOT / target).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    reloaded = json.loads((ROOT / target).read_text(encoding='utf-8')) if apply else payload
    if [[list(point) for point in path] for path in reloaded['paths']] != \
            [[list(point) for point in path] for path in paths]:
        raise ValueError(f'Path values changed while converting {source}')
    return dict(source=source, target=target, paths=len(paths),
                points=sum(len(path) for path in paths))


def main():
    apply = '--apply' in sys.argv[1:]
    report = {'meshes': [], 'paths': []}
    for source, target in MESH_FILES:
        if not (ROOT / source).exists():
            print(f'skip missing {source}')
            continue
        report['meshes'].append(convert_mesh(source, target, apply))
    for source, target, declared_source in PATH_FILES:
        if not (ROOT / source).exists():
            print(f'skip missing {source}')
            continue
        report['paths'].append(convert_paths(source, target, declared_source, apply))
    verb = 'converted' if apply else 'checked'
    print(json.dumps(report, indent=2))
    print(f'{verb}: {len(report["meshes"])} meshes, {len(report["paths"])} path files')
    for item in report['meshes'] + report['paths']:
        print(f'Save at: {ROOT / item["target"]}')


if __name__ == '__main__':
    main()