# `compare_runs.py`

| | |
| --- | --- |
| Stage | Không nằm trong pipeline: dùng sau khi đã có ≥2 archive |
| Vào | `results/runs/<label>/manifest.json` |
| Ra | Bảng trên terminal, `results/comparison/comparison.md` + `.json`, ảnh `<label>-route.png`, `<label>-<goal>-tracking.png` |
| Cờ | `label...` (mặc định mọi archive, xếp theo tên), `--runs DIR`, `--output DIR` |

## Vì sao cần archive

Đổi `cell` từ 5 m sang 4 m làm bề mặt, route và kết quả bay đều khác, nhưng mọi
tool ghi vào cùng đường dẫn: `generated/routes/<mission>.routes.json`,
`generated/simulate/<mission>-g1/validation.json`, … Chạy lần thứ hai là mất số
liệu lần thứ nhất. Vì vậy `main.py --label` chép bộ kết quả sang
`results/runs/<label>/`, nơi không stage nào xoá.

## Cách dùng

```bash
# lần 1: cấu hình mặc định
python3 main.py --label grid5

# lần 2: trả lời cell = 4 ở câu hỏi triangulation
python3 main.py --label grid4

# bảng cho báo cáo
python3 tools/plan/compare_runs.py
```

Muốn lưu kết quả đang có mà không chạy lại:

```bash
python3 main.py --archive grid5-b
```

So sánh một tập con hoặc đổi chỗ ghi:

```bash
python3 tools/plan/compare_runs.py grid5 grid4 --output results/grid-comparison
```

## Bảng gồm gì

| Nhóm | Dòng |
| --- | --- |
| Danh tính | `commit`, `ghi lúc` |
| Hình học | `cell`, `clearance`, `half-width`, `max-slope`, `SHA bề mặt` |
| Solver | `solver (s)`, `max nodes`, `clipping`, `planning (s)` |
| Bay | `speed`, `max accel`, `dwell`, `start delay`, `simplify`, `collision grid` |
| Từng goal | `route gN (m)`, `waypoints gN`, `flight gN (s)`, `max error gN (m)`, `mean error gN (m)`, `mốc bám gN` |

Mỗi cột là một label. File Markdown dùng đúng bảng đó để chép vào báo cáo; JSON
giữ cùng số liệu cho script khác.

`mốc bám gN` là `passed` trong `validation.json`, tức lần bay có nằm trong mốc
chất lượng 1 m hay không — **không** phải điều kiện lần bay hợp lệ. Một lần bay
có thể `mốc bám = trượt` mà vẫn hợp lệ (hết tuyến, dừng đúng đích), và khi đó
cột `max error` / `mean error` mới là số cần trích; xem
[`../simulate/validate.md`](../simulate/validate.md).

## Nguồn từng dòng

`manifest.json` chỉ ghi những nhóm tham số mà lần chạy đó **thực sự hỏi** (chạy
riêng `simulate` thì không có `triangulation`). Tool gộp thêm từ các file đã lưu
trong archive:

| Dòng | Nguồn |
| --- | --- |
| `cell`, `clearance`, `half-width`, `max-slope` | `parameters.triangulation`, thiếu thì `surface.params.json` |
| `solver (s)`, `max nodes`, `clipping` | `parameters.solver`, thiếu thì `routes.solver` trong route JSON |
| `speed`, `accel`, `dwell`, `delay` | `parameters.flight`, thiếu thì `flight_parameters` (đọc từ `world_metadata.json`) |
| `simplify` | `parameters.world.simplify`, thiếu thì `simplify_tolerance` |
| độ dài/waypoint, thời lượng, sai số | `routes` và `flight` trong manifest |

Không có giá trị nào được suy ra từ mặc định của tool: thiếu thì in `—`.

## Ảnh cạnh bảng

Mỗi archive có ảnh tuyến (`routes.png`; archive cũ dùng `route.png`) và
`gN/tracking.png`. Tool chép ra:

```text
results/comparison/grid5-route.png
results/comparison/grid5-g1-tracking.png
results/comparison/grid4-g1-tracking.png
```

Tên file mang label nên hai lần chạy không thể lẫn ảnh. Ảnh giữ nguyên chân
tham số do `figstamp` vẽ, nên mở ảnh vẫn đọc được cấu hình.

## Cách đọc và giới hạn

- **Đổi `cell` là đổi bề mặt**: `SHA bề mặt` khác nhau thì độ dài route khác
  nhau vừa do lưới vừa do hình học; muốn kết luận về thuật toán thì so route
  trên cùng SHA.
- `cell` 4 m làm `plan` chậm hơn nhiều: lần đo trước cho g1 khoảng 107 s và g2
  vượt 300 s. Muốn so đủ ba goal thì trả lời `thời gian tối đa mỗi goal` = 600
  ở lần chạy cell 4, nếu không `g2` sẽ hết giờ giữa lúc lập tuyến (không có
  route để bay), khác hẳn với `mốc bám = trượt` của một lần bay đã hoàn tất.
- Archive ghi `created_at` và ảnh có thời điểm, nên hai lần chạy cùng tham số
  vẫn khác byte ảnh. So sánh bằng tham số + SHA, không bằng hash ảnh.
- Tool không chạy lại gì và không sửa archive; chỉ đọc và chép ảnh.
