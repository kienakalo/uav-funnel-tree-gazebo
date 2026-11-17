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
- `--label`/`--archive` **không ghi đè**: label đã tồn tại thì tool dừng.
- `--fresh` và mọi stage đều không xoá `results/`.
- `comparison/` sinh lại được từ `runs/`, nên có thể bỏ và tạo lại bất cứ lúc nào.

Đọc và so sánh:

```bash
python3 main.py --archive cell5
python3 tools/plan/compare_runs.py          # bảng mọi archive, xếp theo tên
```

Chi tiết: [`../docs/tools/main.md`](../docs/tools/main.md) (mục *Lưu một lần chạy
để so sánh*) và [`../docs/tools/plan/compare_runs.md`](../docs/tools/plan/compare_runs.md).
