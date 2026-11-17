#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, json, struct, sys, zlib, pathlib).
"""List every figure with the settings that produced it.

Each PNG written by this repository carries a footer, PNG text metadata and a
sidecar ``<name>.png.json`` (see lib/figstamp.py). This tool reads all three
back, so a folder full of images can be checked before anything is pasted into
the report:

  .venv/bin/python tools/figures.py
  .venv/bin/python tools/figures.py --folder generated/routes
  .venv/bin/python tools/figures.py --json generated/figures.json

A figure is reported as a problem when the sidecar is missing, when the SHA256
recorded there no longer matches the file (the image was overwritten), when the
PNG metadata disagrees with the sidecar, or when a sidecar has no image. Exit
code is 1 when there is at least one problem, so it can guard a commit.

Examples:
  .venv/bin/python tools/figures.py
  .venv/bin/python tools/figures.py --folder generated --no-fail
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
from figstamp import relative, sha256

DEFAULT_FOLDERS = (ROOT / 'generated',)
SIGNATURE = b'\x89PNG\r\n\x1a\n'


def fail(message):
    raise SystemExit(f'figures: {message}')


def png_text(blob):
    """Read the tEXt, zTXt and iTXt chunks of a PNG."""
    if blob[:8] != SIGNATURE:
        fail(f'{len(blob)} byte file is not a PNG')
    text = {}
    offset = 8
    while offset < len(blob):
        size, kind = struct.unpack_from('>I4s', blob, offset)
        data = blob[offset + 8:offset + 8 + size]
        if kind == b'tEXt':
            key, _, value = data.partition(b'\x00')
            text[key.decode('latin-1')] = value.decode('latin-1')
        elif kind == b'zTXt':
            key, _, rest = data.partition(b'\x00')
            method, _, payload = rest.partition(b'\x00')
            if method == b'\x00':
                text[key.decode('latin-1')] = zlib.decompress(
                    payload).decode('latin-1')
        elif kind == b'iTXt':
            key, _, rest = data.partition(b'\x00')
            compressed, rest = rest[0:1], rest[2:]
            _, _, rest = rest.partition(b'\x00')      # language tag
            _, _, payload = rest.partition(b'\x00')   # translated keyword
            if compressed == b'\x01':
                payload = zlib.decompress(payload)
            text[key.decode('latin-1')] = payload.decode('utf-8')
        if kind == b'IEND':
            break
        offset += 12 + size
    return text


def sidecar_path(image):
    return image.with_name(image.name + '.json')


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def problems_of(image, sidecar, embedded):
    problems = []
    if sidecar is None:
        problems.append('thiếu sidecar')
    else:
        if sidecar.get('image_sha256') != sha256(image):
            problems.append('SHA ảnh lệch')
        recorded = sidecar.get('image')
        if recorded and Path(recorded).name != image.name:
            problems.append('sidecar trỏ ảnh khác')
    if not embedded:
        problems.append('thiếu metadata PNG')
    elif sidecar is not None:
        try:
            if json.loads(embedded.get('Parameters', '{}')) != sidecar.get('parameters'):
                problems.append('metadata PNG khác sidecar')
        except ValueError:
            problems.append('metadata PNG hỏng')
    return problems


def summary(sidecar):
    """One line of parameters and facts, as the footer shows them."""
    if not sidecar:
        return ''
    items = []
    for key, value in (sidecar.get('parameters') or {}).items():
        items.append(f'{key}={value}' if not isinstance(value, bool)
                     else f'{key}={"Y" if value else "N"}')
    for key, value in (sidecar.get('facts') or {}).items():
        items.append(f'{key}={value}')
    return ' · '.join(items)


def collect(folders):
    images, orphans = [], []
    for folder in folders:
        if not folder.is_dir():
            fail(f'{relative(folder)} không phải thư mục')
        images += sorted(folder.rglob('*.png'))
        for sidecar in sorted(folder.rglob('*.png.json')):
            image = sidecar.with_name(sidecar.name[:-len('.json')])
            if not image.is_file():
                orphans.append(sidecar)
    return images, orphans


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--folder', type=Path, action='append',
                        help='Thư mục cần quét (mặc định: generated)')
    parser.add_argument('--json', type=Path, metavar='PATH',
                        help='Ghi bảng tổng hợp ra JSON')
    parser.add_argument('--no-fail', action='store_true',
                        help='Trả mã 0 dù có ảnh lỗi')
    args = parser.parse_args()

    folders = [folder.resolve() for folder in args.folder or DEFAULT_FOLDERS]
    images, orphans = collect(folders)
    if not images and not orphans:
        fail('không thấy ảnh nào trong ' + ', '.join(str(relative(f))
                                                     for f in folders))

    records, failed = [], 0
    for image in images:
        sidecar = read_json(sidecar_path(image))
        embedded = png_text(image.read_bytes())
        problems = problems_of(image, sidecar, embedded)
        if problems:
            failed += 1
        when = (sidecar or {}).get('generated_at') or embedded.get('Generated', '')
        print(relative(image))
        line = summary(sidecar) or embedded.get('Description', '')
        if line:
            print(f'    {line}')
        mark = 'ok' if not problems else ' · '.join(problems)
        print(f'    {when[:16].replace("T", " ")} · {mark}')
        records.append({
            'image': str(relative(image)),
            'image_sha256': sha256(image),
            'generated_at': when,
            'parameters': (sidecar or {}).get('parameters'),
            'facts': (sidecar or {}).get('facts'),
            'sources': (sidecar or {}).get('sources'),
            'script': (sidecar or {}).get('script'),
            'status': 'ok' if not problems else 'problem',
            'problems': problems,
        })

    for sidecar in orphans:
        failed += 1
        print(relative(sidecar))
        print('    · sidecar mồ côi (không có ảnh)')
        records.append({'image': None, 'sidecar': str(relative(sidecar)),
                        'status': 'problem', 'problems': ['sidecar mồ côi']})

    print(f'\n{len(images)} ảnh, {len(orphans)} sidecar mồ côi, '
          f'{failed} lỗi')
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({'images': records}, indent=2,
                                        ensure_ascii=False) + '\n',
                             encoding='utf-8')
        print(f'Save at: {relative(args.json)}')
    if failed and not args.no_fail:
        raise SystemExit('figures: có ảnh không khớp tham số đã ghi; '
                         'xem danh sách ở trên')


if __name__ == '__main__':
    main()
