# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, hashlib, json, pathlib);
# local modules (mesh, raw_sidecars).
"""Pass-through the validated raw OFF fixtures into data/processed/meshes.

These fixtures do not need a geometric transformation, but downstream code
should still read them from data/processed. Copying validates each mesh,
keeps the bytes unchanged, and writes a processed-asset sidecar that points
back to the raw file and its hash.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from mesh import read_off
from raw_sidecars import describe_off, sidecar_path as raw_sidecar

RAW = ROOT / 'data/raw/meshes'
OUTPUT = ROOT / 'data/processed/meshes'


def payload(source, target):
    raw_meta = json.loads(raw_sidecar(source).read_text(encoding='utf-8'))
    described = describe_off(target)
    data = {
        'schema': 1,
        'kind': 'processed-asset',
        'file': target.name,
        'format': 'OFF',
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'bytes': target.stat().st_size,
        'geometry': described['geometry'],
        'units': raw_meta['units'],
        'axis': raw_meta['axis'],
        'origin': raw_meta['origin'],
        'license': raw_meta['license'],
        'expected': raw_meta['expected'],
        'notes': raw_meta['notes'],
        'source': {
            'file': source.relative_to(ROOT).as_posix(),
            'sha256': raw_meta['sha256'],
        },
    }
    return data


def write_all():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    written = []
    for source in sorted(RAW.glob('*.off')):
        read_off(source)
        target = OUTPUT / source.name
        shutil.copyfile(source, target)
        metadata = payload(source, target)
        meta_path = target.with_name(target.name + '.json')
        meta_path.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        written.extend([target, meta_path])
    return written


def check_all(root=ROOT):
    root = Path(root)
    problems = []
    raw_dir = root / 'data/raw/meshes'
    out_dir = root / 'data/processed/meshes'
    for source in sorted(raw_dir.glob('*.off')):
        target = out_dir / source.name
        meta_path = target.with_name(target.name + '.json')
        if not target.is_file():
            problems.append(f'{target}: missing processed copy')
            continue
        if source.read_bytes() != target.read_bytes():
            problems.append(f'{target}: bytes differ from {source}')
        if not meta_path.is_file():
            problems.append(f'{target}: missing sidecar')
            continue
        current = json.loads(meta_path.read_text(encoding='utf-8'))
        expected = payload(source, target)
        for key, value in expected.items():
            if current.get(key) != value:
                problems.append(f'{target}: {key} expected {value!r}, found {current.get(key)!r}')
    if problems:
        raise SystemExit('Processed mesh check failed:\n  ' + '\n  '.join(problems))
    return len(list(raw_dir.glob('*.off')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true', help='Copy and refresh sidecars')
    group.add_argument('--check', action='store_true', help='Verify copies and sidecars')
    args = parser.parse_args()
    if args.write:
        for target in write_all():
            print(f'Save at: {target}')
    else:
        count = check_all(ROOT)
        print(f'Processed meshes: {count} files consistent')


if __name__ == '__main__':
    main()
