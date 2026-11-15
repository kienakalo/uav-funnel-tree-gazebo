# Dữ liệu đã xử lý

Thư mục này chứa sản phẩm của ba quy trình, không sửa tay. Đầu vào nằm ở
[`data/raw/`](../raw/) và đầu ra không được dùng làm nguồn cho quy trình khác.

| Tệp | Nội dung | Sinh bởi |
| --- | --- | --- |
| `scenes/city.scene.glb` | Scene thành phố đã chuẩn hoá, Y-up | `tools/prepare_scene.py` |
| `scenes/meshes/*.sim.glb` | Fixture chuyển sang GLB cho Gazebo, Z-up | `tools/off_to_glb.py` |
| `meshes/city.surface.cell5.off` | Bề mặt dẫn đường đã tam giác phân, Z-up | `tools/prepare_surface.py` |
| `meshes/city.surface.cell5.json` | Tham số, hash nguồn và thống kê của bề mặt | `tools/prepare_surface.py` |

## Chạy

```bash
python3 tools/prepare_scene.py
python3 tools/off_to_glb.py
.venv/bin/python tools/prepare_surface.py
```

`prepare_surface.py` cần Shapely và dùng STL chuẩn
`generated/funnel_preview/city.stl` (cùng hệ với `horizontal_plan.json`).
Thêm `--from-scene` nếu muốn dựng lại STL từ scene; khi đó bề mặt có thể lệch
cỡ 1e-6 do scene lưu float32 và bị chuẩn hoá lại.

## Trục toạ độ

- `city.scene.glb` giữ **Y-up** đúng chuẩn glTF để mở bằng viewer.
- Gazebo **không** tự xoay glTF từ Y-up sang Z-up (xem `gz-common`
  `AssimpLoader.cc`: với glTF, root transform được giữ nguyên).
- Vì vậy muốn dùng một GLB Y-up trong Gazebo phải bake
  `(x, y, z) → (x, -z, y)`.
- Fixture `.off` của repo dùng **Z-up** (z là cao độ), nên `.sim.glb` giữ
  nguyên toạ độ. Dùng `tools/off_to_glb.py --to-z-up` cho nguồn Y-up.
- `city.surface.cell5.off` ở hệ **Gazebo đã chuẩn hoá, Z-up**, cùng hệ với
  `horizontal_plan.json`.

## Lưu trong Git

- `scenes/city.scene.glb`: **không commit** (khoảng 6 MB, sinh lại được từ
  `data/raw/scenes/city.glb`).
- `scenes/meshes/*.sim.glb`: commit, mỗi file vài KB.
- `meshes/city.surface.cell5.off` và manifest: commit, đây là đầu vào thuật
  toán và có hash trong kết quả thí nghiệm.
