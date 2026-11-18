---
title: validate.py
aliases:
  - validate
type: tool
stage: simulate
source: tools/simulate/validate.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/simulate
---

# `tools/simulate/validate.py`

> [!abstract] Mục đích
> Chấm một lần bay từ telemetry: tách **hợp lệ** (hết tuyến, dừng đúng đích)
> khỏi **đạt mốc chất lượng** (bám tuyến trong 1 m), rồi ghi `validation.json` và
> `tracking.png`.

> [!info] Vị trí
> **File** `tools/simulate/validate.py` — stage `simulate`, bước cuối  
> **Thuật toán** Thống kê cột `error` và `phase` của telemetry; `valid` tách khỏi `passed`  
> **Vào** `generated/simulate/<mission>-<goal>/physics_telemetry.csv` + `telemetry_metadata.json` + `world_metadata.json` + `flown_route.json`  
> **Ra** `validation.json`, `tracking.png` + `tracking.png.json` (dấu tham số) trong cùng thư mục  
> **Cờ** `--run DIR`, `--root DIR`, `--mission`, `--goal`, `--max-error M`, `--arrival-tolerance M`, `--no-png`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `run_folder(args)` | `--run` hoặc root + mission + goal | `Path` thư mục run | Xác định thư mục cần chấm |
| `relative(path)` | đường dẫn | đường dẫn gọn | Bỏ tiền tố repo khi ghi `validation.json` và chân ảnh |
| `read_rows(path)` | CSV telemetry | danh sách dòng đã đổi kiểu | Đọc 16 cột do plugin ghi |
| `analyse(rows, max_error)` | dòng + mốc | `dict` kết quả | Tính `completed`, `duration`, `final_error`, `max_error`, `mean_error`, `max_speed`, `max_acceleration`, `valid`, `passed` |
| `render(rows, folder, title, limit, metadata, result)` | telemetry + metadata | `tracking.png` + sidecar | Vẽ mặt bằng tuyến và sai số theo thời gian |
| `stamp_data(metadata, result, limit)` | metadata + kết quả | `(parameters, facts, sources)` | Gom tham số bay và số đo để đóng dấu |
| `main()` | cờ dòng lệnh | JSON + PNG; thoát 1 nếu không hợp lệ | Đọc, chấm, ghi, in lý do khi fail |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | Matplotlib; `argparse`, `csv`, `hashlib`, `json`, `math` | Vẽ và đọc telemetry |
| Nội bộ | `lib/figstamp.py: save` | Chân ảnh, metadata PNG, sidecar |
| Dữ liệu | `physics_telemetry.csv`, `telemetry_metadata.json` | Số đo của phiên |
| Dữ liệu | `world_metadata.json`, `flown_route.json` | Tham số bay và tuyến để vẽ; archive cũ dùng `route.json` |

`flown_route.json` chỉ dùng để vẽ tuyến trong `tracking.png`. Thư mục của archive
lưu trước 18/11/2026 còn tên cũ `route.json`; tool đọc tên đó khi không có
`flown_route.json`.

## Chỉ số

| Chỉ số | Cách tính |
| --- | --- |
| `rows` | Số dòng telemetry |
| `completed` | `phase` của dòng cuối = `complete` |
| `duration` | `sim_time` cuối − đầu |
| `final_error` | Cột `error` của dòng cuối (drone dừng cách đích bao xa) |
| `max_error`, `mean_error` | Cột `error` do plugin ghi |
| `max_speed` | `max ‖(vx, vy, vz)‖` |
| `max_acceleration` | Hiệu vận tốc giữa hai dòng liên tiếp chia `Δt` |

## Hai câu hỏi, hai tiêu chí

```
valid  = completed AND final_error <= --arrival-tolerance  (mặc định 0,5 m)
passed = valid     AND max_error   <= --max-error           (mặc định 1,0 m)
```

| | `valid` | `passed` |
| --- | --- | --- |
| Trả lời | lần bay có chạy đúng không: hết tuyến và dừng ở đích | bám tuyến có chặt không |
| Dùng để | `main.py` dừng stage (exit 1) | nhãn "đạt mốc" trong bảng so sánh, manifest archive |
| Không đạt | ghi file xong **thoát mã 1** | chỉ in cảnh báo, **exit 0**, stage chạy tiếp |

### Vì sao phải tách

