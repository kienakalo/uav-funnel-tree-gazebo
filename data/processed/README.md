# Dữ liệu đã xử lý

Thư mục này chứa đầu vào đã xử lý cho thuật toán, không sửa tay.
Nguồn nằm ở [`data/raw/`](../raw/).

| Tệp | Bước | Công cụ |
| --- | --- | --- |
| `meshes/*.off` | Pass-through (validate + copy) | `tools/copy_meshes.py` |
| `scenes/city.standardized.glb` | Standardize | `tools/standardize.py` |
| `scenes/meshes/*.off2glb.glb` | OFF → GLB (Y-up) | `tools/off2glb.py` |
| `meshes/city.standardized.triangulation.off` | Tam giác phân bề mặt | `tools/triangulation.py` |

Tên file theo quy trình. Không có file metadata đi kèm; tham số được ghi ở
dưới và in ra khi chạy tool.

## Vì sao từng bước

| Bước | Vì sao cần |
| --- | --- |
| Pass-through | Downstream chỉ đọc `processed/`; bản copy byte-identical tách "nguồn" khỏi "đầu vào đã kiểm tra" và phát hiện lệch giữa hai bản. |
| Standardize | `city.glb` là scene Sketchfab thô: 55 node, tên `Object_N`, material/texture, transform lồng nhau. Chuẩn hoá bake transform, đổi tên, bỏ material và ghi provenance vào `extras` để mọi công cụ đọc theo cùng một quy ước dữ liệu. |
| OFF → GLB | OFF không mở được bằng Blender/MeshLab; GLB thì được. Xuất Y-up đúng chuẩn glTF để xem đúng chiều; `--keep-z-up` nếu cần giữ Z-up. |
| Triangulation | Funnel Tree cần một mặt liên tục, đỉnh dùng chung, toạ độ double. `city.glb` là các vỏ công trình rời, không đi được. Bước này dựng envelope an toàn rồi tam giác phân thành 2.295 đỉnh / 4.400 mặt. |
| Visualization | `.off` không có viewer phổ quát; render PNG hoặc cửa sổ 3D để kiểm tra hình học và overlay đường tham chiếu. |

Tên tệp phản ánh chuỗi bước: `city.standardized.triangulation.off` = city →
standardize → triangulation.

## Vì sao không có `city.standardized.off`

Scene chuẩn hoá là **GLB** vì cần giữ object, transform và mở được bằng
Blender/MeshLab. `.off` chỉ dành cho mesh dẫn xuất: một lưới duy nhất, đỉnh
dùng chung, toạ độ double. Thành phố trong hệ Z-up đã chuẩn hoá được
`tools/data_viz.py --scene` và `tools/triangulation.py` dựng trực tiếp từ
`scenes/city.standardized.glb` qua `tools/glb2off.py: read_glb_scene` (bake
transform, đổi Z-up, chuẩn hoá width 200), nên không cần thêm một bản OFF
~20 MB không có nơi dùng và cũng không cần STL trung gian.

## Chạy

```bash
python3 tools/copy_meshes.py --write
python3 tools/standardize.py
python3 tools/off2glb.py
.venv/bin/python tools/triangulation.py --force
.venv/bin/python tools/data_viz.py --all
.venv/bin/python tools/set_start_goal.py \
  --start -38.752 22.103 7.206 --goal 74.737 -55.357 7.206 \
  --name data-demo --force
```

Bước `data_viz` render mỗi mesh `.off` thành một ảnh PNG trong
`generated/data_viz/`, kèm các đường tham chiếu trong `data/expected/` nếu có.
Dùng `--show` để mở cửa sổ 3D tương tác thay vì ghi PNG. Bước cuối dựng một
nhiệm vụ mẫu trong `generated/missions/data-demo/`.

Sau bước này, mọi công cụ chỉ đọc `data/processed/`, không đọc thẳng
`data/raw/`.

Thêm `--force` khi ghi đè bề mặt đã có; nếu không, tool dừng. `triangulation.py`
cần Shapely, đọc thẳng `data/processed/scenes/city.standardized.glb` và nhận
`--start/--goal` (mặc định là hai đầu nhiệm vụ giao hàng). Không có bước STL
trung gian.

## Xem mesh `.off`

GLB mở được bằng Blender, MeshLab hoặc trình xem glTF; `.off` cần
`tools/data_viz.py`.

