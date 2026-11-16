# `route_viz.py`

| | |
| --- | --- |
| Stage | `plan` bước 2 |
| Vào | `generated/routes/*.json` + mesh ghi trong file |
| Ra | `generated/routes/<mission>.png` |
| Cờ | `--routes` (lặp lại), `--input`, `--output`, `--max-routes N` (60), `--show` |

## Vì sao tách khỏi `run_funnel`

Vẽ lại không cần chạy lại Funnel: trên bề mặt thành phố, lập tuyến mất ~190 s,
còn vẽ chỉ vài giây. Tách ra cũng giúp `run_funnel` không phụ thuộc Matplotlib
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

## `--max-routes`

Khi số tuyến lớn hơn ngưỡng, tool giữ các tuyến **dài nhất** (sắp xếp giảm dần
theo `length`). Với `terrain` (48 goal) dùng `--max-routes 12` cho ảnh dễ đọc.

## Đầu ra

```
generated/routes/cliff.png      1069×1104, ~258 KB
generated/routes/city.standardized.triangulation.png   1184×1101, ~380 KB
```

150 dpi, `bbox_inches='tight'`. Ảnh **có commit** cùng JSON (kết quả stage `plan`).

## `--show`

Mở cửa sổ 3D thay vì ghi PNG. Cần backend Tk/Qt/GTK; thiếu thì tool dừng với
thông báo nêu cách cài (xem [`lib.md`](lib.md)). Trên NixOS có thể chạy qua
`steam-run` hoặc symlink `_tkinter` vào venv.

## Ví dụ

```bash
.venv/bin/python tools/plan/route_viz.py
.venv/bin/python tools/plan/route_viz.py --routes generated/routes/cliff.json
.venv/bin/python tools/plan/route_viz.py --routes generated/routes/terrain.json --max-routes 12
.venv/bin/python tools/plan/route_viz.py --output /tmp/routes
```
