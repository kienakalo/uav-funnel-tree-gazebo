# `figures.py`

| | |
| --- | --- |
| Stage | Không nằm trong pipeline: kiểm tra ảnh trước khi dán vào báo cáo |
| Vào | `*.png` trong `generated/` (mặc định) + sidecar `<tên>.png.json` + metadata PNG |
| Ra | Bảng trên terminal; `--json PATH` ghi bảng tổng hợp |
| Cờ | `--folder DIR` (lặp lại), `--json PATH`, `--no-fail` |
| Mã thoát | 1 khi có ảnh thiếu sidecar, SHA lệch, metadata khác sidecar, hoặc sidecar mồ côi |

## Vì sao cần

Một run sinh hàng chục ảnh: fixture, bề mặt, bản xem thành phố, route và
`tracking.png` cho từng goal. Tên file được dùng lại khi `cell`, `clearance`
hay tốc độ đổi, nên nhìn ảnh không biết nó thuộc cấu hình nào. Mỗi ảnh đã được
`lib/figstamp.py` đóng dấu ở ba chỗ; tool này đọc lại cả ba và đối chiếu.

## Cách dùng

```bash
.venv/bin/python tools/figures.py
.venv/bin/python tools/figures.py --folder generated/routes
.venv/bin/python tools/figures.py --json generated/figures.json
```

```text
generated/data_viz/city.standardized.triangulation.png
    cell=5.0 · coverage=city · vertical_clearance=1.5 · horizontal_half_width=1.6 · max_axis_slope=0.5 · expected paths=Y · vertices=2295 · triangles=4400
    2026-11-17 18:24 · ok
generated/simulate/city.standardized.triangulation-g1/tracking.png
    speed=5.0 · max_acceleration=3.0 · dwell=0.0 · start_delay=2.0 · simplify=0.1 · collision_grid=1.0 · max_error_limit=1.0 · goal=g1 · rows=341 · …
    2026-11-17 18:45 · ok
```

## Kiểm tra gì

| Kiểm tra | Khi nào báo lỗi |
| --- | --- |
| `thiếu sidecar` | PNG có nhưng `<tên>.png.json` không có |
| `SHA ảnh lệch` | `image_sha256` trong sidecar khác SHA của file, tức ảnh đã bị ghi đè |
| `sidecar trỏ ảnh khác` | Trường `image` không cùng tên file |
| `thiếu metadata PNG` | Ảnh không có chunk `tEXt`/`zTXt`/`iTXt` |
| `metadata PNG khác sidecar` | Hai bản ghi không cùng tham số |
| `sidecar mồ côi` | Có `<tên>.png.json` nhưng không có PNG |

Ba nguồn lệch nhau thường có nghĩa ảnh được chép tay hoặc bị ghi đè bởi tool
khác — đúng loại lỗi cần phát hiện trước khi trích ảnh vào báo cáo.

## Metadata PNG đọc bằng stdlib

Không cần Pillow: tool tự đọc chunk PNG (header 8 byte, mỗi chunk `size` +
`type` + `data` + CRC) và xử lý `tEXt` (latin-1), `zTXt` (zlib + latin-1),
`iTXt` (UTF-8, có thể nén). Matplotlib ghi các khóa `Software`, `Title`,
`Description`, `Parameters`, `Sources`, `Generated`.

## Liên quan

- [`lib/figstamp.py`](lib.md) — nơi ghi dấu.
- [`data_viz.md`](data/data_viz.md), [`route_viz.md`](plan/route_viz.md),
  [`validate.md`](simulate/validate.md) — ba nơi gọi.
- [`compare_runs.md`](plan/compare_runs.md) — so sánh số liệu giữa các lần chạy.
