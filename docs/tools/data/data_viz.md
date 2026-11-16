# `data_viz.py`

| | |
| --- | --- |
| Stage | `data` bước 5 |
| Vào | `.off` trong `data/processed/meshes/` (mặc định) |
| Ra | `generated/data_viz/<tên>.png` hoặc cửa sổ 3D |
| Cờ | `--all`, `--input`, `--output`, `--source N`, `--no-paths`, `--show` |
| Cần | NumPy, Matplotlib |

## Hai chế độ

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

Quét `--input` (mặc định `data/processed/meshes`), mỗi `.off` một ảnh.

## Đầu ra

| Chế độ | Đường dẫn |
| --- | --- |
| Mesh | `generated/data_viz/<stem>.png` |
| `--show` | Không ghi file |

Ảnh 150 dpi, `bbox_inches='tight'`, nền trắng. Kích thước điển hình
1000–1200 px, 200–450 KB.

## `--show`

Mở cửa sổ Matplotlib thay vì ghi file. Cần backend đồ hoạ; nếu không có, tool
dừng với thông báo (xem [`lib.md`](../lib.md)) thay vì lặng lẽ dùng `Agg`.

## Ghi chú

- Tool **không** sửa mesh; chỉ đọc.
- Đường tham chiếu lấy từ `data/expected/`, không tính lại.
- So sánh trước/sau (scene chuẩn hoá với bề mặt) **không** còn trong tool này;
  muốn xem scene thì mở GLB bằng Blender/MeshLab.
- Ảnh nằm trong `generated/data_viz/` và hiện được commit cùng kết quả stage.
