---
title: run_simulate.sh
aliases:
  - run_simulate
type: script
stage: simulate
source: tools/simulate/run_simulate.sh
tags:
  - funnel-tree/tool
  - funnel-tree/stage/simulate
---

# `tools/simulate/run_simulate.sh`

> [!abstract] Mục đích
> Chạy một phiên Gazebo cho một goal: dựng world nếu cần, kiểm runtime, chạy
> `gz sim` (trong container hoặc trên máy), chờ telemetry kết thúc rồi in kết
> quả.

> [!info] Vị trí
> **File** `tools/simulate/run_simulate.sh` (kèm `gazebo_system_python.sh`) — stage `simulate`, bước chạy  
> **Thuật toán** Kiểm runtime → chạy `gz sim` trong container/máy → chờ `phase=complete` → in kết quả  
> **Vào** `generated/simulate/<mission>-<goal>/funnel_physics.sdf` + `flown_route.json`  
> **Ra** trong cùng thư mục: telemetry, metadata, `gazebo.log`, ảnh chụp (nếu có)  
> **Cờ** `--mission`, `--goal`, `--headless`, `--software`, `--show-surface`, `--timeout S`, `--check`, `--no-build`, `--container/--native`, `--image`, `--gpu`, `--keep-open`, `--pull`  
> **Cần** Docker (mặc định) hoặc Gazebo Jetty trên máy (`--native`)  

## Thành phần chính

| Hàm shell | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `usage()` | — | help | In toàn bộ cờ và ví dụ |
| `check_environment()` | cờ runtime | lỗi hoặc `ok` | Kiểm Docker/image hoặc `gz` trên máy, bindings, plugin |
| `check_files()` | mission, goal | lỗi hoặc `ok` | Kiểm SDF, `flown_route.json`, `gz sdf -k`, Assimp đọc GLB |
| `resolve_gpu()`, `gpu_label()` | `--gpu` | `nvidia`/`intel`/`software` + nhãn | Chọn thiết bị render và nhãn ghi vào `FUNNEL_GPU` |
| `prepare_gui_home()` | `world_metadata.json` | `HOME` tạm | Gọi `gui_config.py` để có camera + `MarkerManager` |
| `unpause_world()` | tên world | — | Gửi `/world/<world>/control` sau khi plugin đã nạp |
| `wait_for_completion()` | chế độ chạy | mã thoát | GUI chờ hết tuyến; headless chờ `phase=complete` |
| `cleanup()` | — | — | Đóng tiến trình và dọn container còn sót |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Hệ thống | `docker`, image `ghcr.io/openrobotics/gazebo:jetty-full` | Runtime mặc định |
| Hệ thống | `gz`, `gz sdf`, `libassimp5` | Runtime `--native` và kiểm SDF/GLB |
| Nội bộ | `tools/simulate/build_world.py` | Dựng world khi không có `--no-build` |
| Nội bộ | `tools/simulate/gui_config.py` | Ghi `gui.config` cho `HOME` tạm |
| Nội bộ | `tools/simulate/check_glb.py` | Kiểm visual trước khi bay |
| Nội bộ | `gazebo_system_python.sh` | Bỏ `VIRTUAL_ENV`/`PYTHONHOME` khi chạy native |

## Việc nó làm

```text
1. build_world.py --mission --goal [--surface]      (bỏ qua khi --no-build)
2. kiểm runtime: Docker + image, hoặc gz trên máy; bindings; plugin; SDF; GLB
3. backup physics_telemetry.csv + telemetry_metadata.json cũ (cùng timestamp)
4. export FUNNEL_ROUTE, FUNNEL_OUTPUT_DIR, FUNNEL_RUN_ID, FUNNEL_GPU, FUNNEL_TRAIL
5. dựng gui.config riêng (camera + MarkerManager) nếu chạy GUI
6. chạy gz sim (-r cho GUI, -s -r cho headless) trong container hoặc trên máy
7. chờ telemetry_metadata.json có đúng run_id
8. unpause /world/<world>/control
9. GUI: chờ route xong rồi đóng cửa sổ (trừ khi --keep-open)
   headless: chờ CSV có phase=complete rồi dừng
10. in số dòng telemetry và Save at
```

Mỗi lần chạy là một tiến trình Gazebo mới; không có trạng thái nào được giữ lại
ngoài các file trong thư mục run.

## Cờ

