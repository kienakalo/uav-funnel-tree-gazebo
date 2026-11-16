# Pipeline: từng bước và từng tool

Tài liệu này mô tả **chính xác** dữ liệu vào/ra và thuật toán của từng bước, để
viết báo cáo hoặc kiểm tra lại kết quả. Quy ước định dạng nằm ở
[`data-format.md`](data-format.md); cấu trúc thư mục ở
[`../README.md`](../README.md).

## 0. Luồng dữ liệu

```text
data/raw/scenes/city.glb ──standardize──► data/processed/scenes/city.standardized.glb
                                                  │
                                                  └─triangulation──► .../city.standardized.triangulation.off
                                                                          │
data/processed/missions/<mesh>.json ──────────────────────────────────────┤
                                                                          ▼
                                                                    run_funnel ──► generated/routes/<mission>.json
                                                                                        │
                                                                    route_viz ──────────┴──► .png
                                                                    compare   ──► generated/compare/*.json

data/raw/meshes/*.off ──copy_meshes──► data/processed/meshes/*.off
                      └─off2glb──────► data/processed/scenes/meshes/*.off2glb.glb
```

Hai stage độc lập theo một chiều: `plan` chỉ đọc kết quả của `data`, không sửa
`data/`.

## 1. `main.py`

| | |
| --- | --- |
| Vai trò | Chạy stage bằng subprocess, dừng ở lỗi đầu tiên |
| Chọn interpreter | `.venv/bin/python` nếu tồn tại, ngược lại `sys.executable` |
| `STAGES` | `data`: 6 lệnh; `plan`: 3 lệnh |
| `flow` | In các lệnh sẽ chạy rồi thoát |
| `--dry-run` | In lệnh, không chạy |
| `--all-meshes` / `--no-all-meshes` | Bước 6 của `data`: chọn cho mọi mesh (mặc định) hay chỉ bề mặt |
| `--force-missions` | Chỉ với `--all-meshes`: chọn lại cả mesh đã có mission |

`main.py` không tự tính gì; mọi phép tính nằm trong tool. Vì vậy muốn trích dẫn
số liệu, chạy tool trực tiếp với cùng tham số.

## 2. Stage `data`

### 2.1 `tools/data/copy_meshes.py`

| | |
| --- | --- |
| Vào | `data/raw/meshes/*.off` |
| Ra | `data/processed/meshes/*.off` (byte-identical) |
| Kiểm tra | `read_off` trên bản nguồn: header, số dòng, mặt tam giác, chỉ số đỉnh, toạ độ hữu hạn |
| `--check` | So byte từng cặp raw/processed, báo lệch |

Mục đích: tách "nguồn" khỏi "đầu vào đã kiểm tra", và phát hiện lệch byte giữa
hai bản. Không biến đổi hình học.

### 2.2 `tools/data/standardize.py`

| | |
| --- | --- |
| Vào | `data/raw/scenes/city.glb` (scene Sketchfab, 55 node, Y-up) |
| Ra | `data/processed/scenes/city.standardized.glb` |
| Đọc | `tools/data/glb2off.py: transformed_objects` — duyệt cây node, bake transform, trả tam giác ở toạ độ world |
| Ghi | `lib/mesh_glb.py: write_glb` |

Các bước:

1. Duyệt scene graph, nhân dồn ma trận từng node (`translation`/`rotation`/
   `scale` hoặc `matrix`), đưa mọi tam giác về toạ độ world của scene.
2. Gộp tam giác rời của từng node thành lưới có chỉ số (`indexed_from_triangles`).
3. Đổi tên node thành `object_000`, `object_001`, … và giữ tên gốc trong `extras`.
4. Bỏ material và texture; **không** đổi trục, **không** chuẩn hoá đơn vị.
5. Ghi `extras` cấp scene: `source_file`, `source_sha256`, `license`, `author`,
   `source_url`, `title`, `units`, `axis` (`Y-up (glTF convention)`), `objects`,
   `vertices`, `triangles`, `policy`.