```bash
# một mesh (tên không cần .off)
.venv/bin/python tools/data_viz.py L

# nhiều mesh
.venv/bin/python tools/data_viz.py L terrain cube

# bề mặt thành phố
.venv/bin/python tools/data_viz.py city.standardized.triangulation

# so sánh trước/sau tam giác phân: scene chuẩn hoá | bề mặt
.venv/bin/python tools/data_viz.py city.standardized.triangulation --scene

# đường dẫn đầy đủ, kể cả file ngoài data/processed/meshes
.venv/bin/python tools/data_viz.py data/processed/meshes/L.off

# tất cả
.venv/bin/python tools/data_viz.py --all
```

PNG ghi vào `generated/data_viz/<tên>.png`. Với `--scene`, ảnh là hai bảng
cạnh nhau `<tên>-compare.png`: bên trái là scene chuẩn hoá (trước), bên phải
là bề mặt đã tam giác phân (sau).

| Cờ | Tác dụng |
| --- | --- |
| `--show` | Mở cửa sổ 3D tương tác thay vì ghi PNG |
| `--source N` | Đánh dấu đỉnh nguồn N bằng màu cam |
| `--no-paths` | Không vẽ đè đường tham chiếu từ `data/expected/` |
| `--scene [GLB]` | So sánh với scene chuẩn hoá, mặc định `data/processed/scenes/city.standardized.glb` |
| `--scene-triangles N` | Giới hạn số tam giác của scene; `0` vẽ tất cả (mặc định) |
| `--input DIR` | Đổi thư mục tìm mesh, mặc định `data/processed/meshes` |
| `--output DIR` | Đổi thư mục ghi ảnh, mặc định `generated/data_viz` |

Với `--show`, cửa sổ Matplotlib cho xoay/zoom bằng chuột; đóng cửa sổ để
thoát. Cần môi trường có giao diện (Ubuntu/WSLg); nếu backend không mở được,
dùng chế độ ghi PNG.

Mesh có `data/expected/<tên>.paths.json` sẽ được vẽ đè các đường tham chiếu
màu đỏ. `python3 main.py data` render tất cả ở bước 5 của stage `data`.

## Chọn START/GOAL thủ công

`tools/set_start_goal.py` nhận điểm do bạn chọn, snap về đỉnh gần nhất rồi chạy
Funnel Tree. Mặc định chạy trên bề mặt đã xử lý; `--mesh` để dùng mesh khác.

### Nhiệm vụ trên bề mặt thành phố

```bash
# một goal
.venv/bin/python tools/set_start_goal.py \
  --start -38.752 22.103 7.206 \
  --goal 74.737 -55.357 7.206 \
  --name giao-hang

# ba goal trong một lần chạy, dùng chung một source graph
.venv/bin/python tools/set_start_goal.py \
  --start -38.752 22.103 7.206 \
  --goal 74.737 -55.357 7.206 \
  --goal 10 20 7.2 \
  --goal -60 -30 7.2 \
  --name ba-dich
```

### Fixture như `cliff.off`

```bash
# đỉnh bắt đầu do bạn chọn, mọi đỉnh còn lại là goal
.venv/bin/python tools/set_start_goal.py \
  --mesh data/processed/meshes/cliff.off \
  --start-vertex 1 --all-goals --name cliff-v1
```

`--all-goals` dựng cây đường đi từ một đỉnh nguồn tới **mọi đỉnh còn lại**, nên
chỉ dùng cho mesh nhỏ (tối đa 300 đỉnh). Với bề mặt thành phố, dùng `--goal`.

### File mission để tái lập

```json
{
  "name": "giao-hang",
  "start": [-38.752, 22.103, 7.206],
  "goals": [[74.737, -55.357, 7.206], [10, 20, 7.2]]
}
```

```bash
.venv/bin/python tools/set_start_goal.py --mission missions/giao-hang.json
```

Fixture có thể chỉ định bằng chỉ số đỉnh:

```json
{"name": "cliff-v1", "start_vertex": 1, "all_goals": true}
```

### Kết quả

