# Dữ liệu đã xử lý

Thư mục này chứa sản phẩm của ba quy trình, không sửa tay. Đầu vào nằm ở
[`data/raw/`](../raw/); mỗi thư mục con ứng với một quy trình.

| Thư mục | Tệp | Quy trình | Công cụ |
| --- | --- | --- | --- |
| `standardized/` | `city.standardized.glb` | Standardize | `tools/standardize.py` |
| `off2glb/` | `*.off2glb.glb` | OFF → GLB cho Gazebo | `tools/off2glb.py` |
| `triangulation/` | `city.triangulation.cell5.off` + `.json` | Tam giác phân bề mặt | `tools/triangulation.py` |

`cell5` nghĩa là bề mặt dựng với **kích thước ô 5**. Tham số đầy đủ nằm trong
tệp `.json` đi kèm.

## Chạy

```bash
python3 tools/standardize.py
python3 tools/off2glb.py
.venv/bin/python tools/triangulation.py
```

`triangulation.py` cần Shapely và dùng STL chuẩn
`generated/funnel_preview/city.stl` (cùng hệ với `horizontal_plan.json`).
Thêm `--from-scene` nếu muốn dựng lại STL từ scene; khi đó bề mặt có thể lệch
khoảng 1e-6 do scene lưu float32 và bị chuẩn hoá lại.

## Trục toạ độ

- `city.standardized.glb` giữ **Y-up** đúng chuẩn glTF để mở bằng viewer.
- Gazebo **không** tự xoay glTF từ Y-up sang Z-up (xem `gz-common`
  `AssimpLoader.cc`: với glTF, root transform được giữ nguyên).
- Muốn dùng GLB Y-up trong Gazebo phải bake `(x, y, z) → (x, -z, y)`.
- Fixture `.off` dùng **Z-up** (z là cao độ), nên `.off2glb.glb` giữ nguyên
  toạ độ. Cờ `--to-z-up` dành cho nguồn Y-up.
- `city.triangulation.cell5.off` ở hệ **Gazebo đã chuẩn hoá, Z-up**, cùng hệ
  với `horizontal_plan.json`.

## Lưu trong Git

- `standardized/city.standardized.glb`: **không commit** (khoảng 6 MB, sinh
  lại được từ `data/raw/scenes/city.glb`).
- `off2glb/*.off2glb.glb`: commit, mỗi file vài KB.
- `triangulation/city.triangulation.cell5.off` và manifest: commit, đây là
  đầu vào thuật toán và có hash trong kết quả thí nghiệm.
