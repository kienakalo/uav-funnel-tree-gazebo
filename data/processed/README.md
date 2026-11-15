# Dữ liệu đã xử lý

Thư mục này chứa sản phẩm của ba quy trình, không sửa tay. Đầu vào nằm ở
[`data/raw/`](../raw/).

| Tệp | Quy trình | Công cụ |
| --- | --- | --- |
| `scenes/city.standardized.glb` | Standardize | `tools/standardize.py` |
| `scenes/meshes/*.off2glb.glb` | OFF → GLB cho Gazebo | `tools/off2glb.py` |
| `meshes/city.triangulation.off` | Tam giác phân bề mặt | `tools/triangulation.py` |
| `meshes/city.triangulation.json` | Tham số, hash nguồn và thống kê bề mặt | `tools/triangulation.py` |

Tên file theo quy trình; tham số tam giác phân nằm trong tệp `.json` đi kèm.
Bề mặt hiện dùng ô 5, khe hở dọc 1,5 và dự phòng ngang 1,6.

## Chạy

```bash
python3 tools/standardize.py
python3 tools/off2glb.py
.venv/bin/python tools/triangulation.py
```

`triangulation.py` cần Shapely và dùng STL chuẩn
`generated/funnel_preview/city.stl` (cùng hệ với `horizontal_plan.json`).
Thêm `--from-scene` nếu muốn dựng lại STL từ scene; khi đó bề mặt có thể lệch
khoảng 1e-6 do scene lưu float32 và bị chuẩn hoá lại. Nếu chạy với tham số
khác mà tệp đích đã tồn tại, tool dừng và yêu cầu `--force`.

## Trục toạ độ

- `city.standardized.glb` giữ **Y-up** đúng chuẩn glTF để mở bằng viewer.
- Gazebo **không** tự xoay glTF từ Y-up sang Z-up (xem `gz-common`
  `AssimpLoader.cc`: với glTF, root transform được giữ nguyên).
- Muốn dùng GLB Y-up trong Gazebo phải bake `(x, y, z) → (x, -z, y)`.
- Fixture `.off` dùng **Z-up** (z là cao độ), nên `.off2glb.glb` giữ nguyên
  toạ độ. Cờ `--to-z-up` dành cho nguồn Y-up.
- `city.triangulation.off` ở hệ **Gazebo đã chuẩn hoá, Z-up**, cùng hệ với
  `horizontal_plan.json`.

## Lưu trong Git

- `scenes/city.standardized.glb`: **không commit** (khoảng 6 MB, sinh lại
  được từ `data/raw/scenes/city.glb`).
- `scenes/meshes/*.off2glb.glb`: commit, mỗi file vài KB.
- `meshes/city.triangulation.off` và manifest: commit, đây là đầu vào thuật
  toán và có hash trong kết quả thí nghiệm.
