---
title: off2glb.py
aliases:
  - off2glb
type: tool
stage: data
source: tools/data/off2glb.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/data
---

# `off2glb.py`

> [!abstract] Mục đích
> Chuyển từng fixture OFF sang glTF nhị phân (Y-up mặc định) để mở bằng
> Blender, MeshLab hay bất kỳ viewer glTF nào; chỉ đổi định dạng, không sửa hình
> học.

> [!info] Vị trí
> **File** `tools/data/off2glb.py` — stage `data`, bước 4  
> **Thuật toán** Đổi trục `(x, y, z) → (x, z, −y)`, ghi GLB float32, đọc lại đối chiếu số đỉnh/mặt  
> **Vào** `data/raw/meshes/*.off`  
> **Ra** `data/processed/scenes/meshes/<mesh>.off2glb.glb`  
> **Cờ** `--input`, `--output`, `--mesh` (lặp lại), `--keep-z-up`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `convert(source, output, keep_z_up=False)` | một `.off`, đích `.glb`, cờ trục | `report` của `write_glb` (số mesh/đỉnh/mặt/byte) | Đọc OFF, đổi `(x, y, z) → (x, z, −y)` trừ khi `keep_z_up`, ghi GLB kèm extras, đọc lại so số đỉnh/mặt |
| `main()` | `--input`, `--output`, `--mesh`, `--keep-z-up` | mỗi file một dòng JSON + `Save at:` | Lọc fixture theo `--mesh` rồi gọi `convert` |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy; `argparse`, `hashlib`, `json`, `pathlib` | Đổi trục, CLI, hash nguồn |
| Nội bộ | `lib/mesh_off.py: read_off` | Đọc fixture thành mảng float64 + chỉ số |
| Nội bộ | `lib/mesh_glb.py: write_glb, read_glb` | Ghi GLB và đọc lại để tự kiểm |
| Dữ liệu | `data/raw/meshes/*.off` | Fixture gốc, 9 file |

## Chạy

```bash
.venv/bin/python tools/data/off2glb.py                       # cả 9 fixture
.venv/bin/python tools/data/off2glb.py --mesh terrain        # một fixture
.venv/bin/python tools/data/off2glb.py --mesh cube --keep-z-up
```

## Việc nó làm

1. Đọc fixture bằng `lib/mesh_off.py: read_off` (mảng NumPy float64 + chỉ số).
2. Đổi trục từ Z-up (quy ước fixture) sang Y-up (quy ước glTF):

   ```
   (x, y, z) → (x, z, −y)
   ```

   Ví dụ: `(1, 2, 3) → (1, 3, −2)`.

3. Ghi GLB bằng `write_glb` (float32, một node, `mode` tam giác).
4. Ghi `extras`: `source_file`, `source_sha256`, `axis`, `units`,
   `vertices`, `triangles`, `policy` (`format conversion only; no geometric repair`).
5. Đọc lại file vừa ghi và so số đỉnh/mặt; lệch thì báo lỗi.

## Cờ

| Cờ | Tác dụng |
| --- | --- |
| `--input DIR` | Thư mục nguồn (mặc định `data/raw/meshes`) |
| `--output DIR` | Thư mục ra (mặc định `data/processed/scenes/meshes`) |
| `--mesh TÊN` | Chỉ chuyển các fixture này; lặp lại được |
| `--keep-z-up` | Giữ Z-up thay vì ghi Y-up (khi cần hệ mô phỏng) |

## Vì sao cần bước này

`.off` không mở được bằng Blender/MeshLab; GLB thì mở được ở mọi viewer glTF.
Bản Y-up để xem đúng chiều; `--keep-z-up` để dùng trong mô phỏng nếu sau này cần.

## Đầu ra

```
terrain: {"meshes": 1, "vertices": 49, "triangles": 72, "bytes": 2668}
Save at: data/processed/scenes/meshes/terrain.off2glb.glb
```

9 file, tổng vài chục KB — **có commit**, vì là đầu ra ổn định và nhỏ.

## Giới hạn

- Chỉ đổi hệ trục, không sửa hình học, không weld, không chuẩn hoá tỉ lệ.
- Float32 khi ghi, nên toạ độ double của fixture bị làm tròn (xem
  [`../../data/README.md`](../../../data/README.md) mục định dạng).

## Liên quan

- [`copy_meshes.md`](copy_meshes.md) — bước 1 đưa fixture vào `processed/`.
- [`standardize.md`](standardize.md) — chuẩn hoá scene thành phố theo cùng định dạng.
- [`../../data-format.md`](../../data-format.md) — quy ước trục và float32 khi ghi GLB.
- [`../lib.md`](../lib.md) — `write_glb`/`read_glb` và cách ghi accessor.
