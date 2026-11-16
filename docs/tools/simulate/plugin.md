# `plugin/` — bộ điều khiển bay

| | |
| --- | --- |
| Stage | `simulate` bước 2 |
| File | `tools/simulate/plugin/trajectory.py`, `funnel_drone_system.py` |
| Chạy trong | tiến trình Gazebo, system Python 3.12 có `gz.sim10` |
| Vào | `route.json` (qua `FUNNEL_ROUTE`) |
| Ra | `physics_telemetry.csv`, `telemetry_metadata.json` (trong `FUNNEL_OUTPUT_DIR`) |

## Vai trò

World ở bước 1 chỉ có một hộp 1 kg. Plugin này là **phi công**: đọc tuyến, biến
nó thành kế hoạch theo thời gian, và mỗi bước vật lý đẩy hộp bằng lực để bám
theo kế hoạch.

## Biến môi trường

| Biến | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `FUNNEL_ROUTE` | Có | Đường dẫn tuyệt đối tới `route.json` |
| `FUNNEL_OUTPUT_DIR` | Có | Thư mục ghi CSV + metadata; tạo nếu chưa có |
| `FUNNEL_RUN_ID` | Không | Định danh phiên, ghi vào metadata |

Thiếu biến bắt buộc → `ValueError` ngay trong `configure`; Gazebo ghi lỗi vào log.

## `trajectory.py`

Chia polyline thành từng đoạn, mỗi đoạn bay từ **đứng yên → đứng yên**:

```
s(u)   = 10u³ − 15u⁴ + 6u⁵            (quintic smoothstep)
u      = (t − t_đoạn) / thời_lượng_đoạn
thời lượng = max(1, 1.875·d/v_max, sqrt((10/√3)·d/a_max))
nghỉ giữa đoạn = dwell (1,5 s)
```

`state(t)` trả `(vị trí, vận tốc, gia tốc, chỉ số đoạn, pha)` với pha ∈
`waiting | moving | dwell | descending | complete`. Đoạn hạ cánh (nếu có) dùng
`descent_speed` và phải thẳng đứng.

Hệ quả: drone **dừng lại ở mỗi waypoint**; vì vậy route được rút gọn bằng
Douglas–Peucker ở `build_world` (`--simplify 0.1` m) thay vì dùng 72–156 điểm
cắt cạnh thô.

## Điều khiển

```
a = a_ff + 2.5·(p_đích − p) + 3.2·(v_đích − v)
a = kẹp(a, ±6 m/s²)
lực = 1 kg × (a_x, a_y, a_z + 9.8)      ← bù trọng lực
```

Mô hình **điểm khối lượng chịu lực tại COM**; không phải mô hình rotor hay
autopilot.

## Telemetry 10 Hz

`physics_telemetry.csv`, 16 cột:

| Cột | Nội dung |
| --- | --- |
| `sim_time` | Thời gian mô phỏng (giây) |
| `x, y, z` | Vị trí thật của link |
| `target_x, target_y, target_z` | Điểm đích theo quỹ đạo |
| `error` | Khoảng cách thật tới đích |
| `vx, vy, vz` | Vận tốc thật |
| `target_vx, target_vy, target_vz` | Vận tốc mong muốn |
| `segment` | Chỉ số đoạn |
| `phase` | `waiting/moving/dwell/descending/complete` |

## `telemetry_metadata.json`

| Trường | Nội dung |
| --- | --- |
| `route_sha256` | Hash tuyến đã bay |
| `model` | Mô hình 1 kg, lực tại COM |
| `nominal_duration` | `trajectory.duration + start_delay` |
| `world`, `mission`, `goal` | Phiên chạy thuộc world/nhiệm vụ/đích nào |
| `run_id` | `<timestamp>-<pid>` (giữ theo quyết định; mỗi phiên làm file dirty) |

## Kiểm chứng

| Ở đâu | Việc | Kết quả |
| --- | --- | --- |
| Tại đây | `py_compile` hai file | OK |
| Tại đây | `grep "generated/" plugin/` | không còn đường dẫn cứng |
| Tại đây | `Trajectory` trên 3 route | `state(0)`/`state(cuối)` khớp endpoint; v ≤ 5 m/s; a ≤ 3 m/s² |
| Máy ảo | `run_simulate.sh --check` import plugin | chờ chạy |

Thời lượng danh nghĩa sau khi rút gọn (dwell 1,5 s):

| Goal | Waypoint | Thời gian |
| --- | --- | --- |
| g1 | 18 | 92,1 s |
| g2 | 47 | 224,1 s |
| g3 | 34 | 140,0 s |

## Giới hạn

- Cần `gz.sim10`; không chạy được bằng venv 3.14 (không có binding).
- Không import NumPy/Matplotlib — plugin chạy trong Gazebo bằng Python hệ thống.
- Chưa kiểm chứng API trên Gazebo Jetty thực tế; nếu tên hàm đổi, sửa theo
  binding và chạy lại `--check`.
