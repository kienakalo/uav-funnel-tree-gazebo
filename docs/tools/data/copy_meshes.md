---
title: copy_meshes.py
aliases:
  - copy_meshes
type: tool
stage: data
source: tools/data/copy_meshes.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/data
---

# `copy_meshes.py`

> [!abstract] Mục đích
> Sao chép **nguyên byte** 9 fixture OFF từ `data/raw/meshes/` sang
> `data/processed/meshes/` sau khi kiểm cú pháp, để mọi stage sau chỉ đọc một thư
> mục đã được xác nhận.

> [!info] Vị trí
> **File** `tools/data/copy_meshes.py` — stage `data`, bước 1  
> **Thuật toán** Kiểm cú pháp bằng `read_off` rồi `shutil.copyfile` — không parse lại, không biến đổi hình học  
> **Vào** `data/raw/meshes/*.off` (9 fixture, bất biến)  
> **Ra** `data/processed/meshes/*.off`, byte-identical với nguồn  
> **Cờ** `--write` hoặc `--check` (bắt buộc chọn một)  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `write_all()` | — | tạo `data/processed/meshes/`, in `Save at:` từng file | Đọc và kiểm mọi `.off` bằng `read_off`, rồi `shutil.copyfile` sang đích |
| `check_all(root=ROOT)` | thư mục gốc repo | in số cặp khớp; thoát mã 1 nếu lệch | So byte từng cặp `raw/` ↔ `processed/` |
| `main()` | `--write` / `--check` | mã thoát | Chọn chế độ rồi gọi hàm trên |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | `argparse`, `shutil`, `sys`, `pathlib` | CLI, copy byte, đường dẫn |
| Nội bộ | `lib/mesh_off.py: read_off` | Kiểm cú pháp OFF trước khi copy |
| Dữ liệu | `data/raw/meshes/*.off` | Nguồn fixture gốc, không sửa |

## Chạy

```bash
.venv/bin/python tools/data/copy_meshes.py --write    # copy rồi in Save at từng file
.venv/bin/python tools/data/copy_meshes.py --check    # so byte, thoát 1 nếu lệch
```

## Việc nó làm

1. Với mỗi `.off` trong `data/raw/meshes/`, đọc và kiểm bằng
   `lib/mesh_off.py: read_off`:
   - dòng đầu `OFF`, header `V F E` đọc được;
   - `V ≥ 3`, `F ≥ 1`, số dòng = `2 + V + F`;
   - mỗi mặt là tam giác, chỉ số nằm trong `0..V−1`;
   - toạ độ hữu hạn.
2. `shutil.copyfile` sang `data/processed/meshes/` — **byte-identical**, không
   parse lại rồi ghi.
3. `--check` so byte từng cặp raw/processed; lệch thì liệt kê và thoát khác 0.

## Vì sao copy thay vì để tool đọc `raw/`

- Downstream chỉ đọc `data/processed/`; `raw/` là nguồn bất biến.
- Bản copy tách "nguồn" khỏi "đầu vào đã kiểm tra": nếu ai sửa nhầm một bên,
  `--check` phát hiện ngay.
- Không biến đổi hình học, nên hash của fixture trong `raw/` và `processed/`
  trùng nhau.

## Đầu ra

```
Save at: data/processed/meshes/<tên>.off     (9 dòng)
Processed meshes: 9 copies consistent        (khi --check)
```

## Khi nào chạy lại

- Thêm fixture mới vào `data/raw/meshes/`.
- Nghi ngờ `data/processed/` bị sửa tay.

## Giới hạn

Chỉ kiểm cấu trúc file, không kiểm topology (non-manifold, fan rời). Việc đó do
`Mesh` làm khi `set_start_goal` hoặc `run_funnel` đọc mesh.

## Liên quan

- [`set_start_goal.md`](set_start_goal.md) — bước 7 chọn START/GOAL trên chính các mesh này.
- [`off2glb.md`](off2glb.md) — cùng fixture, chuyển sang GLB để mở bằng viewer.
- [`../../data-format.md`](../../data-format.md) — quy tắc định dạng OFF.
- [`../lib.md`](../lib.md) — `read_off`, `write_off`, `inspect_mesh`, `Mesh`.
