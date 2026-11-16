# `tools/simulate/validate.py`

| | |
| --- | --- |
| Stage | `simulate` (bước cuối) |
| Vào | `generated/simulate/<mission>-<goal>/physics_telemetry.csv` + `telemetry_metadata.json` |
| Ra | `validation.json`, `tracking.png` trong cùng thư mục |
| Cờ | `--run DIR`, `--root DIR`, `--mission`, `--goal`, `--max-error M`, `--no-png` |

## Chỉ số

| Chỉ số | Cách tính |
| --- | --- |
| `rows` | Số dòng telemetry |
| `completed` | `phase` của dòng cuối = `complete` |
| `duration` | `sim_time` cuối − đầu |
| `max_error`, `mean_error` | Cột `error` do plugin ghi |
| `max_speed` | `max ‖(vx, vy, vz)‖` |
| `max_acceleration` | Hiệu vận tốc giữa hai dòng liên tiếp chia `Δt` |

## Điều kiện đạt

```
passed = completed AND max_error <= --max-error (mặc định 1,0 m)
```

Không đạt thì ghi file xong **thoát mã 1**, để `main.py simulate` dừng ở bước này.

## `validation.json`

```json
{
  "rows": 920,
  "completed": true,
  "duration": 91.8,
  "max_error": 0.42,
  "mean_error": 0.11,
  "max_speed": 5.0,
  "max_acceleration": 3.0,
  "max_error_limit": 1.0,
  "mission": "data/processed/missions/....json",
  "goal": "g1",
  "world": "funnel_sim_..._g1",
  "route_sha256": "…",
  "run_id": "20261116_193000-1234",
  "nominal_duration": 94.1,
  "telemetry": "generated/simulate/.../physics_telemetry.csv",
  "telemetry_sha256": "…",
  "passed": true
}
```

## `tracking.png`

Một đồ thị: `error` theo thời gian mô phỏng, kèm đường ngưỡng `--max-error`.
Dùng để thấy nhanh drone bám tuyến từ đầu đến cuối hay lệch ở đoạn nào.

## Ví dụ

```bash
.venv/bin/python tools/simulate/validate.py --mission city.standardized.triangulation --goal g1
.venv/bin/python tools/simulate/validate.py --run generated/simulate/cliff-v3 --max-error 0.5
.venv/bin/python tools/simulate/validate.py --goal g2 --no-png
```

## Ghi chú

- Không kiểm vật lý hay va chạm; chỉ đo bám tuyến từ telemetry.
- `nominal_duration` lấy từ metadata để so với `duration` thực tế.
- `run_id` trong kết quả là của phiên vừa chạy, nên mỗi lần chạy làm file dirty.

## Kiểm tra tại chỗ (đã chạy)

| Đầu vào tổng hợp | Kết quả |
| --- | --- |
| 20 dòng, error giảm 0,30 → 0, `complete` | `passed: true`, exit 0 |
| 20 dòng, error = 2,0, không `complete` | `passed: false`, exit 1 |
