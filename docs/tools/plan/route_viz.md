# `route_viz.py`

| | |
| --- | --- |
| Stage | `plan` bước 2 |
| Vào | `generated/routes/*.routes.json` + mesh ghi trong file; bỏ qua `<tên>.png.json` (sidecar ảnh) và `summary.json` |
| Ra | `generated/routes/<mission>.routes.png` + `<mission>.png.json` (dấu tham số) |
| Cờ | `--routes` (lặp lại), `--input`, `--output`, `--max-routes N` (60), `--show` |

## Vì sao tách khỏi `run_funnel`

Vẽ lại không cần chạy lại Funnel: trên bề mặt thành phố, lập tuyến mất khoảng
60–80 s cho 3 goal (mission hiện tại), còn vẽ chỉ vài giây. Tách ra cũng giúp `run_funnel` không phụ thuộc Matplotlib
và chạy được trên máy không có cửa sổ.

## Nội dung ảnh

| Thành phần | Chi tiết |
| --- | --- |
| Bề mặt | `plot_trisurf`, cmap `viridis`, `alpha=0.5`, không viền |
| START | chấm tròn `#167a40`, 90 pt |
| Tuyến | mỗi tuyến một màu trong bảng 8 màu, linewidth 1.6 |
| Goal | ngôi sao cùng màu tuyến, 110 pt |
| Chú thích | chỉ khi ≤12 tuyến: `id — độ dài` |
| Tiêu đề | `<mission> — N route(s), T s` (T lấy từ `planning_seconds`) |
| Tỉ lệ | `set_box_aspect` theo bounding box thật của mesh |

## Đóng dấu tham số

| Ghi vào | Nội dung |
| --- | --- |
| Chân ảnh | `solve limit`, `max nodes`, `clipping`, `planning`, độ dài từng goal, tham số bay nếu đã dựng world, SHA ngắn, thời điểm |
| Metadata PNG | cùng nội dung, dạng `tEXt` |
| `<mission>.png.json` | tham số, facts, SHA của mesh/mission/module/route + SHA ảnh, dòng lệnh |

Nguồn:

- `generated/routes/<mission>.routes.json`: `solver.timeout_seconds`,
  `solver.max_nodes`, `solver.clipping`, `planning_seconds`, `mesh_sha256`,
  `mission_sha256`, `solver.module_sha256`, danh sách route + độ dài.
- `generated/simulate/<mission>-g*/world_metadata.json` nếu đã dựng world:
  `flight.speed`, `flight.max_acceleration`, `flight.dwell`,
  `flight.start_delay`, `simplify_tolerance`, `collision_stats.cell`.
  Chưa dựng world thì ảnh **không** ghi tốc độ, để không ai tưởng là 5 m/s.
  Nhiều goal có cấu hình bay khác nhau thì ghi `flight mixed`.

## `--max-routes`

Khi số tuyến lớn hơn ngưỡng, tool giữ các tuyến **dài nhất** (sắp xếp giảm dần
theo `length`). Với `terrain` (48 goal) dùng `--max-routes 12` cho ảnh dễ đọc.

## Đầu ra

```
generated/routes/cliff.routes.png      1069×1104, ~258 KB
generated/routes/city.standardized.triangulation.routes.png   1184×1101, ~380 KB
```

150 dpi, `bbox_inches='tight'`. Ảnh và sidecar **có commit** cùng JSON (kết quả
stage `plan`).

## `--show`

Mở cửa sổ 3D thay vì ghi PNG. Cần backend Tk/Qt/GTK; thiếu thì tool dừng với
thông báo nêu cách cài (xem [`lib.md`](../lib.md)). Trên NixOS có thể chạy qua
`steam-run` hoặc symlink `_tkinter` vào venv.

## Ví dụ

```bash
.venv/bin/python tools/plan/route_viz.py
.venv/bin/python tools/plan/route_viz.py --routes generated/routes/cliff.routes.json
.venv/bin/python tools/plan/route_viz.py --routes generated/routes/terrain.routes.json --max-routes 12
.venv/bin/python tools/plan/route_viz.py --output /tmp/routes
```