Một lần bay hỏng (telemetry cụt, drone không tới đích) phải chặn pipeline. Một
lần bay đúng tuyến nhưng trễ 0,2 s ở một góc cua thì không: đó là số đo để báo
cáo, không phải lỗi. Gộp cả hai vào `passed` khiến g2 của mission hiện tại bị
xếp "trượt" dù bay đúng và về đích, và khiến `main.py simulate` dừng giữa bộ ba
goal.

### Mốc 1 m nghĩa là gì

`--max-error` là **mốc chất lượng của nghiên cứu**, không phải giới hạn vật lý.
Nó không lấy từ repo cũ: repo cũ báo `max_tracking_error ≈ 2,4 mm`, nhưng đó là
sai số tái dựng route offline, khác đại lượng với sai số bám setpoint động.
Với cấu hình hiện tại, 1 m tương đương:

| So với | Giá trị |
| --- | --- |
| cạnh ô lưới envelope (5 m) | 1 m = 20 % một ô |
| `vertical_clearance` (1,5 m) | 1 m = 2/3 khe hở an toàn |
| tốc độ bay (5 m/s) | 1 m = 0,2 s trễ |

Vì vậy khi báo cáo nên nêu **số đo** (`max_error`, `mean_error`) kèm mốc, và
không đổi mốc sau khi đã nhìn thấy kết quả.

## `tracking.png`

Hai panel:

1. **Nhìn từ trên**: tuyến kế hoạch (cam, chấm vàng ở waypoint, xanh ở start,
   hồng ở goal) và **đường đã bay** (tím) lấy từ cột `x, y` của telemetry.
2. **Sai số theo thời gian** kèm đường mốc `--max-error` (nét đứt, chỉ để tham
   chiếu: vượt mốc không làm lần bay thành không hợp lệ).

Panel 1 trả lời câu "drone có đi đúng tuyến không"; panel 2 trả lời "bám sát
đến mức nào". Ảnh là hình vẽ từ CSV, không phải ảnh chụp cửa sổ Gazebo.

### Đóng dấu tham số

| Ghi vào | Nội dung |
| --- | --- |
| Chân ảnh | `speed`, `accel`, `dwell`, `delay`, `simplify`, `collision grid`, `error limit`, `goal`, số dòng, thời lượng, `max error`, `mean`, `completed`, SHA ngắn, thời điểm |
| Metadata PNG | cùng nội dung, dạng `tEXt` |
| `tracking.png.json` | tham số, facts, SHA của scene/bề mặt/route/telemetry + SHA ảnh, dòng lệnh |

Tham số bay đọc từ `world_metadata.json` (không phải `telemetry_metadata.json`,
file đó chỉ có mission/goal/run id). Nhờ vậy ảnh bay ở 5 m/s và ở 2 m/s phân
biệt được dù cùng tên `tracking.png`.

## `validation.json`

Ví dụ của g2 (mission START 792): hợp lệ nhưng trượt mốc chất lượng.

```json
{
  "rows": 331,
  "completed": true,
  "duration": 33.245,
  "max_error": 1.0224,
  "mean_error": 0.1101,
  "final_error": 0.0,
  "max_speed": 5.0413,
  "max_acceleration": 7.9832,
  "max_error_limit": 1.0,
  "mission": "data/processed/missions/city.standardized.triangulation.mission.json",
  "goal": "g2",
  "world": "funnel_sim_city_standardized_triangulation_g2",
  "route_sha256": "…",
  "run_id": "20261117_220538-67475",
  "nominal_duration": 29.225898101487356,
  "telemetry": "generated/simulate/.../physics_telemetry.csv",
  "telemetry_sha256": "…",
  "arrival_tolerance": 0.5,
  "valid": true,
  "passed": false
}
```

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

| Đầu vào | Kết quả |
| --- | --- |
| g1 thật (357 dòng, `max_error` 0,365 m) | `valid: true`, `passed: true`, exit 0 |
| g2 thật (330 dòng, 1,022 m) | `valid: true`, `passed: false`, exit 0 + cảnh báo mốc |
| g3 thật (249 dòng, 0,852 m) | `valid: true`, `passed: true`, exit 0 |
| g1 cắt còn 120 dòng đầu (dòng cuối `moving`) | `valid: false`, exit 1, lý do *last row is not in the complete phase* |

## Liên quan

- [`plugin.md`](plugin.md) — nguồn của cột `error` và `phase`.
- [`build_world.md`](build_world.md) — `world_metadata.json` chứa tham số bay.
- [`../main.md`](../main.md) — stage dừng khi `valid: false`.
- [`../plan/compare_runs.md`](../plan/compare_runs.md) — cột `mốc bám` lấy từ `passed`.
