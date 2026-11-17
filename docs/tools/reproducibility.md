# Tái lập kết quả

## Nguyên tắc

Mỗi kết quả phải trả lời được: **dữ liệu nào, mã nào, tham số nào**. Vì vậy:

| Kết quả | Định danh được ghi |
| --- | --- |
| Route JSON | SHA256 của mission, của mesh, của `algo/funnel_tree.py` |
| Mission JSON | SHA256 của mesh + số đỉnh/mặt lúc chọn |
| Bề mặt `.off` | SHA256 (ghi trong README của `data/processed`) |
| Scene chuẩn hoá | `source_sha256` trong `extras` |
| Fixture GLB | `source_sha256` trong `extras` |

## Cái gì tất định

| File | Tất định? | Ghi chú |
| --- | --- | --- |
| `data/processed/meshes/*.off` | Có | Copy byte-identical từ `raw/` |
| `data/processed/meshes/city.standardized.triangulation.off` | Có | Phụ thuộc scene + START/GOAL + hằng số |
| `data/processed/scenes/meshes/*.off2glb.glb` | Có | |
| `data/processed/scenes/city.standardized.glb` | Có | Có commit; SHA dưới đây |
| `data/processed/missions/*.json` | Có | Không có timestamp |
| `generated/routes/*.json` | **Không** | `planning_seconds` đổi mỗi lần chạy |
| `generated/compare/*.json` | Có | Không chứa thời gian |
| `generated/simulate/*/physics_telemetry.csv` | Không | Phụ thuộc physics Gazebo |
| `generated/simulate/*/telemetry_metadata.json` | Không | Có `run_id` của phiên |
| `generated/simulate/*/validation.json` | Không | Có `run_id` và số đo phiên |
| `generated/simulate/*/tracking.png` | Không | Vẽ từ telemetry của phiên |
| `generated/simulate/*/gazebo.log` | Không | Log phiên; chứa đường dẫn tuyệt đối của máy chạy |

Vì `planning_seconds` là số đo thật, chạy lại `main.py plan` sẽ làm route JSON
dirty trong Git. Đó là lựa chọn có chủ đích: báo cáo cần thời gian chạy.

## Cái gì làm kết quả đổi

| Thay đổi | Ảnh hưởng |
| --- | --- |
| Sửa `city.glb` | Scene chuẩn hoá → bề mặt → mọi route |
| Sửa `cell`, `CLEARANCE`, `HALF_WIDTH`, `MAX_AXIS_SLOPE` | Bề mặt |
| Đổi START/GOAL của triangulation | Bề mặt (lưới và extent) |
| Sửa `algo/funnel_tree.py` | Route + `solver.module_sha256` |
| Đổi mission (START/GOAL) | Route của mission đó |
| Sửa `data/expected/*.paths.json` | Kết quả `compare` |

## Quy trình chạy lại

```bash
python3 main.py data     # tái tạo bề mặt + mission (mission đã có thì giữ)
python3 main.py plan     # route + ảnh + compare
```

Kiểm tra bề mặt không đổi:

```bash
sha256sum data/processed/meshes/city.standardized.triangulation.off
# f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df
```

Nếu khác, ghi SHA cũ/mới + lý do vào
[`../../data/processed/README.md`](../../data/processed/README.md) trước khi
commit.

Tham số đã dùng nằm ở hai chỗ, nên một kết quả luôn truy được về cấu hình:

| File | Nội dung |
| --- | --- |
| `generated/parameters.json` | `main.py` ghi mỗi run: tham số từng bước, nguồn (mặc định / người trả lời / cờ), dòng lệnh, commit, thời gian chạy |
| `data/processed/meshes/city.standardized.triangulation.params.json` | `triangulation.py` ghi cạnh bề mặt: tham số, SHA của scene, script và file `.off` |
| `data/processed/meshes/city.standardized.glb2off.params.json` | `glb2off.py` ghi cạnh bản xem: `width`, SHA của scene và file OFF |
| `<ảnh>.png.json` | `figstamp` ghi cạnh mỗi PNG: tham số, facts, SHA của input + ảnh, script, dòng lệnh (xem [`figures.md`](figures.md)) |
| `results/runs/<label>/manifest.json` | `main.py --label` ghi cả một lần chạy: tham số + nguồn, SHA, độ dài route, kết quả bay |

