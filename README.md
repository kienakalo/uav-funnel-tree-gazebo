# UAV Funnel Tree — dữ liệu dẫn đường

Repo này dựng **dữ liệu đầu vào và tuyến cho Funnel Tree**: từ scene thành phố
thô (`data/raw/scenes/city.glb`) và chín mesh mẫu, stage `data` tạo ra scene đã
chuẩn hoá, các bản GLB để xem, bề mặt tam giác phân dùng làm miền dẫn đường,
ảnh kiểm tra hình học và nhiệm vụ START → GOAL; stage `plan` chạy thuật toán,
vẽ tuyến và đối chiếu độ dài với đường tham chiếu.

Thuật toán Funnel Tree chỉ đọc mesh `.off`; repo này không chứa phần mô phỏng
Gazebo hay benchmark.

## Kết quả của stage `data`

| Tệp | Nội dung |
| --- | --- |
| `data/processed/meshes/*.off` | Chín mesh mẫu, copy byte-identical từ `data/raw/meshes/` |
| `data/processed/scenes/city.standardized.glb` | Scene thành phố đã bake transform, bỏ material |
| `data/processed/scenes/meshes/*.off2glb.glb` | Mesh mẫu ở dạng GLB Y-up để mở bằng viewer |
| `data/processed/meshes/city.standardized.triangulation.off` | Bề mặt dẫn đường 2.295 đỉnh / 4.400 tam giác |
| `generated/data_viz/*.png` | Ảnh kiểm tra từng mesh, kèm đường tham chiếu |
| `data/processed/missions/<mesh>.json` | START/GOAL đã chọn cho từng mesh |

## Kết quả của stage `plan`

| Tệp | Nội dung |
| --- | --- |
| `generated/routes/<mission>.json` | Waypoint từng tuyến, độ dài, hash mesh/mission/mã thuật toán, tham số và thời gian chạy |
| `generated/routes/<mission>.png` | Ảnh bề mặt + các tuyến |
| `generated/compare/<mesh>.json` | So từng đỉnh với `data/expected/<mesh>.paths.json` |
| `generated/compare/summary.json` | Mesh nào đạt, không đạt, bị bỏ qua |

## Cài đặt

Cần Python 3.10+ với NumPy, Matplotlib (ảnh) và Shapely (tam giác phân):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Cửa sổ 3D (`--show`, `--pick`) cần thêm thư viện hệ thống, pip không cài được:

```bash
# Debian/Ubuntu
sudo apt install python3-tk libzstd1 libxkbcommon0 libgl1 libegl1
# hoặc: .venv/bin/pip install PyQt6   (vẫn cần các lib hệ thống ở trên)

# NixOS: Tk nằm trong site-packages của interpreter Nix, venv không thấy
ln -sf "$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"/_tkinter*.so \
  .venv/lib/python*/site-packages/

# hoặc dùng PyQt6 trong môi trường FHS
steam-run .venv/bin/python tools/plan/route_viz.py \
  --routes generated/routes/city.standardized.triangulation.json --show
```

Chỉ cửa sổ 3D cần các gói này; chạy stage bằng PNG thì không cần.

`main.py` tự dùng `.venv/bin/python` nếu có, ngược lại dùng `python3`.

## Chạy

```bash
python3 main.py flow        # liệt kê các bước và lệnh
python3 main.py data        # chạy toàn bộ stage
python3 main.py data --dry-run

# bước 6 mặc định chọn START/GOAL cho mọi mesh (10 file mission)
python3 main.py data
python3 main.py data --no-all-meshes       # chỉ bề mặt thành phố
python3 main.py data --force-missions      # chọn lại cả mesh đã có

python3 main.py plan        # lập tuyến, vẽ ảnh, đối chiếu reference
```

Sáu bước, dừng ngay khi một bước lỗi:

