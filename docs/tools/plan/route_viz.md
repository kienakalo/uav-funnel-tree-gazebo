---
title: route_viz.py
aliases:
  - route_viz
type: tool
stage: plan
source: tools/plan/route_viz.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/plan
---

# `route_viz.py`

> [!abstract] Mục đích
> Vẽ các route đã lập thành PNG (hoặc cửa sổ 3D), tách khỏi bước giải để có
> thể xem lại mà không tốn thời gian chạy Funnel và không cần Matplotlib trong
> `run_funnel`.

> [!info] Vị trí
> **File** `tools/plan/route_viz.py` — stage `plan`, bước 2  
> **Thuật toán** Vẽ `plot_trisurf` + polyline mỗi tuyến, giới hạn theo độ dài, đóng dấu tham số solver  
> **Vào** `generated/routes/*.routes.json` + mesh ghi trong file; bỏ qua `<tên>.routes.png.json` (sidecar ảnh) và `summary.json`  
> **Ra** `generated/routes/<mission>.routes.png` + `<mission>.routes.png.json` (dấu tham số)  
> **Cờ** `--routes` (lặp lại), `--input`, `--output`, `--max-routes N` (60), `--show`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `mission_of(path)` | đường dẫn route | stem | `cliff.routes.json → cliff`; bỏ qua sidecar và `summary.json` |
| `flight_settings(mission)` | tên mission | `dict` tham số bay hoặc trạng thái `mixed` | Đọc `world_metadata.json` của các goal đã dựng world; chưa dựng thì trả rỗng để ảnh không ghi tốc độ |
| `stamp_data(path, record, shown, limit)` | route + danh sách tuyến đã vẽ | `(parameters, facts)` | Gom tham số solver, độ dài từng goal, SHA để đóng dấu |
| `render(path, output, limit, show)` | một route JSON, đích, giới hạn | ghi PNG hoặc mở cửa sổ | Vẽ `plot_trisurf` + tuyến + START/GOAL, gọi `figstamp.save` |
| `main()` | `--routes`, `--input`, `--output`, `--max-routes`, `--show` | ảnh + sidecar | Chọn tuyến dài nhất khi vượt `--max-routes` |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy, Matplotlib | Dựng mặt và vẽ tuyến |
| Nội bộ | `lib/mesh_off.py: read_off` | Đọc bề mặt để làm nền |
| Nội bộ | `lib/figstamp.py: save` | Chân ảnh, metadata PNG, sidecar |
| Nội bộ | `lib/plotting.py: use_interactive, unavailable_message` | Backend cho `--show` |
| Dữ liệu | `generated/routes/*.routes.json`, `generated/simulate/*/world_metadata.json` | Tuyến và tham số bay (nếu có) |

## Vì sao tách khỏi `run_funnel`

Vẽ lại không cần chạy lại Funnel: trên bề mặt thành phố, lập tuyến mất khoảng
45–62 s cho 3 goal (mission hiện tại), còn vẽ chỉ vài giây. Tách ra cũng giúp `run_funnel` không phụ thuộc Matplotlib
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
| `<mission>.routes.png.json` | tham số, facts, SHA của mesh/mission/module/route + SHA ảnh, dòng lệnh |

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

## Liên quan

- [`run_funnel.md`](run_funnel.md) — sinh file route mà bước này đọc.
- [`../figures.md`](../figures.md) — kiểm tra dấu tham số của ảnh.
- [`../lib.md`](../lib.md) — `figstamp` và `plotting`.
- [`../simulate/build_world.md`](../simulate/build_world.md) — nguồn `world_metadata.json`.
