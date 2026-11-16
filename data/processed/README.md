# Dữ liệu đã xử lý

Thư mục này chứa đầu vào đã xử lý cho thuật toán, không sửa tay.
Nguồn nằm ở [`data/raw/`](../raw).

| Tệp | Bước | Công cụ |
| --- | --- | --- |
| `meshes/*.off` | Pass-through (validate + copy) | `tools/data/copy_meshes.py` |
| `scenes/city.standardized.glb` | Standardize | `tools/data/standardize.py` |
| `scenes/meshes/*.off2glb.glb` | OFF → GLB (Y-up) | `tools/data/off2glb.py` |
| `meshes/city.standardized.triangulation.off` | Tam giác phân bề mặt | `tools/data/triangulation.py` |
| `meshes/city.standardized.glb2off.off` | Bản OFF của scene để xem, không phải đầu vào thuật toán | `tools/data/glb2off.py` |
| `missions/<mesh>.json` | START/GOAL đã chọn | `tools/data/set_start_goal.py` |

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

Thuật toán dựng bề mặt (lưới ô, khe hở, lan truyền dốc) được mô tả từng bước
ở [`docs/tools/triangulation.md`](../../docs/tools/data/triangulation.md).

## Vì sao không có `city.standardized.off`

Scene chuẩn hoá là **GLB** vì cần giữ object, transform và mở được bằng
Blender/MeshLab. `.off` chỉ dành cho mesh dẫn xuất: một lưới duy nhất, đỉnh
dùng chung, toạ độ double. `tools/data/triangulation.py` dựng trực tiếp từ
`scenes/city.standardized.glb` qua `tools/data/glb2off.py: read_glb_scene` (bake
transform, đổi Z-up, chuẩn hoá width 200), nên không cần thêm một bản OFF
~20 MB không có nơi dùng và cũng không cần STL trung gian.

## Chạy

```bash
python3 tools/data/copy_meshes.py --write
python3 tools/data/standardize.py
python3 tools/data/off2glb.py
.venv/bin/python tools/data/triangulation.py --force
.venv/bin/python tools/data/data_viz.py --all
.venv/bin/python tools/data/set_start_goal.py
```

Bước `data_viz` render mỗi mesh `.off` thành một ảnh PNG trong
`generated/data_viz/`, kèm các đường tham chiếu trong `data/expected/` nếu có.
Dùng `--show` để mở cửa sổ 3D tương tác thay vì ghi PNG.

Bước cuối **không tự chọn hộ**: nó đọc `data/processed/missions/<mesh>.json` đã
lưu. Lần đầu, khi file chưa có, tool hỏi chọn START/GOAL trên terminal rồi ghi
file — kể cả khi stdout bị pipe, vì prompt đi qua `/dev/tty`. Muốn chọn lại dù
đã có file: `--force`, thêm `--pick` nếu muốn click trong cửa sổ 3D.

Không có file mission nào được ship sẵn trong Git. Chạy stage một lần rồi commit
`data/processed/missions/<mesh>.json` nếu muốn lựa chọn đó tái lập ở máy khác.

Stage `plan` đọc chính các file này (`python3 main.py plan`) và ghi tuyến vào
`generated/routes/`.

Sau bước này, mọi công cụ chỉ đọc `data/processed/`, không đọc thẳng
`data/raw/`.

Thêm `--force` khi ghi đè bề mặt đã có; nếu không, tool dừng. `triangulation.py`
cần Shapely, đọc thẳng `data/processed/scenes/city.standardized.glb` và nhận
`--start/--goal` (mặc định là hai đầu nhiệm vụ giao hàng). Không có bước STL
trung gian.

## Xem mesh `.off`

GLB mở được bằng Blender, MeshLab hoặc trình xem glTF; `.off` cần
`tools/data/data_viz.py`.

```bash
# một mesh (tên không cần .off)
.venv/bin/python tools/data/data_viz.py L

# nhiều mesh
.venv/bin/python tools/data/data_viz.py L terrain cube

# bề mặt thành phố
.venv/bin/python tools/data/data_viz.py city.standardized.triangulation

# đường dẫn đầy đủ, kể cả file ngoài data/processed/meshes
.venv/bin/python tools/data/data_viz.py data/processed/meshes/L.off

# tất cả
.venv/bin/python tools/data/data_viz.py --all
```

PNG ghi vào `generated/data_viz/<tên>.png`.

| Cờ | Tác dụng |
| --- | --- |
| `--show` | Mở cửa sổ 3D tương tác thay vì ghi PNG |
| `--source N` | Đánh dấu đỉnh nguồn N bằng màu cam |
| `--no-paths` | Không vẽ đè đường tham chiếu từ `data/expected/` |
| `--input DIR` | Đổi thư mục tìm mesh, mặc định `data/processed/meshes` |
| `--output DIR` | Đổi thư mục ghi ảnh, mặc định `generated/data_viz` |

Với `--show`, cửa sổ Matplotlib cho xoay/zoom bằng chuột; đóng cửa sổ để
thoát. Cần môi trường có giao diện (Ubuntu/WSLg); nếu backend không mở được,
dùng chế độ ghi PNG.

Mesh có `data/expected/<tên>.paths.json` sẽ được vẽ đè các đường tham chiếu
màu đỏ. `python3 main.py data` render tất cả ở bước 5 của stage `data`.

## Chọn START/GOAL

`tools/data/set_start_goal.py` quét mesh `.off`, in kích thước, số cạnh biên và
bước lưới, rồi lấy lựa chọn theo thứ tự:

1. **JSON đã lưu** — `data/processed/missions/<mesh>.json`; có file thì dùng
   luôn, không hỏi lại.
2. **Tham số dòng lệnh** — `--start-vertex`, `--goal-vertex`, `--start`,
   `--goal`, `--all-goals`.
3. **Hỏi tương tác** — gõ chỉ số hoặc `x y z`; `--pick` mở cửa sổ 3D để click
   (`s` gán START, `g` thêm GOAL, `u` bỏ GOAL cuối, Enter để lưu). `--pick` cần
   backend Tk/Qt/GTK (`sudo apt install python3-tk` hoặc `pip install PyQt6`,
   kèm thư viện hệ thống, xem mục Cài đặt trong README); thiếu backend thì tool
   báo rồi chuyển sang chọn bằng bàn phím.

`--force` bỏ qua file đã lưu để chọn lại. Khi chạy không có bàn phím
(`python3 main.py data`), tool cần file JSON hoặc tham số dòng lệnh; thiếu cả
hai thì dừng với thông báo rõ ràng.

### Ví dụ

```bash
# lần đầu: chọn tay trên bề mặt thành phố
.venv/bin/python tools/data/set_start_goal.py

# xem mesh nào đã có lựa chọn
.venv/bin/python tools/data/set_start_goal.py --list-meshes

# một mesh khác
.venv/bin/python tools/data/set_start_goal.py \
  --mesh data/processed/meshes/cliff.off --pick

# chọn cho mọi mesh còn thiếu
.venv/bin/python tools/data/set_start_goal.py --all-meshes

# hoặc chạy cả stage: bước mission mặc định chọn cho mọi mesh
python3 main.py data
python3 main.py data --no-all-meshes    # chỉ bề mặt thành phố
python3 main.py data --force-missions   # chọn lại cả mesh đã có

# chọn bằng chuột trong cửa sổ 3D
.venv/bin/python tools/data/set_start_goal.py --pick

# không tương tác
.venv/bin/python tools/data/set_start_goal.py \
  --start -38.752 22.103 7.206 --goal 74.737 -55.357 7.206

# mesh nhỏ: mọi đỉnh còn lại là goal
.venv/bin/python tools/data/set_start_goal.py \
  --mesh data/processed/meshes/cliff.off --start-vertex 1 --all-goals

# đọc lại lựa chọn đã lưu
.venv/bin/python tools/data/set_start_goal.py
```

### File JSON

| Trường | Nội dung |
| --- | --- |
| `mesh`, `mesh_sha256` | Mesh đã chọn điểm; SHA để phát hiện mesh thay đổi |
| `mesh_vertices`, `mesh_faces`, `boundary_edges` | Kích thước mesh lúc chọn |
| `vertex_spacing`, `snap_mode`, `max_snap` | Bước lưới và quy tắc snap |
| `mode` | `explicit` hoặc `all-goals` |
| `selected_by` | `cli`, `console` hoặc `pick` |
| `start` | `vertex`, `xyz`, `input`, `snap` |
| `goals` | `id`, `vertex`, `xyz`, `input`, `snap`; rỗng khi `all-goals` |

```json
{
  "mesh": "data/processed/meshes/city.standardized.triangulation.off",
  "mesh_sha256": "f6e01c6d…",
  "mesh_vertices": 2295,
  "mesh_faces": 4400,
  "vertex_spacing": 5.0,
  "snap_mode": "xy",
  "mode": "explicit",
  "selected_by": "cli",
  "start": {"vertex": 792, "xyz": [-38.752124, 22.103392, 8.643046], "snap": 0.000411},
  "goals": [{"id": "g1", "vertex": 1810, "xyz": [74.736587, -55.357157, 8.947593]}]
}
```

### Snap và giới hạn

- Toạ độ snap về đỉnh gần nhất trong XY; `--snap 3d` để snap theo 3D.
- Sai số được in ra và lưu ở `snap`; mặc định chặn nếu quá nửa đường chéo ô
  (`--max-snap` để đổi).
- `z` trong `xyz` là cao độ envelope, không phải `z` bạn nhập; `input` giữ điểm
  gốc để thấy đoạn tiếp cận.
- START không được trùng GOAL; hai GOAL không được trùng nhau.
- `--all-goals` chỉ dùng cho mesh tối đa 300 đỉnh.
- Tên file theo mesh: `missions/cliff.json`,
  `missions/city.standardized.triangulation.json`; `--mission` đổi đường dẫn,
  `--output` đổi thư mục.

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

`tools/data/triangulation.py` chuyển từ STL trung gian
(`generated/funnel_preview/city.stl`, dựng từ `data/raw/scenes/city.glb`) sang
đọc thẳng scene đã chuẩn hoá. Hai nguồn không cho cùng byte vì
`tools/data/standardize.py` làm tròn float32 *trước* khi chuẩn hoá, còn STL làm tròn
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
- Nếu cần Z-up, chạy `tools/data/off2glb.py --keep-z-up`.
- `city.standardized.triangulation.off` ở hệ **đã chuẩn hoá, Z-up**, cùng hệ
  với START/GOAL của nhiệm vụ.

## Lưu trong Git

- `scenes/city.standardized.glb`: **không commit** (khoảng 6 MB, sinh lại
  được từ `data/raw/scenes/city.glb`).
- `scenes/meshes/*.off2glb.glb`: commit, mỗi file vài KB.
- `meshes/city.standardized.triangulation.off`: commit, đây là đầu vào thuật toán.