6. Đọc lại file vừa ghi, kiểm tổng số tam giác và toạ độ hữu hạn.

Hệ quả số học: phép bake chạy trên float64, nhưng GLB lưu float32, nên toạ độ
bị làm tròn **trước** khi chuẩn hoá. Đây là lý do bề mặt dựng từ scene chuẩn
hoá lệch cỡ `2e-6` m so với bề mặt dựng từ STL cũ (xem
[`../data/processed/README.md`](../data/processed/README.md)).

### 2.3 `tools/data/off2glb.py`

| | |
| --- | --- |
| Vào | `data/raw/meshes/*.off` |
| Ra | `data/processed/scenes/meshes/<mesh>.off2glb.glb` |
| Đổi trục | `(x, y, z) → (x, z, −y)` (Z-up của fixture → Y-up của glTF) |
| `--keep-z-up` | Giữ nguyên Z-up khi cần hệ mô phỏng |
| `--mesh` | Chỉ chuyển các mesh được nêu tên |

Không sửa hình học, chỉ đổi hệ trục và đóng gói. `extras` ghi `source_file`,
`source_sha256`, `axis`, `units`, `vertices`, `triangles`, `policy`. Sau khi
ghi, đọc lại và so số đỉnh/mặt.

### 2.4 `tools/data/glb2off.py`

| | |
| --- | --- |
| Vào | `data/processed/scenes/city.standardized.glb` (hoặc bất kỳ GLB 2) |
| Ra | `generated/meshes/<stem>.glb2off.off` |
| Cờ | `--output`, `--width` (mặc định 200), `--force` |
| Vai trò | Tool độc lập **và** thư viện đọc scene cho `triangulation`, `data_viz`, `standardize` |

Xử lý:

1. `read_document`: tách header 12 byte, chunk JSON, chunk BIN; từ chối file
   không phải GLB 2.
2. `_accessor`: đọc accessor thành mảng NumPy (chỉ kiểu `u1/u2/u4/f4`, không
   sparse, không buffer ngoài).
3. `_node_matrix`: dựng ma trận 4×4 cục bộ của node.
4. `iter_scene_meshes`: duyệt cây, nhân dồn ma trận, trả `(tên, vertices, faces)`
   ở toạ độ world, giữ trục và đơn vị gốc.
5. `read_glb_scene`: gộp tất cả, đổi **Y-up → Z-up** `(x, z, −y)`, rồi chuẩn hoá:
   `scale = width / max(dx, dy)`, `origin = (tâm XY, z_min)`,
   `vertices = (vertices − origin) × scale`.
6. Ghi OFF bằng `lib/mesh_off.py: write_off` (`%.17g`), đếm cạnh thực, kiểm số
   dòng = `2 + V + F`.

Với `city.standardized.glb`: 204.682 đỉnh, 301.490 tam giác, 498.767 cạnh,
bề rộng 200 m.

### 2.5 `tools/data/triangulation.py`

Đây là bước quan trọng nhất của stage `data`.

| | |
| --- | --- |
| Vào | `data/processed/scenes/city.standardized.glb` + START/GOAL |
| Ra | `data/processed/meshes/city.standardized.triangulation.off` |
| Tham số | `--cell 5`, `--coverage city`, `--start`, `--goal`, `--output`, `--force` |
| Hằng số | `CLEARANCE = 1.5`, `HALF_WIDTH = 1.6`, `MAX_AXIS_SLOPE = 0.5` |
| Cần | Shapely (`STRtree`, `box`, `polygons`) |

Thuật toán:

1. **Đọc tam giác thành phố** từ scene: `(vertices, faces) = read_glb_scene(...)`,
   rồi `triangles = vertices[faces]` (Z-up, đơn vị mét đã chuẩn hoá).
2. **Lưới ô.** `xs`, `ys` là bội số của `cell` phủ vùng `extent` (mọi đỉnh tam
   giác + START + GOAL) nới thêm 16 m mỗi phía; luôn chèn thêm toạ độ START/GOAL
   để hai điểm nằm đúng trên lưới.
