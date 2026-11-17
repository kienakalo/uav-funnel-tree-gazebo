# Kết quả lưu theo lần chạy

Thư mục này **không phải** output của pipeline. `generated/` là kết quả của lần
chạy gần nhất; `results/` giữ số liệu của một lần chạy đã xong, để so sánh giữa
các cấu hình sau khi `generated/` bị ghi đè.

| Mục | Ai ghi | Vì sao giữ |
| --- | --- | --- |
| `runs/<label>/manifest.json` | `main.py --label` / `--archive` | Tham số + nguồn, commit, SHA scene/bề mặt/route, START/GOAL đã snap, độ dài route, thời lượng bay, `max_error`, danh sách file kèm SHA |
| `runs/<label>/parameters.json` | như trên | Bản sao `generated/parameters.json` của lần chạy đó (file gốc bị ghi đè mỗi run) |
| `runs/<label>/surface.params.json` | như trên | Tham số + SHA của bề mặt đã dùng, để biết hai archive có cùng hình học hay không |
| `runs/<label>/mission.json`, `route.json`, `route.png` | như trên | Mission, route đã lập và ảnh tuyến; ảnh có chân ghi tham số |
| `runs/<label>/gN/` | như trên | `validation.json`, `world_metadata.json`, quỹ đạo bay, `tracking.png` + sidecar, `telemetry_metadata.json` của từng goal |
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
- `--fresh` và mọi stage đều không xoá `results/`.
- `comparison/` sinh lại được từ `runs/`, nên có thể bỏ và tạo lại bất cứ lúc nào.

## Các archive đang có

| Label | Mission | Nội dung |
| --- | --- | --- |
| `cell5` | START 182 (−100, −95) → g1 1275, g2 2112, g3 1147 | bay 34,2 s / 64,6 s / 35,6 s; `max_error` 0,820 / 0,989 / 0,971 m |
| `cell5b` | như trên, chạy lại `main.py --force` | bay 34,5 s / 64,3 s / 35,4 s; cùng sai số — dùng để nói độ lặp lại |
| `city792` | START 792 (−38,75, 22,10) → g1 1810, g2 1910, g3 1518 | bay 35,4 s / 33,2 s / 24,6 s; `max_error` 0,365 / 1,022 / 0,851 m; cả ba `valid`, g2 trượt mốc 1 m 2 % tại một góc cua |

Mission hiện tại của thành phố là START 792 → 1810 / 1910 / 1518 (xem
[`../docs/tools/data/set_start_goal.md`](../docs/tools/data/set_start_goal.md));
`city792` là archive của nó.

Đọc và so sánh:

```bash
python3 main.py --archive cell5
python3 tools/plan/compare_runs.py          # bảng mọi archive, xếp theo tên
```

Chi tiết: [`../docs/tools/main.md`](../docs/tools/main.md) (mục *Lưu một lần chạy
để so sánh*) và [`../docs/tools/plan/compare_runs.md`](../docs/tools/plan/compare_runs.md).
