# UAV Funnel Tree — dữ liệu dẫn đường

Repo này dựng **dữ liệu đầu vào cho Funnel Tree**: từ scene thành phố thô
(`data/raw/scenes/city.glb`) và chín mesh mẫu, stage `data` tạo ra scene đã
chuẩn hoá, các bản GLB để xem, bề mặt tam giác phân dùng làm miền dẫn đường,
ảnh kiểm tra hình học và một nhiệm vụ mẫu START → GOAL.

Thuật toán Funnel Tree chỉ đọc mesh `.off`; repo này không chứa phần mô phỏng,
benchmark hay thí nghiệm.

## Kết quả của stage `data`

| Tệp | Nội dung |
| --- | --- |
| `data/processed/meshes/*.off` | Chín mesh mẫu, copy byte-identical từ `data/raw/meshes/` |
| `data/processed/scenes/city.standardized.glb` | Scene thành phố đã bake transform, bỏ material |
| `data/processed/scenes/meshes/*.off2glb.glb` | Mesh mẫu ở dạng GLB Y-up để mở bằng viewer |
| `data/processed/meshes/city.standardized.triangulation.off` | Bề mặt dẫn đường 2.295 đỉnh / 4.400 tam giác |
| `generated/data_viz/*.png` | Ảnh kiểm tra từng mesh, kèm đường tham chiếu |
| `data/processed/missions/<mesh>.json` | START/GOAL đã chọn cho từng mesh |

## Cài đặt

Cần Python 3.10+ với NumPy, Matplotlib (ảnh) và Shapely (tam giác phân):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`main.py` tự dùng `.venv/bin/python` nếu có, ngược lại dùng `python3`.

## Chạy

```bash
python3 main.py flow        # liệt kê các bước và lệnh
python3 main.py data        # chạy toàn bộ stage
python3 main.py data --dry-run
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
# xem một mesh, hoặc so sánh scene với bề mặt
.venv/bin/python tools/data/data_viz.py L
.venv/bin/python tools/data/data_viz.py city.standardized.triangulation --scene
```

`set_start_goal.py` đọc mesh, in kích thước và lưới, rồi lấy lựa chọn theo thứ
tự: **file JSON đã lưu → tham số dòng lệnh → hỏi tương tác**. Lựa chọn được lưu
một lần, các lần sau chạy lại chỉ đọc, không hỏi lại.

```bash
# lần đầu: chọn tay, lưu vào data/processed/missions/<mesh>.json
.venv/bin/python tools/data/set_start_goal.py

# chọn bằng chuột trong cửa sổ 3D
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

Chi tiết cờ và schema JSON ở
[`data/processed/README.md`](data/processed/README.md).

## Định dạng

- `.off`: lưới tam giác văn bản, `OFF` + `V F E` + đỉnh + mặt.
- `.glb`: glTF 2 nhị phân; scene chuẩn hoá giữ Y-up, mesh dẫn xuất dùng Z-up.
- `.paths.json`: đường tham chiếu cho ảnh kiểm tra.

Quy ước chi tiết ở [`docs/data-format.md`](docs/data-format.md) và
[`data/README.md`](data/README.md).

## Cấu trúc thư mục

```text
main.py                  # chạy stage data
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
  glb2off.py             # GLB → OFF (thư viện đọc scene + tool)
  glb_nodes.py           # duyệt node GLB, bake transform
  off_mesh.py            # kiểm tra topology + ghi OFF
src/
  funnel_tree.py         # lan truyền và dựng lại tuyến
  verification.py        # kiểm tra đoạn thẳng nằm trên mesh
  glb.py                 # container GLB
generated/               # đầu ra, không commit
docs/data-format.md      # quy ước định dạng
```

`src/` không phải package: các module được import theo tên sau khi thêm `src/`
vào `sys.path`, xem [`src/README.md`](src/README.md).

## Lưu trong Git

- Commit: dữ liệu `raw/`, đầu ra `processed/` (kể cả `missions/*.json`), mã
  nguồn và tài liệu.
- Không commit: `.venv/`, `generated/**` (trừ `generated/README.md`) và
  `data/processed/scenes/city.standardized.glb` vì sinh lại được ở bước 2.

Chạy lại stage `data` phải cho ra đúng byte của
`data/processed/meshes/city.standardized.triangulation.off`. Nếu khác, ghi lại
SHA cũ/mới và lý do trong `data/processed/README.md`.

## Giấy phép và nguồn

Mã nguồn theo BSD-3-Clause ([LICENSE](LICENSE)). Nguồn, giấy phép và trục của
từng tệp dữ liệu ở [ATTRIBUTION.md](ATTRIBUTION.md) và
[`data/README.md`](data/README.md).