3. **Độ cao yêu cầu cho từng ô** `(i, j)`: lấy hộp 2D của ô nới `HALF_WIDTH` mỗi
   phía, truy vấn `STRtree` các tam giác phủ hộp, lấy **z cao nhất** trong đó
   cộng `CLEARANCE`. Nếu ô không phủ tam giác nào, yêu cầu là `CLEARANCE`.
   Công thức: `required[i,j] = max(z của tam giác giao hộp) + 1.5`.
4. **Độ cao đỉnh lưới**: khởi tạo `CLEARANCE`; mỗi đỉnh ô nhận `max` của
   `required` ở tối đa 4 ô kề nó.
5. **Lan truyền dốc (ramp).** Dùng max-heap: lấy đỉnh cao nhất, hạ dần sang 4
   hàng xóm theo `h ≤ h_nguồn − 0.5 × khoảng cách`. Bước này chỉ **nâng** độ
   cao, không hạ, nên envelope vẫn an toàn.
6. **Kiểm tra từng ô**: 4 đỉnh của ô phải ≥ `required` (sai số `1e-9`).
7. **Dựng mặt**: mỗi ô thành 2 tam giác; `inspect_mesh` xác nhận không có cạnh
   non-manifold, không đỉnh "fan" rời, không tam giác suy biến.
8. **Kiểm tra cột đứng tại START/GOAL**: hộp `HALF_WIDTH` quanh mỗi điểm không
   được giao tam giác thành phố trong khoảng z giữa điểm và mặt (±0.2 m).
9. **Ghi OFF** với số cạnh thực.

Ý nghĩa: đây là **envelope an toàn phía trên thành phố**, không phải địa hình
hay mái nhà. Mặt chỉ tồn tại trong hành lang giữa START và GOAL; ngoài hành lang
không có gì để đi.

Kết quả hiện tại: 2.295 đỉnh, 4.400 tam giác, 6.694 cạnh,
SHA256 `f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df`.

### 2.6 `tools/data/data_viz.py`

| Chế độ | Cờ | Ra |
| --- | --- | --- |
| Một/nhiều mesh | `L terrain` | `generated/data_viz/<tên>.png` |
| Tất cả | `--all` | 10 ảnh |
| So sánh scene | `--scene` | `<tên>-compare.png`: scene chuẩn hoá bên trái, bề mặt bên phải |
| Cửa sổ 3D | `--show` | Không ghi PNG |

Đọc `.off` bằng `lib/mesh_off.py: read_off`; nếu có
`data/expected/<tên>.paths.json` thì vẽ đè các đường tham chiếu màu đỏ
(`read_paths` trong cùng file). Vẽ bằng `plot_trisurf` + `Poly3DCollection`,
`--scene-triangles N` giới hạn số tam giác của scene khi so sánh.

### 2.7 `tools/data/set_start_goal.py`

| | |
| --- | --- |
| Vào | Một `.off` (mặc định bề mặt thành phố) + lựa chọn của người dùng |
| Ra | `data/processed/missions/<mesh>.json` |
| Cờ | `--mesh`, `--mission`, `--output`, `--list-meshes`, `--all-meshes`, `--start[-vertex]`, `--goal[-vertex]`, `--all-goals`, `--pick`, `--snap`, `--max-snap`, `--force` |

Quy trình:

1. Đọc mesh bằng `Mesh` (kiểm đỉnh trùng, mặt suy biến, cạnh >2 mặt).
2. In kích thước, số cạnh biên, bước lưới, bounds; nếu ≤200 đỉnh thì in bảng.
3. Lấy lựa chọn theo thứ tự: **JSON đã lưu → tham số CLI → hỏi terminal**
   (`/dev/tty` nếu stdout bị pipe) hoặc `--pick` (cửa sổ 3D).
