# `standardize.py`

| | |
| --- | --- |
| Stage | `data` bước 2 |
| Vào | `data/raw/scenes/city.glb` (scene Sketchfab) |
| Ra | `data/processed/scenes/city.standardized.glb` |
| Cờ | `--input`, `--output` |
| Đọc bằng | `tools/data/glb2off.py: transformed_objects` |
| Ghi bằng | `lib/mesh_glb.py: write_glb` |

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