| Tệp trong `generated/missions/<tên>/` | Nội dung |
| --- | --- |
| `plan.json` | điểm đã snap, chỉ số đỉnh, waypoints, độ dài, source chain, hash |
| `funnel_cache.json` | cache từng source, chỉ khi có goal cụ thể |
| `<tên>.paths.json` | một đường cho mỗi đỉnh, chỉ với `--all-goals` |
| `routes.png` | ảnh 3D các tuyến |

### Snap và giới hạn

- Toạ độ snap về đỉnh gần nhất trong XY; `--snap 3d` để snap theo 3D.
- Sai số được in ra; mặc định chặn nếu quá nửa đường chéo ô (`--max-snap` để đổi).
- `z` của đỉnh snap là cao độ envelope, không phải `z` bạn nhập. Waypoint đầu
  tiên vẫn là điểm bạn nhập để thấy đoạn tiếp cận.
- Kết quả không chứng nhận tối ưu (`optimality_certified: false`), giống thí nghiệm.
- Thêm `--force` khi ghi đè `plan.json` đã có; `--seconds` đổi giới hạn thời gian
  cho mỗi lần lan truyền.

## Tham số bề mặt hiện tại

| Tham số | Giá trị |
| --- | --- |
| Cell | 5 |
| Coverage | `city` |
| Vertical clearance | 1,5 |
| Horizontal half width | 1,6 |
| Max axis slope | 0,5 |
| Scene đầu vào | `data/processed/scenes/city.standardized.glb` |
| START mặc định | `-38.7521239854311 22.103391740920674 7.205632472302205` |
| GOAL mặc định | `74.73658745332892 -55.35715733632823 7.205632472302205` |
| Kết quả | 2.295 đỉnh, 4.400 tam giác, 6.694 cạnh |

Tham số được in ra console mỗi lần chạy. Không có file metadata đi kèm; muốn
tái lập thì dùng đúng lệnh và tham số ở trên.

### Thay đổi nguồn dựng bề mặt (2026-11-16)

`tools/triangulation.py` chuyển từ STL trung gian
(`generated/funnel_preview/city.stl`, dựng từ `data/raw/scenes/city.glb`) sang
đọc thẳng scene đã chuẩn hoá. Hai nguồn không cho cùng byte vì
`tools/standardize.py` làm tròn float32 *trước* khi chuẩn hoá, còn STL làm tròn
*sau*. Đo được trên bề mặt 2.295 đỉnh:

| | Trước | Sau |
| --- | --- | --- |
| SHA256 `city.standardized.triangulation.off` | `7baf3c084dd6767350c8b0dcf27e5490aa3b7ba16fabfd6854df0d6cf9ed7310` | `f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df` |
| Dung lượng | 117.644 byte | 117.870 byte |
| Toạ độ XY và danh sách mặt | — | giống tuyệt đối |
| Cao độ z | — | lệch ≤ 1,822e-06 m (1385/2295 đỉnh) |

Bề mặt dựng từ GLB trùng hình học với bề mặt cũ ở mức ≈2 µm: cùng danh sách
đỉnh theo XY và cùng danh sách mặt, chỉ cao độ z lệch trong sai số làm tròn
float32. Các kết quả thí nghiệm cũ dùng SHA trước đây đã được xoá khỏi cây làm
việc cùng đợt dọn repo; lấy lại ở tag `pre-data-only-cleanup` nếu cần đối chiếu.

## Trục toạ độ

- `city.standardized.glb` giữ **Y-up** đúng chuẩn glTF để mở bằng viewer.
- glTF giữ **Y-up**; mọi phép tính trong repo dùng **Z-up**, nên `glb2off`
  đổi trục khi đọc scene.
- Fixture `.off` dùng **Z-up** (z là cao độ). `.off2glb.glb` chuyển sang
  **Y-up** `(x, y, z) → (x, z, -y)` để mở đúng chiều trong mọi glTF viewer.
- Nếu cần Z-up, chạy `tools/off2glb.py --keep-z-up`.
- `city.standardized.triangulation.off` ở hệ **đã chuẩn hoá, Z-up**, cùng hệ
  với START/GOAL của nhiệm vụ.

## Lưu trong Git

- `scenes/city.standardized.glb`: **không commit** (khoảng 6 MB, sinh lại
  được từ `data/raw/scenes/city.glb`).
- `scenes/meshes/*.off2glb.glb`: commit, mỗi file vài KB.
- `meshes/city.standardized.triangulation.off`: commit, đây là đầu vào thuật toán.