4. Snap toạ độ về đỉnh gần nhất (XY hoặc 3D), chặn nếu quá `--max-snap`
   (mặc định nửa đường chéo ô).
5. Ghi JSON: `mesh`, `mesh_sha256`, số đỉnh/mặt/cạnh biên, `vertex_spacing`,
   `snap_mode`, `max_snap`, `mode` (`explicit`/`all-goals`), `selected_by`,
   `start`, `goals`.

`all-goals` chỉ dùng cho mesh ≤300 đỉnh. File JSON là **đầu vào được commit**;
lần chạy sau chỉ đọc lại, `--force` để chọn lại.

## 3. Stage `plan`

### 3.1 `tools/plan/run_funnel.py`

| | |
| --- | --- |
| Vào | `data/processed/missions/*.json` + mesh trong mission |
| Ra | `generated/routes/<mission>.json` |
| Cờ | `--mission`, `--input`, `--output`, `--seconds` (mặc định 300), `--max-nodes`, `--no-clipping` |

Quy trình:

1. Kiểm `mesh_sha256` và số đỉnh/mặt khớp mission; mesh đổi thì dừng.
2. Dựng `Mesh` từ OFF, chạy `solve_targets`.
3. Mission `explicit` có nhiều goal: chạy **mỗi goal một lượt** (frontier nhỏ
   hơn, nhanh hơn); một goal hoặc `all-goals`: một lượt chung.
4. Ghi JSON: mission/mesh/module hash, giới hạn, `stats`, `planning_seconds`,
   phiên bản Python/NumPy, và `routes[]` gồm `id`, `vertex`, `length`,
   `waypoints`.

Độ dài tuyến = tổng khoảng cách Euclid giữa các waypoint liên tiếp (đường trên
mặt, không phải chim bay).

### 3.2 `tools/plan/route_viz.py`

| | |
| --- | --- |
| Vào | `generated/routes/*.json` + mesh ghi trong file |
| Ra | `generated/routes/<mission>.png` |
| Cờ | `--routes` (lặp lại), `--input`, `--output`, `--max-routes` (60), `--show` |

Vẽ bề mặt (50% trong suốt), START, từng tuyến một màu, ngôi sao ở goal; chú
thích khi ≤12 tuyến. `--max-routes` giữ các tuyến **dài nhất**. Không tính lại
tuyến.

### 3.3 `tools/plan/compare.py`

| | |
| --- | --- |
| Vào | `data/expected/*.paths.json` + mesh tương ứng |
| Ra | `generated/compare/<mesh>.json`, `summary.json` |
| Cờ | `--expected`, `--meshes`, `--output`, `--seconds`, `--tolerance` (1e-4) |

Với từng file reference: chạy Funnel từ **`source` ghi trong reference** (không
phải START của mission), so độ dài từng đỉnh:

```
relative_error = |L_funnel − L_reference| / L_reference
```

Vượt `--tolerance` thì ghi vào `failures` và stage thoát khác 0. Mesh không có
file reference được liệt kê là `skipped`; dự án **không** cài thêm solver thứ
hai, nên các mesh đó chỉ có kết quả của Funnel, không có đối chiếu.

## 4. `algo/funnel_tree.py`

| Thành phần | Vai trò |
| --- | --- |
| `Funnel` | Một funnel: `p`, `q` (hai đầu), `x` (đỉnh đang xét), `sequence` (dải mặt), các độ dài/góc, `deleted`, `children` |
| `clip_children` | Procedure 2 của bài báo: so hai funnel, quyết định giữ nhánh nào (0 = trái, 1 = phải) |
| `seeds` | Khởi tạo funnel quanh đỉnh nguồn bằng cách đi vòng các tam giác kề; hỗ trợ fan biên |
| `propagate` | Lan truyền theo tầng mặt: mở rộng `sequence` sang mặt bên kia cạnh, cập nhật góc/góc lệch, cắt children, ghi nhận funnel hợp lệ |
| `reconstruct` | Trải dải mặt ra mặt phẳng, tìm đường thẳng từ nguồn tới đích, cắt các cạnh chung và quy đổi điểm cắt về 3D |
| `solve_targets` | Dijkstra trên các **secondary source** (đỉnh có tổng góc > 2π, hoặc > π ở biên) để xử lý mặt lõm; chỉ dựng đường cho các đỉnh được hỏi |
| `solve` | `solve_targets` cho mọi đỉnh, trả danh sách theo chỉ số |

