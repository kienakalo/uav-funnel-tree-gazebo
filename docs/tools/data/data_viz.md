# `data_viz.py`

| | |
| --- | --- |
| Stage | `data` bước 6 |
| Vào | `.off` trong `data/processed/meshes/` (mặc định) + `<mesh>.params.json` nếu có |
| Ra | `generated/data_viz/<tên>.png` + `<tên>.png.json` (dấu tham số) hoặc cửa sổ 3D |
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
1000–1200 px, 200–450 KB (cộng thêm dải chân 2–3 dòng).

## Đóng dấu tham số

Mỗi ảnh tự nói nó được sinh từ cấu hình nào (xem
[`lib/figstamp.py`](../lib.md) và [`figures.py`](../figures.md)):

| Ghi vào | Nội dung |
| --- | --- |
| Chân ảnh | tham số của mesh + số đỉnh/mặt + SHA ngắn + thời điểm |
| Metadata PNG | cùng nội dung, dạng `tEXt` đọc được bằng máy |
| `<tên>.png.json` | tham số, facts, SHA của mesh/scene/bề mặt/ảnh, tên + SHA script, dòng lệnh |

Tham số hình học đọc từ sidecar `<mesh>.params.json` do `triangulation.py` hoặc
`glb2off.py` ghi:

- `city.standardized.triangulation.off` → `cell`, `clearance`, `half-width`,
  `max-slope`, SHA scene;
- `city.standardized.glb2off.off` → `width` (200 m), SHA scene;
- fixture (`J17.off`, ...) không có sidecar → chỉ `expected paths` và số
  đỉnh/mặt, không bịa tham số hình học.

Dòng tham số vẽ thêm khi render cũng được ghi: `expected paths`, `source`. Nhờ
vậy hai ảnh cùng tên ở hai lần chạy khác cấu hình không thể bị dán nhầm vào báo
cáo.

## `--show`

Mở cửa sổ Matplotlib thay vì ghi file. Cần backend đồ hoạ; nếu không có, tool
dừng với thông báo (xem [`lib.md`](../lib.md)) thay vì lặng lẽ dùng `Agg`.

## Ghi chú

- Tool **không** sửa mesh; chỉ đọc.
- Đường tham chiếu lấy từ `data/expected/`, không tính lại.
- So sánh trước/sau (scene chuẩn hoá với bề mặt) **không** còn trong tool này;
  muốn xem scene thì mở GLB bằng Blender/MeshLab.
- Ảnh nằm trong `generated/data_viz/` và hiện được commit cùng kết quả stage.
