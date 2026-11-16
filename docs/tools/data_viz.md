# `data_viz.py`

| | |
| --- | --- |
| Stage | `data` bước 5 |
| Vào | `.off` trong `data/processed/meshes/` (mặc định) |
| Ra | `generated/data_viz/<tên>.png` hoặc cửa sổ 3D |
| Cờ | `--all`, `--input`, `--output`, `--source N`, `--no-paths`, `--scene [GLB]`, `--scene-triangles N`, `--show` |
| Cần | NumPy, Matplotlib; `--scene` thêm `glb2off.read_glb_scene` |

## Ba chế độ

### 1. Một hoặc nhiều mesh

```bash
.venv/bin/python tools/data/data_viz.py L terrain cube
```

- Đọc bằng `lib/mesh_off.py: read_off`.
- Vẽ `plot_trisurf(points, triangles=faces, cmap='viridis', edgecolor='#333333',
  linewidth=0.2, alpha=0.95)`.
- Nếu có `data/expected/<stem>.paths.json`: vẽ đè các đường tham chiếu màu
  `#c0392b`, mặc định bật, tắt bằng `--no-paths`.
- `--source N`: chấm cam đánh dấu đỉnh nguồn.
- Tiêu đề ghi số đỉnh/mặt; tỉ lệ hộp theo bounding box thật.

### 2. Tất cả

```bash
.venv/bin/python tools/data/data_viz.py --all
```

Quét `--input` (mặc định `data/processed/meshes`), mỗi `.off` một ảnh. Hiện có
10 ảnh (9 fixture + bề mặt thành phố).

### 3. So sánh trước/sau

```bash
.venv/bin/python tools/data/data_viz.py city.standardized.triangulation --scene
```

- Trái: scene chuẩn hoá (`Poly3DCollection`, xám `#7b8794`), đọc từ GLB.
- Phải: bề mặt tam giác phân (viridis).
- Hai bảng cùng giới hạn trục và cùng góc nhìn (`elev=30, azim=-58`).
- `--scene-triangles N` giới hạn số tam giác của scene (0 = tất cả); tiêu đề ghi
  `N of M triangles shown`.
- Ra `<tên>-compare.png`.

## Đầu ra

| Chế độ | Đường dẫn |
| --- | --- |
| Mesh | `generated/data_viz/<stem>.png` |
| So sánh | `generated/data_viz/<stem>-compare.png` |
| `--show` | Không ghi file |

Ảnh 150 dpi, `bbox_inches='tight'`, nền trắng. Kích thước điển hình
1000–1200 px, 200–450 KB.

## `--show`

Mở cửa sổ Matplotlib thay vì ghi file. Cần backend đồ hoạ; nếu không có,
tool dừng với thông báo (xem [`lib.md`](lib.md)) thay vì lặng lẽ dùng `Agg`.

## Ghi chú

- Tool **không** sửa mesh; chỉ đọc.
- Đường tham chiếu lấy từ `data/expected/`, không tính lại.
- Ảnh nằm trong `generated/data_viz/`, **không commit** (sinh lại được bằng
  `main.py data`).