Chi tiết `solve_targets`:

1. Ứng viên source = đỉnh nguồn + mọi đỉnh có tổng góc vượt ngưỡng (ngưỡng
   `2π` trong mặt, `π` ở biên, sai số `1e-5`).
2. Hàng đợi ưu tiên `cost + ||p_s − goal gần nhất||` (Euclid, admissible).
3. Mỗi source được settle một lần; `propagate` chỉ dựng funnel cho **goal** và
   các source còn có thể cải thiện, lọc bằng cận dưới
   `cost + |v−s| + |s−goal| < best`.
4. Cập nhật `best[goal]`, lưu `previous[goal] = (source, funnel)`; dừng khi
   `min(queue) ≥ max(best)`.
5. Dựng lại đường bằng cách nối chuỗi `previous` (mỗi chặng một `reconstruct`).

Giới hạn: `timeout` (mặc định 300 s) và `max_nodes` (200.000) cho mỗi lần gọi;
vượt thì `TimeoutError`. Thuật toán tự kiểm tra độ dài dựng lại khớp khoảng cách
nội tại (`1e-6` tương đối) và báo lỗi nếu lệch.

Trạng thái: **experimental** — đã đối chiếu 5 fixture với reference (xem mục 6),
nhưng chưa có chứng nhận tối ưu và chưa kiểm chứng độc lập rằng tuyến nằm trên
mặt cho các mesh không có reference.

## 5. `lib/`

| File | Nội dung |
| --- | --- |
| `mesh_glb.py` | `read_glb`, `write_glb`, `indexed_from_triangles`: container GLB 2 (header, chunk JSON/BIN, accessor, bufferView) |
| `mesh_off.py` | `read_off`, `write_off`, `inspect_mesh`, `unique_edge_count`, `Point`, `Mesh`, `read_mesh` |
| `plotting.py` | `use_interactive`, `unavailable_message`: chọn backend Matplotlib, báo rõ khi thiếu |

`Mesh` tính sẵn `vertex_faces`, `edge_faces` và cung cấp `distance`, `angle`,
`other_face`, `third_vertex`, `stats`; thuật toán chỉ làm việc với cấu trúc này,
không đọc file.

## 6. Số liệu hiện tại

| Hạng mục | Giá trị |
| --- | --- |
| Bề mặt thành phố | 2.295 đỉnh / 4.400 tam giác / 6.694 cạnh |
| Route city | 133,71 m; 284,08 m; 140,57 m (START 182 → 1275, 2112, 1147) |
| Thời gian `main.py plan` | ~3 phút 20 giây (city chiếm ~190 s) |
| Đối chiếu reference | 5/5 fixture, sai lệch lớn nhất 1,7e-5 (reference làm tròn 4 chữ số) |

## 7. Tái lập

- Mỗi route ghi SHA256 của mesh, mission và `algo/funnel_tree.py`; sửa mã hoặc
  đổi mesh là hash đổi.
- `planning_seconds` là số đo thực, nên chạy lại `plan` sẽ làm JSON thay đổi.
  `compare` không chứa thời gian nên tất định.
- `data` phải tái tạo đúng byte bề mặt; nếu khác, ghi SHA cũ/mới và lý do trong
  [`../data/processed/README.md`](../data/processed/README.md).
- Phiên bản Python/NumPy được ghi trong mỗi route; tham số bề mặt in ra console
  và chép ở `data/processed/README.md`.
- `generated/routes/**` và `generated/compare/**` được commit; phần còn lại của
  `generated/` chỉ để xem lại.
