---
title: standardize.py
aliases:
  - standardize
type: tool
stage: data
source: tools/data/standardize.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/data
---

# `standardize.py`

> [!abstract] Mục đích
> Chuẩn hoá `city.glb` của bên thứ ba thành scene **một node một vật thể**:
> bake transform, đổi tên node, bỏ material/texture và ghi nguồn vào `extras`.
> Hình học không đổi.

> [!info] Vị trí
> **File** `tools/data/standardize.py` — stage `data`, bước 2  
> **Thuật toán** Bake ma trận `parent × local` theo cây node, weld tam giác trùng theo giá trị float, ghi float32  
> **Vào** `data/raw/scenes/city.glb` (scene Sketchfab, Y-up)  
> **Ra** `data/processed/scenes/city.standardized.glb`  
> **Cờ** `--input`, `--output`  
> **Đọc bằng** `tools/data/glb2off.py: transformed_objects`  
> **Ghi bằng** `lib/mesh_glb.py: write_glb`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `asset_extras(path)` | đường dẫn GLB | `dict` `extras` của khối `asset`, rỗng nếu thiếu | Tách chunk JSON để lấy `license`, `author`, `source_url`, `title` từ file gốc |
| `main()` | `--input`, `--output` | GLB chuẩn hoá + một dòng số đo | Duyệt node bằng `transformed_objects`, gộp tam giác bằng `indexed_from_triangles`, đổi tên `object_%03d`, ghi bằng `write_glb`, đọc lại tự kiểm |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy; `argparse`, `hashlib`, `json`, `struct`, `pathlib` | Mảng toạ độ, CLI, hash, đọc chunk GLB |
| Nội bộ | `tools/data/glb2off.py: transformed_objects` | Bake transform và trả triangle soup theo từng node |
| Nội bộ | `lib/mesh_glb.py: indexed_from_triangles, write_glb` | Weld tam giác rời thành lưới có chỉ số rồi ghi GLB |
| Dữ liệu | `data/raw/scenes/city.glb` | Scene nguồn duy nhất |

## Chạy

```bash
.venv/bin/python tools/data/standardize.py
.venv/bin/python tools/data/standardize.py \
    --input data/raw/scenes/city.glb --output /tmp/city.standardized.glb
```

Mặc định đọc `data/raw/scenes/city.glb` và ghi `data/processed/scenes/city.standardized.glb`.

## Scene gốc có gì

`city.glb` là glTF 2 nhị phân với 1 scene, 55 node:

```
scene "Sketchfab_Scene"
└─ node 0 "Sketchfab_model"     matrix: đổi trục + scale 0.0164
   └─ node 1 "...2025.obj.cleaner..."
      ├─ node 2..54 "Object_N"  mỗi node một mesh
```

Chỉ node 0 có transform. Tam giác trong accessor là toạ độ **local**: đỉnh đầu
của mesh 0 là `(2025.17, 691.17, 64.39)`, sau khi nhân ma trận scene thành
`(33.30, 1.06, −11.37)`.

## Các bước

1. **Bake transform.** `transformed_objects` duyệt cây, tính
   `M = parent × local(node)` và biến đổi mọi đỉnh: `p' = (p,1)ᵀ · Mᵀ`, lấy 3
   thành phần đầu. Kết quả là tam giác ở toạ độ world của scene.
2. **Gộp tam giác rời thành lưới có chỉ số.** `indexed_from_triangles` gom đỉnh
   trùng (theo giá trị float) thành `vertices` + `faces` cho từng node.
3. **Đổi tên.** Node thứ `i` thành `object_{i:03d}`; tên gốc giữ ở
   `extras.source_name` của node.
4. **Bỏ material và texture** — chỉ giữ hình học.
5. **Không đổi trục, không chuẩn hoá đơn vị**: scene chuẩn hoá vẫn Y-up và vẫn
   ở đơn vị gốc. Việc đổi Z-up/200 m là của `glb2off`/`triangulation`.
6. **Ghi extras cấp scene** (dùng cho trích dẫn):

   | Khóa | Giá trị |
   | --- | --- |
   | `source_file`, `source_sha256` | đường dẫn và hash của GLB gốc |
   | `license`, `author`, `source_url`, `title` | lấy từ `asset.extras` của nguồn |
   | `units` | `original model units` |
   | `axis` | `Y-up (glTF convention)` |
   | `objects`, `vertices`, `triangles` | số đo sau khi gộp |
   | `policy` | `transforms baked once; materials and textures dropped; node names normalized` |

7. **Tự kiểm.** Đọc lại file vừa ghi: tổng số tam giác phải bằng nguồn, mọi toạ
   độ hữu hạn.

## Hệ quả số học (quan trọng khi viết báo cáo)

- Bake chạy trên float64, nhưng GLB chỉ lưu float32.
- Vì vậy toạ độ bị làm tròn **trước** khi chuẩn hoá 200 m, khác với đường STL cũ
  (làm tròn **sau** khi chuẩn hoá).
- Hai đường lệch nhau cỡ `1,5e-5` m trước chuẩn hoá, `≤1,8e-6` m trên bề mặt.
  Chi tiết và hai SHA ở [`../../data/processed/README.md`](../../../data/processed/README.md).

## Đầu ra

```
{
  "meshes": 53, "vertices": 204682, "triangles": 301490, ...
}
Save at: data/processed/scenes/city.standardized.glb
```

File này **không commit** (≈6 MB, sinh lại được).

## Giới hạn

- Chỉ đọc primitive tam giác không nén; gặp Draco hoặc sparse accessor thì dừng.
- Không kiểm material, UV, normal — chúng bị bỏ.
- Đỉnh không được weld giữa các node: mỗi node giữ lưới riêng.

## Liên quan

- [`glb2off.md`](glb2off.md) — nơi định nghĩa `transformed_objects` và `read_glb_scene`.
- [`triangulation.md`](triangulation.md) — đọc scene chuẩn hoá để dựng bề mặt.
- [`../../data-format.md`](../../data-format.md) — khác biệt float32/float64 và hệ trục.
- [`../lib.md`](../lib.md) — container GLB tối giản của repo.
