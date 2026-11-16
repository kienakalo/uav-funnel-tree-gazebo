# `off2glb.py`

| | |
| --- | --- |
| Stage | `data` bước 3 |
| Vào | `data/raw/meshes/*.off` |
| Ra | `data/processed/scenes/meshes/<mesh>.off2glb.glb` |
| Cờ | `--input`, `--output`, `--mesh` (lặp lại), `--keep-z-up` |

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
