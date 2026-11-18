# Kết quả lưu theo lần chạy

Thư mục này **không phải** output của pipeline. `generated/` là kết quả của lần
chạy gần nhất; `results/` giữ số liệu của một lần chạy đã xong, để so sánh giữa
các cấu hình sau khi `generated/` bị ghi đè.

| Mục | Ai ghi | Vì sao giữ |
| --- | --- | --- |
| `runs/<label>/manifest.json` | `main.py --label` / `--archive` | Tham số + nguồn, `commit` (HEAD lúc lưu), SHA scene/bề mặt/route, START/GOAL đã snap, độ dài route, thời lượng bay, `max_error`, `mean_error`, `valid`, `passed`, danh sách file kèm SHA |
| `runs/<label>/parameters.json` | như trên | Bản sao `generated/parameters.json` của lần `main.py` **cuối cùng** (file gốc bị ghi đè mỗi run) |
| `runs/<label>/surface.params.json` | như trên | Tham số + SHA của bề mặt đã dùng, để biết hai archive có cùng hình học hay không |
| `runs/<label>/mission.json`, `routes.json`, `routes.png` | như trên | Mission, route đã lập và ảnh tuyến; ảnh có chân ghi tham số |
| `runs/<label>/gN/` | như trên | `validation.json`, `world_metadata.json`, `flown_route.json` (tuyến đã rút gọn mà plugin bay), `tracking.png` + sidecar, `telemetry_metadata.json` của từng goal |
| `comparison/` | `tools/plan/compare_runs.py` | Bảng Markdown + JSON và ảnh của các lần chạy, tên file mang label |

Quy ước:

- Một archive là **bằng chứng đã chạy**, không sinh lại tay. Không sửa file
  trong `runs/`; muốn cấu hình khác thì chạy lại với label mới.
- Archive chụp **toàn bộ kết quả đang có** tại thời điểm lưu, không chỉ phần
  stage vừa chạy: `manifest.json` ghi `stages` của lần chạy và liệt kê `missing`
  nếu thiếu file. Muốn bảng so sánh đầy đủ thì chạy cả ba stage trước khi lưu.
- Tạo bằng `--archive` (không chạy gì) thì `stages` trong manifest rỗng; lần chạy
  đã sinh ra kết quả nằm trong `parameters.json` của chính archive (`command`,
  `stages`, tham số, nguồn).
- `--label`/`--archive` **không ghi đè**: label đã tồn tại thì tool dừng.
- `commit` trong `manifest.json` là `HEAD` **lúc lưu**, không phải lúc bay; với
  archive tạo bằng `--archive` thì còn cách xa hơn. Đừng suy commit sinh ra số
  liệu từ trường này; dùng `route_sha256`/`telemetry_sha256` trong
  `validation.json`.
- Chỉ lần chạy cuối được giữ archive. Các archive của cấu hình cũ (lưới 5 m với
  mission START 182) đã bỏ khỏi repo; muốn dựng lại một cấu hình để so sánh thì
  chạy `main.py --label <tên>` rồi so bằng `compare_runs.py`.
- `--fresh` và mọi stage đều không xoá `results/`.
- Bản backup telemetry của lần bay trước (`physics_telemetry_<timestamp>.csv`,
  `telemetry_metadata_<timestamp>.json`) chỉ nằm trên máy và đã ignore; bằng
  chứng của lần đang dùng là file không timestamp và bản trong archive.
  `comparison/` cũng ignore vì sinh lại được.
- `gN/` **không** chứa `physics_telemetry.csv` và `gazebo.log`; archive chỉ giữ
  `telemetry_sha256` trong `validation.json`. Hai file gốc nằm ở
  `generated/simulate/<mission>-<goal>/` (đã commit) và sẽ bị ghi đè hoặc xoá ở
  lần chạy sau, nên archive không tự kiểm lại được telemetry một khi `generated/`
  đổi. Muốn kiểm ngay thì so SHA với file gốc trước lần chạy kế tiếp.
- `comparison/` sinh lại được từ `runs/`, nên có thể bỏ và tạo lại bất cứ lúc nào.

## Các archive đang có

| Label | Mission | Nội dung |
| --- | --- | --- |
| `city792e` | START 792 (−38,75, 22,10) → g1 1810, g2 1910, g3 1518 | bay 35,9 s / 33,1 s / 25,0 s; `max_error` 0,365 / 1,022 / 0,852 m; `mean_error` 0,067 / 0,111 / 0,089 m; cả ba `valid`, g2 trượt mốc 1 m 2 % |

Mission hiện tại của thành phố là START 792 → 1810 / 1910 / 1518 (xem
[`../docs/tools/data/set_start_goal.md`](../docs/tools/data/set_start_goal.md));
`city792e` là archive của nó.

Cấu hình hiện tại --- 15 tham số của `data`, `plan` và `simulate` --- được
đánh dấu bằng tag
`cell5-clearance1.5-halfwidth1.6-slope0.5-coveragecity-solver300-maxnodes200000-clipping-simplify0.1-collisiongrid1-speed5-accel3-dwell0-delay2-timeout900-maxerror1`;
`git show <tag>` in lại bảng tham số và kết quả của lần chạy đó.

Đọc và so sánh:

```bash
python3 tools/plan/compare_runs.py          # bảng mọi archive, xếp theo tên
```

Chi tiết: [`../docs/tools/main.md`](../docs/tools/main.md) (mục *Lưu một lần chạy
để so sánh*) và [`../docs/tools/plan/compare_runs.md`](../docs/tools/plan/compare_runs.md).