| Cờ | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--mission STEM` | `city.standardized.triangulation` | Tên route trong `generated/routes/` |
| `--goal ID` | `g1` | Goal trong route; route nhiều goal vẫn fail-closed ở `build_world` |
| `--headless` | tắt | `gz sim -s -r`, không mở cửa sổ; tự dừng khi `phase=complete` |
| `--software` | tắt | Ép `LIBGL_ALWAYS_SOFTWARE=1` (llvmpipe), tương đương `--gpu software` |
| `--show-surface` | tắt | Vẽ thêm bề mặt envelope (`surface.stl`) |
| `--timeout S` | 900 | Giới hạn chờ một phiên (headless và GUI) |
| `--check` | tắt | Chỉ kiểm runtime + file, không mở Gazebo |
| `--no-build` | tắt | Không gọi `build_world.py`; dùng world đã có |
| `--container` / `--native` | container | Chạy trong image Gazebo hay dùng `gz` trên máy |
| `--image NAME` | `ghcr.io/openrobotics/gazebo:jetty-full` | Image dùng cho `--container` |
| `--gpu auto\|nvidia\|intel\|software` | `auto` | Chọn đường render cho GUI |
| `--keep-open` | tắt | Không tự đóng cửa sổ khi route xong |
| `--pull` | tắt | `docker pull` image trước khi chạy |

## Chế độ container (mặc định)

Máy chỉ cần Docker; image đã có Gazebo Jetty 10.5.0, bindings Python
(`gz.sim`/`gz.math` không hậu tố) và `libassimp5`.

Hai biến môi trường đổi cách chọn runtime, dùng khi script chạy *bên trong* một
image đã có Gazebo (xem [`../docker.md`](../docker.md)):

| Biến | Tác dụng |
| --- | --- |
| `FUNNEL_RUNTIME=native` | `main.py` thêm `--native` cho bước bay, để không mở container lồng nhau |
| `FUNNEL_PYTHON=/usr/bin/python3` | bỏ qua `.venv/bin/python` của host đang mount, dùng interpreter trong image |

```bash
bash tools/simulate/run_simulate.sh --check
python3 main.py simulate --goal g1
```

Cách script gọi container:

| Thành phần | Cách nối |
| --- | --- |
| Repo | mount tại `/work`; SDF dùng URI tương đối nên chạy được ở bất kỳ đường dẫn nào |
| Người dùng | `--user $(id -u):$(id -g)`, file ghi ra thuộc đúng user trên host |
| Màn hình | `-e DISPLAY`, `-e QT_QPA_PLATFORM=xcb`, mount `/tmp/.X11-unix` |
| Telemetry | `FUNNEL_ROUTE=/work/...`, `FUNNEL_OUTPUT_DIR=/work/...` |
| Plugin | `PYTHONPATH=/work/tools/simulate/plugin:/usr/lib/python3/dist-packages` |
| Home của Gazebo | thư mục tạm chứa `.gz/sim/10/gui.config` (xem `gui_config.py`) |

`--headless` bỏ các tham số màn hình và chạy `gz sim -s -r`.

## GPU

`--gpu auto` chọn theo thứ tự:

| Điều kiện | Lựa chọn | Tham số container |
| --- | --- | --- |
| có `/var/run/cdi/nvidia-container-toolkit.json` và `nvidia-smi` chạy được | `nvidia` | `--device nvidia.com/gpu=all`, `__NV_PRIME_RENDER_OFFLOAD=1`, `__GLX_VENDOR_LIBRARY_NAME=nvidia` |
| có `/dev/dri` | `intel` | `--device /dev/dri` (Mesa dùng GPU Intel) |
| không có GPU | `software` | `LIBGL_ALWAYS_SOFTWARE=1` (llvmpipe) |

Docker hiện không nhận `--gpus all` khi chỉ có CDI spec của NVIDIA
(`failed to discover GPU vendor from CDI: no known GPU vendor found`), nên
script dùng `--device nvidia.com/gpu=all`.

Tên GPU được ghi vào telemetry metadata qua `FUNNEL_GPU`, ví dụ
`nvidia: NVIDIA GeForce MX150` hoặc `intel: /dev/dri (Mesa)`.

## `--check`

```
check: runtime, plugin, world, SDF and visual mesh are ready
runtime: container ghcr.io/openrobotics/gazebo:jetty-full
gpu: nvidia: NVIDIA GeForce MX150
world: funnel_sim_city_standardized_triangulation_g1
run:   generated/simulate/city.standardized.triangulation-g1
```

Nó kiểm:

1. Docker chạy được (hoặc `gz` trên PATH khi `--native`).
2. Image tồn tại và `gz sim --versions` chạy được trong image.
3. Bindings `gz.sim`/`gz.math` hoặc `gz.sim10`/`gz.math9` import được.
4. Plugin `funnel_drone_system` import được.
5. `funnel_physics.sdf`, `flown_route.json` tồn tại; `gz sdf -k` chấp nhận SDF.
6. Assimp trong image đọc được `city.sim.glb` (`check_glb.py`). Bước này bắt
   đúng lỗi bufferView từng làm thành phố biến mất trong Gazebo.

## Ảnh minh hoạ

Pipeline **không** chụp ảnh. Muốn ảnh cho báo cáo, tự chụp cửa sổ Gazebo (ví dụ
`grim -g "$(hyprctl clients -j | ...)"`) hoặc dùng ảnh từ `tracking.png` — file
này do `validate.py` vẽ từ telemetry, không phải screenshot. Khi chèn ảnh, ghi
rõ nguồn và phiên chạy theo `AGENTS.md`.

## Biến môi trường truyền cho Gazebo

| Biến | Giá trị |
| --- | --- |
| `FUNNEL_ROUTE` | `/work/generated/simulate/<mission>-<goal>/flown_route.json` (hoặc đường dẫn tuyệt đối khi `--native`) |
| `FUNNEL_OUTPUT_DIR` | thư mục run |
| `FUNNEL_RUN_ID` | `<timestamp>-<pid>` |
| `FUNNEL_GPU` | nhãn GPU đã chọn |
| `FUNNEL_TRAIL` | `0` để tắt vệt bay trên `/marker` (mặc định bật) |
| `PYTHONPATH` | plugin + `/usr/lib/python3/dist-packages` |

### `gazebo_system_python.sh`

Script 14 dòng, chỉ dùng ở nhánh `--native` — tức trên máy có Gazebo, hoặc trong
image pipeline vì image đặt `FUNNEL_RUNTIME=native`. `run_simulate.sh` gọi
`bash tools/simulate/gazebo_system_python.sh sim … <sdf>` thay cho `gz sim`;
nhánh container gọi thẳng `gz sim` trong `docker run`.

| Bước | Việc | Vì sao |
| --- | --- | --- |
| `cd "$(dirname "$0")/../.."` | về gốc repo | Script chạy được từ thư mục khác, không phụ thuộc `cwd` |
| `unset VIRTUAL_ENV PYTHONHOME` | bỏ dấu vết venv | Gazebo nhúng Python hệ thống; nếu còn `VIRTUAL_ENV`, `gz` nạp `libpython` của venv và không thấy binding `gz.sim` cài bằng apt |
| `PATH=/usr/bin:/bin:$PATH` | ưu tiên lệnh hệ thống | Tránh một `gz` khác trong `PATH` (bản build tay, shim) |
| `PYTHONPATH=$PWD/tools/simulate/plugin:/usr/lib/python3/dist-packages` | đường dẫn import | Plugin tìm thấy `trajectory.py`; Python thấy binding Gazebo của hệ thống |
| `PYTHONNOUSERSITE=1` | bỏ `site-packages` của người dùng | Kết quả không phụ thuộc gói cài bằng `pip --user` |
| `exec /usr/bin/gz "$@"` | thay tiến trình | PID, tín hiệu và mã thoát đi thẳng cho `run_simulate.sh` |

Hệ quả khi viết plugin: chỉ được dùng thư viện có trong Python hệ thống — đó là
lý do `trajectory.py` chỉ cần stdlib. Chạy trong container thì script này không
được gọi: image đã có `gz` ở `/usr/bin` và `PYTHONPATH` do `docker run` đặt.

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
python3 main.py simulate --goal g1 --headless --gpu software
python3 main.py simulate --goal g3 --native
```

