# `plugin/` — bộ điều khiển bay

| | |
| --- | --- |
| Stage | `simulate` bước 2 |
| File | `tools/simulate/plugin/trajectory.py`, `funnel_drone_system.py` |
| Chạy trong | tiến trình Gazebo, system Python 3.12 có `gz.sim10` (source build) hoặc `gz.sim` (gói Debian/Ubuntu) |
| Vào | `flown_route.json` (qua `FUNNEL_ROUTE`) |
| Ra | `physics_telemetry.csv`, `telemetry_metadata.json` (trong `FUNNEL_OUTPUT_DIR`) |

## Vai trò

World ở bước 1 chỉ có một hộp 1 kg. Plugin này là **phi công**: đọc tuyến, biến
nó thành kế hoạch theo thời gian, và mỗi bước vật lý đẩy hộp bằng lực để bám
theo kế hoạch.

## Biến môi trường

| Biến | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `FUNNEL_ROUTE` | Có | Đường dẫn tuyệt đối tới `flown_route.json` |
| `FUNNEL_OUTPUT_DIR` | Có | Thư mục ghi CSV + metadata; tạo nếu chưa có |
| `FUNNEL_RUN_ID` | Không | Định danh phiên, ghi vào metadata |

Thiếu biến bắt buộc → `ValueError` ngay trong `configure`; Gazebo ghi lỗi vào log.

## `trajectory.py`

Bay **một mạch** qua toàn bộ tuyến, không dừng ở từng waypoint:

1. Lấy mẫu **Catmull-Rom** qua các waypoint (tangent sai phân trung tâm), bước
   0,2 m → polyline dày đặc, hướng tiếp tuyến liên tục ở các góc.
2. Đo **độ dài cung** của polyline đó.
3. Một biên dạng tốc độ **hình thang** cho cả tuyến: tăng tốc `a`, chạy đều
   `v_max`, giảm tốc `a` về 0 đúng điểm cuối.

```
s(t) = ½at²                                  (t < t_ramp)
     = s_ramp + v_peak·(t − t_ramp)           (t ≤ t_ramp + t_cruise)
     = L − ½a·(T − t)²                       (giảm tốc)
T    = 2·t_ramp + t_cruise
```

`state(t)` trả `(vị trí, vận tốc, gia tốc, chỉ số đoạn, pha)` với pha ∈
`waiting | moving | dwell | complete`. `dwell` chỉ còn là thời gian giữ ở điểm
cuối trước khi `complete`; `build_world` đặt **0** nên drone không dừng giữa
tuyến. Nếu có `descent_speed` và waypoint cuối nằm thẳng dưới waypoint trước,
tốc độ bị giới hạn thêm cho đoạn hạ cánh.

Thời lượng (dwell 0, sau khi làm mượt):

| Goal | Waypoint | Độ dài cung | Thời lượng |
| --- | --- | --- | --- |
| g1 | 18 | 134,9 m | 28,7 s + 2 s chờ |
| g2 | 47 | 286,8 m | 59,0 s + 2 s chờ |
| g3 | 34 | 142,4 m | 30,1 s + 2 s chờ |

Vì tốc độ/hướng liên tục, quỹ đạo mượt nhưng có thể **bo góc** khác polyline
gốc vài decimet; `--simplify 0.1` giữ waypoint sát hình học nên độ lệch nhỏ.

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
| `trail` | `true` nếu plugin publish vệt bay lên `/marker` |

## Vệt bay trên Gazebo

Khi `FUNNEL_TRAIL` khác `0` (mặc định), plugin advertise `/marker`
(`gz.msgs.Marker`, `LINE_STRIP`, màu hồng) và mỗi 0,25 s thêm điểm vị trí thật
rồi publish lại. GUI có `MarkerManager` (xem `gui_config.py`) nên vệt hiện dần
trên bản đồ — bằng chứng trực quan drone đã đi qua đâu.

Nếu image thiếu `gz.transport` hoặc `FUNNEL_TRAIL=0`, plugin vẫn bay bình thường
và ghi `trail: false` vào metadata.

## Kiểm chứng

| Ở đâu | Việc | Kết quả |
| --- | --- | --- |
| Tại đây | `py_compile` hai file | OK |
| Tại đây | `grep "generated/" plugin/` | không còn đường dẫn cứng |
| Tại đây | `Trajectory` trên 3 route | `state(0)`/`state(cuối)` khớp endpoint; v ≤ 5 m/s; a ≤ 3 m/s² |
| Máy ảo | `run_simulate.sh --check` import plugin | chờ chạy |

Thời lượng danh nghĩa được tính lại từ tuyến đã làm mượt (bảng ở trên).

## Giới hạn

- Cần `gz.sim10`/`gz.math9` hoặc `gz.sim`/`gz.math`; không chạy được bằng venv 3.14 (không có binding).
- Không import NumPy/Matplotlib — plugin chạy trong Gazebo bằng Python hệ thống.
- Chưa kiểm chứng API trên Gazebo Jetty thực tế; nếu tên hàm đổi, sửa theo
  binding và chạy lại `--check`.