`generated/parameters.json` không commit (mỗi run ghi đè). Khi trích số liệu
vào báo cáo, chép cả tham số từ file này, không chỉ chép kết quả.

### Ảnh có dấu tham số

Mỗi PNG do pipeline sinh (`data_viz`, `route_viz`, `validate`) mang tham số ở
ba chỗ: chân ảnh, metadata PNG và sidecar `.png.json`. Nhờ vậy hai ảnh cùng tên
ở hai cấu hình khác nhau vẫn phân biệt được. Kiểm tra bằng:

```bash
.venv/bin/python tools/figures.py
```

Đánh đổi đã chọn: dấu có **thời điểm chạy**, nên chạy lại cùng tham số vẫn cho
PNG khác byte. So sánh giữa hai lần chạy bằng tham số + SHA của input
(`surface`, `route`), **không** bằng hash ảnh.

### Archive và so sánh giữa các lần chạy

`--fresh` chỉ xoá những gì các stage được chọn sinh lại (xem
[`main.md`](main.md)); số liệu của một lần chạy chỉ còn nếu đã lưu:

```bash
python3 main.py --label grid5        # chạy rồi lưu
python3 main.py --label grid4        # cấu hình khác, không cần --fresh
python3 tools/plan/compare_runs.py   # bảng cho báo cáo
```

Archive nằm ở `results/runs/<label>/`, ngoài mọi vùng xoá. Mỗi archive giữ
`manifest.json`, `parameters.json`, sidecar bề mặt, mission, route + ảnh route,
`plan-summary.json` và thư mục từng goal (`validation.json`, `world_metadata.json`,
quỹ đạo bay, `tracking.png` + sidecar, `telemetry_metadata.json`).

`commit` trong `manifest.json` là `HEAD` **lúc lưu archive**, không phải lúc bay.
Với `--label` (chạy rồi lưu ngay) hai thời điểm trùng nhau; với `--archive` (lưu
kết quả đã có) thì không — `parameters.json` trong archive cũng chỉ là log của
lần `main.py` **cuối cùng**, có thể chỉ là một goal. Muốn biết số liệu do commit
nào sinh ra thì đọc `validation.json`/`route.json` (có `route_sha256`,
`telemetry_sha256`) và `created_at`/mtime của file; đừng suy từ `commit`.

## Môi trường

- Python 3.14.8, NumPy 2.5.4, Matplotlib 3.11.2, Shapely 2.2.0, Pillow 13.0.0
  (pin trong `requirements.txt`).
- Phiên bản Python và NumPy của lần chạy được ghi trong từng route JSON.
- Gói hệ thống cho cửa sổ 3D trên host: `libzstd1 libxkbcommon0 libgl1`
  (Debian/Ubuntu); NixOS dùng `steam-run` hoặc symlink `_tkinter`.

### Mô phỏng

| Hạng mục | Giá trị của các lần chạy trong repo |
| --- | --- |
| Runtime | container `ghcr.io/openrobotics/gazebo:jetty-full` |
| Digest image | `sha256:452ff649281065121a524ef92354091ac069f2c9b0f73f61fd4c77c61bab08c7` |
| Gazebo | Jetty `gz sim 10.5.0`, bindings `gz.sim`/`gz.math` (không hậu tố) |
| Assimp | 5.3.1 (`libassimp5` trong image) |
| GPU | NVIDIA GeForce MX150 qua CDI (`--device nvidia.com/gpu=all`), Xwayland, `__NV_PRIME_RENDER_OFFLOAD=1` |
| Docker | 29.9.1 trên NixOS 26.11 |
| Vật lý | DART, bước 1 ms, RTF 1 |