Stage gồm 3 bước: `build_world.py`, `run_simulate.sh --no-build`, `validate.py`.
Chạy script trực tiếp thì nó tự dựng world (trừ khi thêm `--no-build`).

## Lỗi thường gặp

| Thông báo | Nguyên nhân |
| --- | --- |
| `docker not found` | Chưa cài Docker; dùng `--native` nếu máy có Gazebo |
| `the Docker daemon is not reachable` | Docker chưa chạy hoặc user không thuộc nhóm docker |
| `image ... is missing` | Chưa pull; chạy `--pull` hoặc `docker pull ghcr.io/openrobotics/gazebo:jetty-full` |
| `failed to discover GPU vendor from CDI` | Dùng `--gpus all`; script đã dùng `--device nvidia.com/gpu=all` |
| `Gazebo exited before the controller loaded` | Plugin lỗi lúc `configure`; xem `gazebo.log` |
| `gz sdf rejects ...` | SDF hỏng hoặc mesh URI không tồn tại |
| `Assimp cannot import .../city.sim.glb` | GLB sai bufferView; dựng lại world (`build_world.py`) |
| Không thấy cửa sổ Gazebo | Thiếu `DISPLAY`/X socket, hoặc chạy `--headless` |

## Liên quan

- [`build_world.md`](build_world.md) — bước 1 của stage, sinh world và route.
- [`plugin.md`](plugin.md) — module được nạp trong phiên chạy này.
- [`validate.md`](validate.md) — bước 3, chấm telemetry vừa ghi.
- [`../docker.md`](../docker.md) — `FUNNEL_RUNTIME=native` khi chạy trong image.
