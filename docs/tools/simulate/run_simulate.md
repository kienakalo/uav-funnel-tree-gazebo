# `tools/simulate/run_simulate.sh`

| | |
| --- | --- |
| Stage | `simulate` (bước chạy) |
| Vào | `generated/routes/<mission>.json` (qua `build_world.py`) |
| Ra | `generated/simulate/<mission>-<goal>/` — world, telemetry, metadata, log |
| Cờ | `--mission`, `--goal`, `--headless`, `--software`, `--show-surface`, `--timeout S`, `--check`, `--no-build` |

## Việc nó làm

```
1. build_world.py --mission --goal [--surface]   (bỏ qua khi --no-build)
2. kiểm môi trường: gz, gz.sim10, import plugin
3. backup physics_telemetry.csv + telemetry_metadata.json cũ (cùng timestamp)
4. export FUNNEL_ROUTE, FUNNEL_OUTPUT_DIR, FUNNEL_RUN_ID
5. chạy gz sim (-r GUI, -s -r headless) qua gazebo_system_python.sh
6. chờ telemetry_metadata.json có đúng run_id
7. unpause /world/<world>/control
8. GUI: chờ đóng cửa sổ; headless: chờ CSV có phase=complete rồi dừng
9. in số dòng telemetry và Save at
```

## Cờ

| Cờ | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--mission STEM` | `city.standardized.triangulation` | Tên route trong `generated/routes/` |
| `--goal ID` | `g1` | Goal trong route; route nhiều goal vẫn fail-closed ở `build_world` |
| `--headless` | tắt | `gz sim -s -r`, tự dừng khi `phase=complete` |
| `--software` | tắt | `LIBGL_ALWAYS_SOFTWARE=1` cho máy không GPU |
| `--show-surface` | tắt | Vẽ thêm bề mặt envelope (`surface.stl`) |
| `--timeout S` | 900 | Giới hạn chờ ở chế độ headless |
| `--check` | tắt | Chỉ kiểm môi trường + file, không mở Gazebo |
| `--no-build` | tắt | Không gọi `build_world.py`; dùng world đã có |

## `--check`

```
check: gz, gz.sim10/gz.sim, plugin, world and SDF are ready
world: funnel_sim_city_standardized_triangulation_g1
run:   generated/simulate/city.standardized.triangulation-g1
```

Nó kiểm: `gz` có trong PATH; `/usr/bin/python3` import được `gz.sim10`/`gz.math9` (bản build từ source) hoặc `gz.sim`/`gz.math` (gói Debian/Ubuntu); plugin `funnel_drone_system` import được với `PYTHONPATH=tools/simulate/plugin`; `funnel_physics.sdf` và `route.json` tồn tại; `gz sdf -k` chấp nhận SDF.

## Biến môi trường truyền cho Gazebo

| Biến | Giá trị |
| --- | --- |
| `FUNNEL_ROUTE` | `$PWD/generated/simulate/<mission>-<goal>/route.json` |
| `FUNNEL_OUTPUT_DIR` | thư mục run |
| `FUNNEL_RUN_ID` | `<timestamp>-<pid>` |
| `PYTHONPATH` | `tools/simulate/plugin:/usr/lib/python3/dist-packages` |
| `LIBGL_ALWAYS_SOFTWARE` | `1` khi `--software` |

`tools/simulate/gazebo_system_python.sh` xoá `VIRTUAL_ENV`/`PYTHONHOME` trước khi `exec gz`, để Gazebo dùng Python hệ thống có binding.

## Backup

Trước mỗi phiên, nếu đã có kết quả:

```
physics_telemetry_YYYYmmdd_HHMMSS.csv
telemetry_metadata_YYYYmmdd_HHMMSS.json
```

Cùng một mốc thời gian cho cả hai, để CSV và metadata luôn khớp cặp.

## Chạy qua `main.py`

```bash
python3 main.py simulate --goal g2
python3 main.py simulate --goal g1 --headless --software
```

Stage gồm 3 bước: `build_world.py`, `run_simulate.sh --no-build`, `validate.py`.
Chạy script trực tiếp thì nó tự dựng world (trừ khi thêm `--no-build`).

## Lỗi thường gặp

| Thông báo | Nguyên nhân |
| --- | --- |
| `gz not found` | Chưa cài Gazebo Jetty hoặc không có trong PATH |
| `system python3 has no gz.sim10 bindings` | Thiếu gói Python binding của gz-sim 10 |
| `cannot import funnel_drone_system` | Sai `PYTHONPATH` hoặc lỗi cú pháp plugin |
| `Gazebo exited before the controller loaded` | Plugin lỗi lúc `configure`; xem `gazebo.log` |
| `gz sdf rejects ...` | SDF hỏng hoặc mesh URI không tồn tại |
