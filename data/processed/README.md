# Dữ liệu đã xử lý

Thư mục này chứa đầu vào đã xử lý cho thuật toán và mô phỏng, không sửa tay.
Nguồn nằm ở [`data/raw/`](../raw/).

| Tệp | Bước | Công cụ |
| --- | --- | --- |
| `meshes/*.off` | Pass-through (validate + copy) | `tools/copy_meshes.py` |
| `scenes/city.standardized.glb` | Standardize | `tools/standardize.py` |
| `scenes/meshes/*.off2glb.glb` | OFF → GLB cho Gazebo | `tools/off2glb.py` |
| `meshes/city.triangulation.off` | Tam giác phân bề mặt | `tools/triangulation.py` |

Tên file theo quy trình. Không có file metadata đi kèm; tham số được ghi ở
dưới và in ra khi chạy tool.

## Chạy

```bash
python3 tools/copy_meshes.py --write
python3 tools/standardize.py
python3 tools/off2glb.py
.venv/bin/python tools/triangulation.py --force
.venv/bin/python tools/data_viz.py --all
```

Bước cuối render mỗi mesh `.off` thành một ảnh PNG trong
`generated/data_viz/`, kèm các đường tham chiếu trong `data/expected/` nếu có.
Dùng `--show` để mở cửa sổ 3D tương tác thay vì ghi PNG.

`check.py`, `plan.py` và `tests/` đọc fixture từ `data/processed/meshes/`,
không đọc thẳng `data/raw/`.

Thêm `--force` khi ghi đè bề mặt đã có; nếu không, tool dừng. `triangulation.py`
cần Shapely và dùng STL chuẩn `generated/funnel_preview/city.stl` (cùng hệ với
`horizontal_plan.json`). Thêm `--from-scene` nếu muốn dựng lại STL từ scene;
khi đó bề mặt có thể lệch khoảng 1e-6 do scene lưu float32 và bị chuẩn hoá lại.

## Xem mesh `.off`

GLB mở được bằng Blender, MeshLab hoặc trình xem glTF; `.off` cần
`tools/data_viz.py`.

```bash
# một mesh (tên không cần .off)
.venv/bin/python tools/data_viz.py L

# nhiều mesh
.venv/bin/python tools/data_viz.py L terrain cube

# bề mặt thành phố
.venv/bin/python tools/data_viz.py city.triangulation

# đường dẫn đầy đủ, kể cả file ngoài data/processed/meshes
.venv/bin/python tools/data_viz.py data/processed/meshes/L.off

# tất cả
.venv/bin/python tools/data_viz.py --all
```

PNG ghi vào `generated/data_viz/<tên>.png`.

| Cờ | Tác dụng |
| --- | --- |
| `--show` | Mở cửa sổ 3D tương tác thay vì ghi PNG |
| `--source N` | Đánh dấu đỉnh nguồn N bằng màu cam |
| `--no-paths` | Không vẽ đè đường tham chiếu từ `data/expected/` |
| `--input DIR` | Đổi thư mục tìm mesh, mặc định `data/processed/meshes` |
| `--output DIR` | Đổi thư mục ghi ảnh, mặc định `generated/data_viz` |

Với `--show`, cửa sổ Matplotlib cho xoay/zoom bằng chuột; đóng cửa sổ để
thoát. Cần môi trường có giao diện (Ubuntu/WSLg); nếu backend không mở được,
dùng chế độ ghi PNG.

Mesh có `data/expected/<tên>.paths.json` sẽ được vẽ đè các đường tham chiếu
màu đỏ. `python3 main.py data` render tất cả ở bước cuối của stage `data`.

## Tham số bề mặt hiện tại

| Tham số | Giá trị |
| --- | --- |
| Cell | 5 |
| Coverage | `city` |
| Vertical clearance | 1,5 |
| Horizontal half width | 1,6 |
| Max axis slope | 0,5 |
| STL đầu vào | `generated/funnel_preview/city.stl` |
| Kết quả | 2.295 đỉnh, 4.400 tam giác, 6.694 cạnh |

Tham số được in ra console mỗi lần chạy. Không có file metadata đi kèm; muốn
tái lập thì dùng đúng lệnh và tham số ở trên.

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
- `meshes/city.triangulation.off`: commit, đây là đầu vào thuật toán và có
  hash trong kết quả thí nghiệm.
