---
title: triangulation.py
aliases:
  - triangulation
type: tool
stage: data
source: tools/data/triangulation.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/data
---

# `triangulation.py`

> [!abstract] Mục đích
> Dựng **bề mặt dẫn đường** liên tục phía trên thành phố: mỗi ô lưới cao hơn
> mọi công trình bên dưới ít nhất `CLEARANCE`, rồi hạ dần thành ramp theo độ dốc
> giới hạn. Đây là envelope an toàn, không phải địa hình thật.

> [!info] Vị trí
> **File** `tools/data/triangulation.py` — stage `data`, bước 5  
> **Thuật toán** Lưới ô 5 m + truy vấn STRtree cho độ cao yêu cầu, lan truyền ramp bằng max-heap, kiểm topology và cột đứng  
> **Vào** `data/processed/scenes/city.standardized.glb` + START/GOAL  
> **Ra** `data/processed/meshes/city.standardized.triangulation.off` + `…params.json`  
> **Cờ** `--scene`, `--start X Y Z`, `--goal X Y Z`, `--cell` (5), `--clearance` (1,5), `--half-width` (1,6), `--max-slope` (0,5), `--coverage {city,mission}`, `--output`, `--force`  
> **Cần** NumPy, Shapely · **Hằng số** `CLEARANCE = 1.5`, `HALF_WIDTH = 1.6`, `MAX_AXIS_SLOPE = 0.5`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `build_surface(triangles, start, goal, step, coverage='city', clearance=1.5, half_width=1.6, max_slope=0.5)` | tam giác thành phố `(F, 3, 3)`, hai điểm 3D, cạnh ô, tham số envelope | `(points, faces, source, target, stats)` — lưới Z-up, chỉ số đỉnh START/GOAL, thống kê topology | Dựng lưới, tính độ cao yêu cầu bằng STRtree, lan truyền ramp bằng max-heap, kiểm cột đứng và topology |
| `sha256(path)` | đường dẫn | hex digest | Ghi hash scene/script vào sidecar |
| `relative(path)` | đường dẫn | đường dẫn tương đối repo | In và ghi sidecar gọn |
| `main()` | cờ dòng lệnh | `.off` + `.params.json`, in tham số và kết quả | Đọc scene, gọi `build_surface`, `write_off`, tự kiểm rồi ghi sidecar |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy, Shapely (`polygons`, `box`, `STRtree`) | Mảng lưới, truy vấn tam giác giao hộp 2D |
| Thư viện | `heapq`, `math`, `argparse`, `hashlib`, `json` | Lan truyền ramp, CLI, sidecar |
| Nội bộ | `tools/data/glb2off.py: read_glb_scene` | Tam giác thành phố ở Z-up, rộng 200 m |
| Nội bộ | `lib/mesh_off.py: write_off, inspect_mesh` | Ghi bề mặt và kiểm topology |
| Dữ liệu | START/GOAL mặc định | Hai đầu nhiệm vụ giao hàng; x/y chèn vào lưới |

Đây là bước biến "thành phố rời rạc" thành **một mặt liên tục** mà Funnel Tree
đi được.

## Ý tưởng

Không đi trên mái nhà hay mặt đất: dựng một **envelope an toàn** phía trên thành
phố. Mỗi ô lưới phải cao hơn mọi tam giác công trình bên dưới nó ít nhất
`CLEARANCE`; sau đó hạ dần độ cao sang ô bên cạnh theo độ dốc giới hạn để tạo
đường lên/xuống.

## Các bước

### 1. Đọc tam giác thành phố

```python
vertices, faces = read_glb_scene(scene_path, 200.)   # Z-up, rộng 200 m
triangles = vertices[faces]                          # (F, 3, 3)
```

### 2. Dựng lưới ô

```python
extent  = mọi đỉnh tam giác (XY) ∪ {start.xy, goal.xy}
min_x   = floor((min_x − 16) / cell) * cell
max_x   = ceil ((max_x + 16) / cell) * cell
xs      = unique(arange(min_x, max_x + cell/2, cell) ∪ {start.x, goal.x})
ys      = ...
```

- Nới 16 m mỗi phía để envelope phủ trọn thành phố.
- Luôn chèn toạ độ START/GOAL để hai điểm nằm **đúng trên đỉnh lưới**.

### 3. Độ cao yêu cầu cho từng ô

Với ô `(i, j)`, lấy hộp 2D nới `HALF_WIDTH` mỗi phía:

```python
box = (xs[i]−1.6, ys[j]−1.6, xs[i+1]+1.6, ys[j+1]+1.6)
ids = STRtree.query(box)                     # các tam giác giao hộp
required[i, j] = max(z của các tam giác đó) + 1.5
```

Ô trống (không có tam giác) lấy `1.5`. `HALF_WIDTH` đảm bảo không cắt sát mép
công trình khi bay qua.

### 4. Độ cao đỉnh lưới

```python
heights = full((len(xs), len(ys)), CLEARANCE)
for (di, dj) in [(0,0), (1,0), (0,1), (1,1)]:
    heights[di:..., dj:...] = maximum(..., required)
```

Mỗi đỉnh nhận `max` của tối đa 4 ô kề nó.

