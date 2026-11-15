# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, hashlib, json, struct, pathlib);
# local modules (mesh).
"""Write or check one metadata sidecar per raw data file.

Sidecar naming: <file>.json, for example data/raw/meshes/L.off.json.

Computed fields (sha256, bytes, counts) are always refreshed from the file.
Curated fields (origin, license, expected, notes) are preserved from an
existing sidecar or taken from the table below when the sidecar is new.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mesh import read_off

RAW_MESHES = ROOT / 'data/raw/meshes'
RAW_SCENES = ROOT / 'data/raw/scenes'

CURATED = {
    'cliff.off': {
        'origin': 'first-party', 'license': 'BSD-3-Clause',
        'expected': 'data/expected/cliff.paths.json',
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Concave step used by the clipping checks.',
    },
    'demo_mesh.off': {
        'origin': 'first-party', 'license': 'BSD-3-Clause',
        'expected': 'data/expected/demo_mesh.paths.json',
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Imported demo mesh with high-precision coordinates.',
    },
    'J17.off': {
        'origin': 'first-party', 'license': 'BSD-3-Clause',
        'expected': 'data/expected/J17.paths.json',
        'units': 'model units', 'axis': 'as authored', 'notes': '',
    },
    'L.off': {
        'origin': 'first-party', 'license': 'BSD-3-Clause',
        'expected': 'data/expected/L.paths.json',
        'units': 'model units', 'axis': 'as authored',
        'notes': 'L-shaped surface with a concave edge.',
    },
    'star.off': {
        'origin': 'first-party', 'license': 'BSD-3-Clause',
        'expected': 'data/expected/star.paths.json',
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Reference data covers source 0 only.',
    },
    'cube.off': {
        'origin': 'paper-derived', 'license': 'BSD-3-Clause', 'expected': None,
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Constructed from the original Funnel Tree paper idea; geometry checks only.',
    },
    'dome.off': {
        'origin': 'paper-derived', 'license': 'BSD-3-Clause', 'expected': None,
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Constructed from the original Funnel Tree paper idea; geometry checks only.',
    },
    'icosahedron.off': {
        'origin': 'paper-derived', 'license': 'BSD-3-Clause', 'expected': None,
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Constructed from the original Funnel Tree paper idea; geometry checks only.',
    },
    'terrain.off': {
        'origin': 'paper-derived', 'license': 'BSD-3-Clause', 'expected': None,
        'units': 'model units', 'axis': 'as authored',
        'notes': 'Constructed from the original Funnel Tree paper idea; geometry checks only.',
    },
}

CITY = {
    'origin': 'third-party', 'license': 'CC-BY-4.0',
    'expected': None, 'units': 'original model units', 'axis': 'Y-up (glTF)',
    'notes': 'Saigon 3D City asset; see ATTRIBUTION.md.',
}


def describe_off(path):
    mesh = read_off(path)
    lines = [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    header = lines[1] if lines and lines[0] == 'OFF' else lines[0]
    _, _, declared_edges = map(int, header.split())
    return {
        'format': 'OFF',
        'vertices': len(mesh.points),
        'faces': len(mesh.faces),
        'declared_edges': declared_edges,
        'computed_edges': len(mesh.edge_faces),
    }


def describe_glb(path):
    blob = path.read_bytes()
    magic, version, total = struct.unpack_from('<4sII', blob)
    if magic != b'glTF' or version != 2 or total != len(blob):
        raise ValueError(f'{path}: invalid GLB2')
    offset, chunks = 12, {}
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        chunks[kind] = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    document = json.loads(chunks[0x4E4F534A])
    triangles = 0
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            accessor = primitive.get('indices')
            if accessor is None:
                accessor = primitive['attributes']['POSITION']
            triangles += document['accessors'][accessor]['count'] // 3
    return {
        'format': 'GLB2',
        'nodes': len(document.get('nodes', [])),
        'meshes': len(document.get('meshes', [])),
        'triangles': triangles,
    }


def sidecar_path(path):
    return path.with_name(path.name + '.json')


def expected_payload(path, current):
    name = path.name
    curated = dict(CURATED.get(name, CITY))
    if current:
        for key in ('origin', 'license', 'expected', 'units', 'axis', 'notes'):
            if key in current:
                curated[key] = current[key]
    payload = {'schema': 1, 'file': name}
    payload.update(describe_glb(path) if path.suffix == '.glb' else describe_off(path))
    payload.update({
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes': path.stat().st_size,
        'origin': curated['origin'],
        'license': curated['license'],
        'expected': curated['expected'],
        'units': curated['units'],
        'axis': curated['axis'],
        'notes': curated['notes'],
    })
    return payload


def raw_files():
    return sorted(RAW_MESHES.glob('*.off')) + sorted(RAW_SCENES.glob('*.glb'))


def write_all():
    written = []
    for path in raw_files():
        target = sidecar_path(path)
        current = json.loads(target.read_text(encoding='utf-8')) if target.is_file() else None
        payload = expected_payload(path, current)
        target.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        written.append(target)
    return written


def check_all(root=ROOT):
    root = Path(root)
    problems = []
    files = sorted((root / 'data/raw/meshes').glob('*.off')) + \
        sorted((root / 'data/raw/scenes').glob('*.glb'))
    for path in files:
        target = path.with_name(path.name + '.json')
        if not target.is_file():
            problems.append(f'{path}: missing sidecar')
            continue
        current = json.loads(target.read_text(encoding='utf-8'))
        expected = expected_payload(path, current)
        for key, value in expected.items():
            if current.get(key) != value:
                problems.append(f'{path}: {key} expected {value!r}, found {current.get(key)!r}')
    known = {path.with_name(path.name + '.json') for path in files}
    for target in list((root / 'data/raw/meshes').glob('*.json')) + \
            list((root / 'data/raw/scenes').glob('*.json')):
        if target not in known:
            problems.append(f'{target}: orphan sidecar')
    if problems:
        raise SystemExit('Raw sidecar check failed:\n  ' + '\n  '.join(problems))
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true', help='Create or refresh sidecars')
    group.add_argument('--check', action='store_true', help='Verify sidecars against the files')
    args = parser.parse_args()
    if args.write:
        for target in write_all():
            print(f'Save at: {target}')
    else:
        count = check_all(ROOT)
        print(f'Raw sidecars: {count} files consistent')


if __name__ == '__main__':
    main()