Telemetry chỉ có nghĩa với đúng tổ hợp này; đổi GPU không đổi số đo (vật lý chạy
CPU), nhưng đổi phiên bản Gazebo/DART thì có. Mỗi `telemetry_metadata.json` ghi
`run_id` và `trail`; GPU đã dùng nằm trong biến `FUNNEL_GPU` mà script truyền
(nếu cần lưu vĩnh viễn, chép vào ghi chú phiên).

Chạy lại:

```bash
bash tools/simulate/run_simulate.sh --check
python3 main.py simulate --goal g1     # ~1 phút gồm dựng world + bay + chấm
```

Pipeline không sinh ảnh cửa sổ. Ảnh minh hoạ (nếu có) do người chạy tự chụp;
ghi nguồn và phiên chạy khi chèn vào báo cáo. Số đo nằm trong
`physics_telemetry.csv`, `validation.json` và `tracking.png` (vẽ từ CSV).

## Số liệu để trích dẫn

| Hạng mục | Giá trị |
| --- | --- |
| Bề mặt thành phố | 2.295 đỉnh / 4.400 tam giác / 6.694 cạnh |
| Tham số bề mặt | ô 5 m, clearance 1,5 m, half-width 1,6 m, slope 0,5 m/m |
| Tham số bay | 5 m/s, 3 m/s², dwell 0 s, start delay 2 s |
| SHA256 bề mặt | `f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df` |
| SHA256 `city.standardized.glb` | `cdd605eedc01011c5c39408ce167fca6244d1a9e0a7527450d13861570a837cb` (sau khi sửa bufferView + thêm NORMAL) |
| Route city (polyline) | 142,42 m · 125,64 m · 86,15 m (mission START 792 → 1810 / 1910 / 1518) |
| Cung spline | không được ghi lại: `world_metadata.json` chỉ có độ dài polyline đã rút gọn (142,42 · 125,63 · 86,14 m). Số cung spline của mission cũ (134,9 · 286,8 · 142,4 m) đo tay, không có script tái lập — đừng trích như số chính thức |
| Bay g1 / g2 / g3 | 35,4 s / 33,2 s / 24,6 s; `max_error` 0,365 / 1,022 / 0,851 m, `mean_error` 0,068 / 0,110 / 0,091 m (mission START 792, lưu ở `results/runs/city792`) |
| Lặp lại cùng mission | `city792b`: 36,4 s / 33,0 s / 24,3 s, `max_error` 0,365 / 1,026 / 0,852 m; `city792c`: 35,7 s / 32,9 s / 24,2 s, 0,365 / 1,022 / 0,852 m — g2 nằm trong 1,02–1,03 m qua năm lần bay, không phải nhiễu |
| Mốc chất lượng bám tuyến | 1,0 m — cả ba lần bay đều `valid`; g2 vượt mốc 2 % tại một góc cua (xem `simulate/validate.md`) |
| Thời gian `main.py plan` | 70–90 s cho cả 10 mission, riêng city 62–78 s; phụ thuộc tải máy nên chỉ ghi khoảng |
| Đối chiếu reference | 5/5 fixture, sai lệch lớn nhất 1,7e-5 |
| Trạng thái thuật toán | experimental, chưa chứng nhận tối ưu |

## Điều chưa kiểm chứng

Nói rõ khi báo cáo:

1. Tuyến **chưa** được kiểm tra độc lập là nằm trên mặt (chỉ có tự kiểm độ dài
   và đối chiếu reference cho 5 fixture). Quỹ đạo Catmull-Rom trong mô phỏng có
   thể bo góc khác polyline vài decimet.
2. City và 4 mesh còn lại **không có reference**, nên không có đối chiếu ngoài.
3. Funnel Tree chưa được chứng minh tối ưu trên mặt không lồi.
4. Bề mặt là envelope an toàn, không phải địa hình thật.
