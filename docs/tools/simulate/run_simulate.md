# `tools/simulate/run_simulate.sh`

| | |
| --- | --- |
| Stage | `simulate` (bước chạy) |
| Vào | `generated/simulate/<mission>-<goal>/funnel_physics.sdf` + `route.json` (do `build_world.py` sinh) |
| Ra | `generated/simulate/<mission>-<goal>/` — telemetry, metadata, `gazebo.log`, ảnh chụp |
| Cờ | `--mission`, `--goal`, `--headless`, `--software`, `--show-surface`, `--timeout S`, `--check`, `--no-build`, `--container/--native`, `--image`, `--gpu`, `--screenshot/--no-screenshot`, `--keep-open`, `--pull` |

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
9. GUI: chụp ảnh ở 10/60/120 s và lúc hoàn thành, đóng khi route xong
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
| `--screenshot` / `--no-screenshot` | bật khi GUI | Chụp cửa sổ Gazebo ở các mốc thời gian mô phỏng |
| `--keep-open` | tắt | Không tự đóng cửa sổ khi route xong |
| `--pull` | tắt | `docker pull` image trước khi chạy |

## Chế độ container (mặc định)

Máy chỉ cần Docker; image đã có Gazebo Jetty 10.5.0, bindings Python
(`gz.sim`/`gz.math` không hậu tố) và `libassimp5`.

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
5. `funnel_physics.sdf`, `route.json` tồn tại; `gz sdf -k` chấp nhận SDF.
6. Assimp trong image đọc được `city.sim.glb` (`check_glb.py`). Bước này bắt
   đúng lỗi bufferView từng làm thành phố biến mất trong Gazebo.

## Ảnh chụp cửa sổ

Khi chạy GUI, `screenshot.py` được gọi ở các mốc **thời gian mô phỏng** 10 s,
60 s, 120 s và lúc `phase=complete` (mốc vượt quá thời lượng route bị bỏ qua):

```
screenshot_t010.png / .json
screenshot_t060.png / .json
screenshot_complete.png / .json
```

Mỗi file `.json` ghi `run_id`, `sim_time`, `phase`, hình học cửa sổ, lệnh chụp,
`DISPLAY`/`WAYLAND_DISPLAY`, SHA256 của ảnh và ghi chú rằng ảnh là **chụp cửa sổ
GUI**, không phải đầu ra đo của mô phỏng. Kết quả đo vẫn là
`physics_telemetry.csv` và `validation.json`.

Trên Hyprland, cửa sổ được tìm theo class `Gazebo GUI` và cắt bằng `grim -g`.
Các cửa sổ Gazebo đang mở trước phiên được ghi vào `FUNNEL_IGNORE_WINDOWS` để
không bị chụp nhầm. Trên X11, script lùi về `import -window root` (chụp cả màn
hình) và ghi rõ trong metadata.

## Biến môi trường truyền cho Gazebo

| Biến | Giá trị |
| --- | --- |
| `FUNNEL_ROUTE` | `/work/generated/simulate/<mission>-<goal>/route.json` (hoặc đường dẫn tuyệt đối khi `--native`) |
| `FUNNEL_OUTPUT_DIR` | thư mục run |
| `FUNNEL_RUN_ID` | `<timestamp>-<pid>` |
| `FUNNEL_GPU` | nhãn GPU đã chọn |
| `FUNNEL_TRAIL` | `0` để tắt vệt bay trên `/marker` (mặc định bật) |
| `PYTHONPATH` | plugin + `/usr/lib/python3/dist-packages` |

`tools/simulate/gazebo_system_python.sh` xoá `VIRTUAL_ENV`/`PYTHONHOME` trước khi
`exec gz` khi chạy native, để Gazebo dùng Python hệ thống có binding.

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