| # | Lệnh | Vào → Ra |
| --- | --- | --- |
| 1 | `tools/data/copy_meshes.py --write` | `data/raw/meshes/*.off` → `data/processed/meshes/*.off` |
| 2 | `tools/data/standardize.py` | `data/raw/scenes/city.glb` → `scenes/city.standardized.glb` |
| 3 | `tools/data/off2glb.py` | `raw/meshes/*.off` → `scenes/meshes/*.off2glb.glb` |
| 4 | `tools/data/triangulation.py --force` | `city.standardized.glb` → `meshes/city.standardized.triangulation.off` |
| 5 | `tools/data/data_viz.py --all` | `processed/meshes/*.off` → `generated/data_viz/*.png` |
| 6 | `tools/data/set_start_goal.py` | bề mặt → `data/processed/missions/<mesh>.json` |

Stage `plan` có ba bước:

| # | Lệnh | Vào → Ra |
| --- | --- | --- |
| 1 | `tools/plan/run_funnel.py` | missions + `.off` → `generated/routes/*.json` |
| 2 | `tools/plan/route_viz.py` | routes JSON → `generated/routes/*.png` |
| 3 | `tools/plan/compare.py` | routes + `data/expected` → `generated/compare/*.json` |

Bước 4 cần `--force` vì tệp đích đã tồn tại; nếu không, tool dừng để tránh ghi
đè ngoài ý muốn. Bước 6 dùng lại lựa chọn START/GOAL đã lưu; lần đầu chưa có
`data/processed/missions/<mesh>.json` thì tool hỏi chọn ngay trong terminal rồi
ghi file. Không có file nào được ship sẵn: commit lựa chọn của bạn nếu muốn tái
lập. Tham số bề mặt được in ra console và ghi ở
[`data/processed/README.md`](data/processed/README.md).

## Bề mặt dẫn đường

Bề mặt không phải địa hình hay mái nhà: đó là **envelope an toàn** phía trên
thành phố, dựng theo từng ô lưới, nâng lên theo khe hở dọc và mở rộng thành
dốc. Nó chỉ tồn tại trong hành lang giữa START và GOAL:

```bash
# mặc định: hai đầu nhiệm vụ giao hàng
.venv/bin/python tools/data/triangulation.py --force

# nhiệm vụ khác
.venv/bin/python tools/data/triangulation.py --force \
  --start -38.752 22.103 7.206 --goal 74.737 -55.357 7.206 \
  --cell 5 --coverage city --output /tmp/surface.off
```

## Kiểm tra và chọn điểm

```bash
# xem một mesh
.venv/bin/python tools/data/data_viz.py L
.venv/bin/python tools/data/data_viz.py city.standardized.triangulation
```

`set_start_goal.py` đọc mesh, in kích thước và lưới, rồi lấy lựa chọn theo thứ
tự: **file JSON đã lưu → tham số dòng lệnh → hỏi tương tác**. Lựa chọn được lưu
một lần, các lần sau chạy lại chỉ đọc, không hỏi lại.

```bash
# lần đầu: chọn tay, lưu vào data/processed/missions/<mesh>.json
.venv/bin/python tools/data/set_start_goal.py

# chọn bằng chuột trong cửa sổ 3D (cần Tk hoặc Qt, xem dưới)
.venv/bin/python tools/data/set_start_goal.py --pick

# không tương tác: chọn theo chỉ số hoặc toạ độ
.venv/bin/python tools/data/set_start_goal.py \
  --start -38.752 22.103 7.206 --goal 74.737 -55.357 7.206

# mesh nhỏ: mọi đỉnh còn lại là goal
.venv/bin/python tools/data/set_start_goal.py \
  --mesh data/processed/meshes/cliff.off --start-vertex 1 --all-goals

# chọn lại
.venv/bin/python tools/data/set_start_goal.py --force
```

`--pick` (và `--show` của `data_viz`, `route_viz`) cần backend đồ hoạ: cài
`sudo apt install python3-tk` hoặc `pip install PyQt6` trong `.venv`, kèm
`libzstd1 libxkbcommon0 libgl1` (Debian/Ubuntu). Thiếu backend thì `--show` báo
lỗi rõ và dừng; `--pick` tự chuyển sang chọn bằng bàn phím.

