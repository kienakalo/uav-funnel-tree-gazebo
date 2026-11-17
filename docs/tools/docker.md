# `Dockerfile` — cả pipeline trong một image

| | |
| --- | --- |
| Nền | `ghcr.io/openrobotics/gazebo@sha256:452ff649…` (Gazebo Jetty 10.5.0, Ubuntu 24.04, Python 3.12.3) |
| Thêm vào | `numpy==2.5.4`, `shapely==2.2.0`, `matplotlib==3.11.2`, `pillow==13.0.0` |
| Vào | repo (trừ `.venv`, `generated/`, `results/`, `.git`) |
| Ra | image `uav-funnel-tree:pipeline`, chạy `python3 main.py` |
| Kèm | `docker-compose.yml` (3 backend GPU), `.dockerignore` |

## Vì sao một image

Pipeline có hai nửa: phần Python (`data`, `plan`, `validate`, `figures`) và
Gazebo (`simulate`). Tách hai image thì phải nối chúng bằng docker socket, tức
là cấp quyền cao hơn và thêm một lớp có thể sai. Lấy image Gazebo làm nền rồi
cài thêm bốn gói pip là cách ngắn nhất, và `simulate` chạy bằng `gz` ngay trong
image (`FUNNEL_RUNTIME=native`) nên không cần Docker lồng nhau.

## Build

```bash
docker compose build pipeline          # hoặc: docker build -t uav-funnel-tree:pipeline .
```

`docker-compose.yml` có ba service dùng chung một image, chỉ khác thiết bị đồ hoạ:

| Service | Thiết bị | Dùng khi |
| --- | --- | --- |
| `pipeline` | `nvidia.com/gpu=all` (CDI) | máy có NVIDIA, như máy đã đo |
| `pipeline-intel` | `/dev/dri` | Intel/AMD iGPU |
| `pipeline-software` | llvmpipe | không có GPU; chậm nhưng chạy được |

## Chạy

```bash
# chạy cả ba stage, không hỏi gì
FUNNEL_UID=$(id -u) FUNNEL_GID=$(id -g) \
  docker compose run --rm pipeline python3 main.py --no-ask

# một stage
docker compose run --rm pipeline python3 main.py plan --no-ask

# chỉ một goal, không mở cửa sổ
docker compose run --rm pipeline python3 main.py simulate --goal g1 --headless
```

`docker compose run` mount repo vào `/work`, nên kết quả ghi vào `generated/`
và `results/` của bạn, không nằm trong container. Muốn chạy hoàn toàn cô lập
(không mount), dùng `docker run --rm uav-funnel-tree:pipeline` — khi đó kết quả
nằm trong `/work` của image và mất khi container dừng.

## Ba biến môi trường image đặt sẵn

| Biến | Giá trị | Vì sao |
| --- | --- | --- |
| `FUNNEL_PYTHON` | `/usr/bin/python3` | `main.py` và `run_simulate.sh` vốn ưu tiên `.venv/bin/python`; mount repo từ host sẽ chỉ vào venv 3.14 của host và chết trong image |
| `FUNNEL_RUNTIME` | `native` | `run_simulate.sh` mặc định mở container Gazebo khác; trong image phải dùng `gz` có sẵn |
| `MPLCONFIGDIR` | `/tmp/matplotlib` | cache Matplotlib không ghi vào repo đang mount |

`HOME` và `XDG_RUNTIME_DIR` trỏ `/tmp` vì container chạy bằng UID của bạn.

## GUI

Cần `DISPLAY` của host và socket X11 (compose đã mount `/tmp/.X11-unix`):

```bash
xhost +local:            # một lần cho phiên hiện tại
docker compose run --rm pipeline python3 main.py simulate --goal g1
```

Không mở được cửa sổ thì dùng `--headless`; số đo không phụ thuộc GUI, plugin
chạy trên server Gazebo.

## Cổng kiểm chứng trước khi trích số trong container

Image chỉ dùng được để báo cáo nếu bốn bước sau đều đạt. Đã chạy ngày
17/11/2026, trên máy có MX150:

| Bước | Kết quả |
| --- | --- |
| `main.py data --no-ask` | 12,0 s; SHA bề mặt **`f6e01c6d…`** — trùng bản trên host, dù Python 3.12 thay vì 3.14 |
| `main.py plan --no-ask` | 50,1 s; route 142,419 / 125,636 / 86,152 m; `compare` 5/5 |
| `main.py simulate --goal g1 --headless` | 42,4 s; 353 dòng, `max_error` 0,365 m, `valid: true` |
| `tools/figures.py` | 0 lỗi |

Nếu SHA bề mặt khác, kết quả trong container **không** so được với số đã công
bố: khi đó phải ghim lại phiên bản Python/thư viện hoặc giữ bảng số của môi
trường host.

## Giới hạn

- Image ~3,2 GB (nền Gazebo 2,96 GB). Build cần mạng để `apt` và `pip`.
- Không có Docker trong container: `main.py simulate` dùng `--native`. Muốn
  quay lại chạy Gazebo trong container riêng thì `docker run` từ host như cũ,
  hoặc đặt `FUNNEL_RUNTIME=container` và mount docker socket.
- `gazebo.log` trong kết quả ghi đường dẫn tuyệt đối của máy chạy (`/work/...`),
  nên log của hai môi trường không byte-identical dù số đo trùng.
- Thời gian chạy phụ thuộc CPU host; đừng so giây giữa các máy.
