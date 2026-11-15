# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, pathlib, shutil);
# local modules (mesh).
"""Copy the validated raw OFF fixtures into data/processed/meshes.

The fixtures do not need a geometric transformation, but downstream code reads
them from data/processed. The copy is byte-identical and is validated with the
same OFF parser the planner uses. Origin, licence and axis for every fixture
are documented in data/README.md instead of per-file sidecars.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mesh import read_off

RAW = ROOT / 'data/raw/meshes'
OUTPUT = ROOT / 'data/processed/meshes'


def write_all():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    written = []
    for source in sorted(RAW.glob('*.off')):
        read_off(source)
        target = OUTPUT / source.name
        shutil.copyfile(source, target)
        written.append(target)
    return written


def check_all(root=ROOT):
    root = Path(root)
    raw_dir = root / 'data/raw/meshes'
    out_dir = root / 'data/processed/meshes'
    problems = []
    for source in sorted(raw_dir.glob('*.off')):
        target = out_dir / source.name
        if not target.is_file():
            problems.append(f'{target}: missing processed copy')
        elif source.read_bytes() != target.read_bytes():
            problems.append(f'{target}: bytes differ from {source}')
    if problems:
        raise SystemExit('Processed mesh check failed:\n  ' + '\n  '.join(problems))
    return len(list(raw_dir.glob('*.off')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true', help='Copy fixtures into processed/')
    group.add_argument('--check', action='store_true', help='Verify copies match the raw files')
    args = parser.parse_args()
    if args.write:
        for target in write_all():
            print(f'Save at: {target}')
    else:
        count = check_all(ROOT)
        print(f'Processed meshes: {count} copies consistent')


if __name__ == '__main__':
    main()