Mặc định tool làm việc trên bề mặt thành phố. Muốn chọn cho mesh khác, hoặc cho
tất cả:

```bash
# xem mesh nào đã có lựa chọn
.venv/bin/python tools/data/set_start_goal.py --list-meshes

# một mesh cụ thể
.venv/bin/python tools/data/set_start_goal.py \
  --mesh data/processed/meshes/cliff.off --pick

# mọi mesh còn thiếu (bỏ qua mesh đã có, --force để làm lại)
.venv/bin/python tools/data/set_start_goal.py --all-meshes
```

Chi tiết cờ và schema JSON ở
[`data/processed/README.md`](data/processed/README.md).

## Định dạng

- `.off`: lưới tam giác văn bản, `OFF` + `V F E` + đỉnh + mặt.
- `.glb`: glTF 2 nhị phân; scene chuẩn hoá giữ Y-up, mesh dẫn xuất dùng Z-up.
- `.paths.json`: đường tham chiếu cho ảnh kiểm tra.

Quy ước chi tiết ở [`docs/data-format.md`](docs/data-format.md); mỗi tool một
file mô tả thuật toán ở [`docs/tools/`](docs/tools/README.md).

## Cấu trúc thư mục

```text
main.py                  # chạy stage data / plan
data/
  raw/                   # nguồn, không sửa tay
  processed/             # đầu vào đã xử lý, sinh lại bằng tools/
  expected/              # đường tham chiếu cho ảnh kiểm tra
tools/data/
  copy_meshes.py         # validate + copy mesh mẫu
  standardize.py         # chuẩn hoá scene GLB
  off2glb.py             # OFF → GLB
  triangulation.py       # dựng + tam giác phân bề mặt
  data_viz.py            # render PNG / cửa sổ 3D
  set_start_goal.py      # chọn START/GOAL, lưu JSON
  glb2off.py             # đọc GLB (duyệt cây node, bake transform) + ghi OFF
tools/plan/
  run_funnel.py          # chạy Funnel cho các mission
  route_viz.py           # routes JSON → PNG
  compare.py             # so độ dài với data/expected
tools/simulate/
  build_world.py         # dựng world Gazebo + mesh từ một route
algo/
  funnel_tree.py         # lan truyền, dựng lại tuyến, tìm source
lib/
  mesh_glb.py            # container GLB
  mesh_off.py            # đọc/ghi OFF + lớp Mesh (kề, góc, khoảng cách)
  plotting.py            # chọn backend cửa sổ, báo lỗi rõ khi thiếu
generated/               # đầu ra
docs/
  data-format.md         # quy ước định dạng
  tools/                 # mỗi tool một file: vào/ra, thuật toán, giới hạn
```

`lib/` không phải package: các module được import theo tên sau khi thêm `lib/`
vào `sys.path`, xem [`lib/README.md`](lib/README.md).

## Lưu trong Git

- Commit: dữ liệu `raw/`, đầu ra `processed/` (kể cả `missions/*.json`), mã
  nguồn, tài liệu và kết quả stage `plan` (`generated/routes/**`,
  `generated/compare/**`).
- Không commit: `.venv/`, `generated/data_viz/` và
  `data/processed/scenes/city.standardized.glb` vì sinh lại được ở bước 2.

Chạy lại stage `data` phải cho ra đúng byte của
`data/processed/meshes/city.standardized.triangulation.off`. Nếu khác, ghi lại
SHA cũ/mới và lý do trong `data/processed/README.md`.

## Giấy phép và nguồn

Mã nguồn theo BSD-3-Clause ([LICENSE](LICENSE)). Nguồn, giấy phép và trục của
từng tệp dữ liệu ở [ATTRIBUTION.md](ATTRIBUTION.md) và
[`data/README.md`](data/README.md).