### 5. Lan truyền dốc (ramp)

Max-heap trên `heights`; mỗi bước lấy đỉnh cao nhất và hạ sang 4 hàng xóm:

```
h_hàng_xóm ≥ h_nguồn − 0.5 × khoảng_cách
```

Chỉ **nâng** độ cao, không hạ, nên envelope vẫn an toàn. `0.5` m/m ≈ 26,6°.

### 6. Kiểm tra và dựng mặt

- Mỗi ô: 4 đỉnh phải `≥ required − 1e-9`.
- 2 tam giác mỗi ô: `(a, b, c)` và `(b, d, c)` với
  `a = i·ny + j`, `b = a + ny`, `c = a + 1`, `d = a + ny + 1`.
- `inspect_mesh` (trong `lib/mesh_off.py`) kiểm: không cạnh non-manifold, không
  đỉnh có fan rời, không tam giác suy biến. Sai thì dừng.

### 7. Kiểm tra cột đứng START/GOAL

Hộp `HALF_WIDTH` quanh mỗi điểm không được giao tam giác thành phố trong khoảng
z giữa điểm vào và mặt envelope (±0,2 m). Nếu giao, envelope không có đường
xuống hợp lệ → dừng.

### 8. Ghi kết quả

`write_off` (17 chữ số), số cạnh thực, in tham số + kết quả:

```
Parameters: {"cell": 5.0, "coverage": "city", "vertical_clearance": 1.5,
             "horizontal_half_width": 1.6, "max_axis_slope": 0.5}
Result: {"vertices": 2295, "triangles": 4400, "edges": 6694,
         "surface_source": 792, "surface_target": 1810, "nonmanifold_edges": 0}
Save at: data/processed/meshes/city.standardized.triangulation.off
Save at: data/processed/meshes/city.standardized.triangulation.params.json
```

File `.params.json` là sidecar, ghi cùng chỗ với bề mặt:

```json
{
  "output": "data/processed/meshes/city.standardized.triangulation.off",
  "output_sha256": "f6e01c6d…",
  "script": "tools/data/triangulation.py",
  "script_sha256": "40f43570…",
  "scene": "data/processed/scenes/city.standardized.glb",
  "scene_sha256": "cdd605ee…",
  "parameters": {"cell": 5.0, "coverage": "city", "vertical_clearance": 1.5,
                 "horizontal_half_width": 1.6, "max_axis_slope": 0.5},
  "result": {"vertices": 2295, "triangles": 4400, "edges": 6694,
             "surface_source": 792, "surface_target": 1810,
             "nonmanifold_edges": 0}
}
```

Nhờ đó một bề mặt luôn truy được về tham số, scene và phiên bản script sinh ra
nó, kể cả khi tham số do người dùng nhập ở `main.py`. Không có dấu thời gian
nên chạy lại với cùng tham số cho ra cùng file.

## Tham số mặc định của bề mặt hiện tại

| Tham số | Giá trị | Ý nghĩa |
| --- | --- | --- |
| `cell` | 5 m | Cạnh ô lưới |
| `coverage` | `city` | Phủ toàn thành phố (không chỉ hành lang) |
| `CLEARANCE` | 1,5 m | Khe hở dọc tối thiểu trên công trình |
| `HALF_WIDTH` | 1,6 m | Nới ngang khi truy vấn tam giác |
| `MAX_AXIS_SLOPE` | 0,5 | Độ dốc tối đa khi mở ramp (m/m) |
| START/GOAL mặc định | `-38.7521 22.1034 7.2056` → `74.7366 -55.3572 7.2056` | Hai đầu nhiệm vụ giao hàng; x/y chèn vào lưới, z chỉ dùng cho bước kiểm tra cột đứng — mission lưu z của bề mặt (hiện `8.6430` và `8.9476`) |

## Kết quả

2.295 đỉnh, 4.400 tam giác, 6.694 cạnh,
SHA256 `f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df`.

## Chạy

```bash
.venv/bin/python tools/data/triangulation.py --force
.venv/bin/python tools/data/triangulation.py --cell 4 --clearance 2 --force
.venv/bin/python tools/data/triangulation.py --coverage mission --force
```

`--force` cần thiết vì `main.py` và lần chạy tay đều ghi đè bề mặt đã có.

## Giới hạn

- Mặt chỉ tồn tại trong vùng `extent`; ngoài đó không có gì để đi.
- Độ phân giải 5 m: khe giữa hai công trình hẹp hơn `cell` có thể bị lấp.
- Envelope là **xấp xỉ an toàn**, không phải mặt đường thật; mọi kết luận về
  đường bay phải nói rõ điều này.
- Không dùng STL trung gian: tam giác lấy trực tiếp từ GLB.

## Liên quan

- [`standardize.md`](standardize.md) — scene đầu vào của bước này.
- [`glb2off.md`](glb2off.md) — `read_glb_scene` và phép chuẩn hoá 200 m.
- [`set_start_goal.md`](set_start_goal.md) — chọn START/GOAL lưu thành mission.
- [`../funnel_tree.md`](../funnel_tree.md) — thuật toán chạy trên bề mặt này.
