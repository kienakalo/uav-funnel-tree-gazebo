---
title: funnel_tree.py
aliases:
  - funnel_tree
  - Funnel Tree
type: algorithm
stage: plan
source: algo/funnel_tree.py
tags:
  - funnel-tree/algorithm
  - funnel-tree/stage/plan
---

# `algo/funnel_tree.py`

> [!abstract] Mục đích
> Cài đặt **Funnel Tree** trên mặt đa diện tam giác: lan truyền cosine cục bộ
> theo tầng mặt, cắt nhánh bằng Procedure 2, rồi chỉ trải dải mặt đã chọn để lấy
> đường ngắn nhất.

> [!info] Vị trí
> **File** `algo/funnel_tree.py` — thư viện thuật toán, stage `plan` gọi qua `run_funnel`  
> **Vào** một `Mesh` (không đọc file) + đỉnh nguồn (+ tập đích nếu có)  
> **Ra** `paths` — danh sách đường 3D theo chỉ số đỉnh — và `stats`  
> **Phụ thuộc** NumPy, stdlib · **Trạng thái** experimental, chưa chứng nhận tối ưu  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `angle_sides(a, b, opposite)` | ba cạnh | góc (radian) | Định luật cosin, góc đối diện cạnh `opposite` |
| `cosine_side(a, b, angle)` | hai cạnh + góc xen giữa | cạnh thứ ba | Định luật cosin |
| `clip_children(length_a, angle_a, length_b, angle_b, tolerance=1e-10)` | độ dài và góc hai nhánh | `(funnel, child)`, `0 = trái`, `1 = phải` | Procedure 2: quyết định giữ nhánh nào |
| `seeds(mesh, source)` | mesh + đỉnh nguồn | danh sách `Funnel` | Đi vòng fan tam giác quanh nguồn; fan không liên thông → `ValueError` |
| `propagate(mesh, source, deadline, max_nodes, clipping=True, target_vertices=None)` | mesh, nguồn, hạn thời gian/node | funnel ứng viên cho từng đích | Lan truyền qua cạnh `(x, q)`, cắt nhánh, tự kiểm bằng `reconstruct` |
| `reconstruct(mesh, source, funnel, deadline=None)` | một funnel | polyline 3D | Trải dải mặt ra 2D, cắt đường thẳng với từng cạnh chung |
| `solve_targets(mesh, source, targets, timeout=20.0, max_nodes=200000, clipping=True)` | mesh, nguồn, tập đích | `(paths, stats)` | Dijkstra trên các secondary source, mỗi source `propagate` một lần |
| `solve(mesh, source, timeout=20.0, max_nodes=200000, clipping=True)` | mesh + nguồn | `paths` cho **mọi** đỉnh | Gọi `solve_targets` với toàn bộ đỉnh, dùng cho mesh nhỏ |
| `trace_path(...)` | `previous`, `cache` | đường tới một đỉnh | Nối chuỗi source đã settle |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy | Toạ độ, độ dài, góc |
| Thư viện | `dataclasses`, `heapq`, `math`, `time` | `Funnel`, hàng đợi ưu tiên, hạn thời gian |
| Nội bộ | `lib/mesh_off.py: Mesh` | Kề mặt/cạnh, `distance`, `angle`, `other_face` |
| Được gọi bởi | `tools/plan/run_funnel.py: solve_targets`, `tools/plan/compare.py: solve` | Lập tuyến và đối chiếu reference |

## Mô hình dữ liệu

`Funnel` (dataclass) đại diện một "phễu" mở từ nguồn qua dải mặt:

| Trường | Ý nghĩa |
| --- | --- |
| `p`, `q` | hai đỉnh biên của phễu tại mặt hiện tại |
| `x` | đỉnh đang được xét (đầu nhọn) |
| `sequence` | dãy mặt đã đi qua |
| `sp`, `pq`, `spq`, `psw`, `pqv` | độ dài và góc dùng cho phép cắt |
| `deleted`, `children` | trạng thái sau khi bị Procedure 2 loại |

## `seeds`

Đi vòng các tam giác kề đỉnh nguồn theo một fan liên thông (hỗ trợ fan biên),
tạo một `Funnel` cho mỗi tam giác với các độ dài/góc ban đầu. Nếu các tam giác
kề không tạo thành một fan → `ValueError`.

## `propagate`

1. Với mỗi phễu ở tầng hiện tại, đi sang mặt bên kia cạnh `(x, q)`.
2. Cập nhật góc tích luỹ `pqv`, tính `vq`, `pv` (cosine rule) và góc `vpq`; nếu
   `pqv > π` thì đổi dấu `vpq`.
3. `beta = spq + vpq`; nếu `beta ≥ π` thì đỉnh `x` tiến lên `v` và tiếp tục.
4. Nếu không, tính `sv` và so với phễu hiện tại; gọi `clip_children` để quyết
   định giữ nhánh nào, đánh dấu `deleted` cho nhánh bị loại.
5. Ghi lại funnel ứng viên cho từng đích; cuối cùng kiểm tra từng ứng viên bằng
   `reconstruct`: độ dài dựng lại phải khớp `sp` trong `1e-6` tương đối, nếu
   không thì loại.
6. `target_vertices` (tùy chọn) giới hạn việc dựng lại cho một tập đích — dùng
   để tăng tốc; khoảng cách của đỉnh ngoài tập vẫn có thể `inf`.

`clip_children` (Procedure 2):

```
da = angle_a − angle_b
dl = length_a − length_b
nếu |da| ≤ tol        → giữ cả hai
nếu dl < −eps         → giữ B (trái/phải theo dấu da)
nếu dl > +eps         → giữ A
còn lại               → giữ cả hai
```

## `reconstruct`

1. Trải tam giác đầu của `sequence` ra mặt phẳng 2D bằng các độ dài thật.
2. Với từng mặt kế tiếp: tìm cạnh chung, dựng đỉnh mới trong 2D bằng cosine
   rule và chọn phía theo đỉnh cũ (giữ hướng trải).
3. Khi đã có toạ độ 2D của nguồn và đích, lấy đường thẳng giữa chúng.
4. Cắt đường thẳng với từng cạnh chung, tham số `r ∈ [0,1]`, quy đổi điểm cắt về
   3D bằng nội suy trên cạnh thật.
5. Trả polyline 3D gồm nguồn, các điểm cắt, đích.

Nếu đường thẳng ra ngoài dải mặt (`r` ngoài `[0,1]`) → `ValueError`.

## `solve_targets`

1. **Ứng viên secondary source**: nguồn + mọi đỉnh có tổng góc vượt ngưỡng
   (`2π` trong mặt, `π` ở biên, sai số `1e-5`). Trên bề mặt thành phố: **646**
   đỉnh.
2. **Dijkstra trên đồ thị source** với ưu tiên `cost + ||p_s − goal gần nhất||`
   (Euclid, admissible).
3. Khi settle một source: `propagate` với phạm vi = các goal + các source còn
   "hữu ích", lọc bằng cận dưới:

   ```
   cost + |v − s| + |s − goal| < best[goal]
   ```

   Nhờ đó không phải dựng funnel cho cả 646 source mỗi lần.
4. Cập nhật `best`, `previous`; dừng khi `min(queue) ≥ max(best)`.
5. Dựng lại bằng cách nối chuỗi `previous`, mỗi chặng một `reconstruct`.

## Độ phức tạp và giới hạn

- `timeout` và `max_nodes` là tham số bắt buộc của `propagate` (mỗi lần gọi).
- Vượt thời gian → `TimeoutError`; vượt số node → `RuntimeError`.
- Số lần lan truyền là số đo hiệu năng: `stats.propagations` là tổng của cả
  mission, `routes[].search.propagations` là của từng goal.

Đo trên bề mặt thành phố ở hai độ mịn, cùng mission và cùng bộ tham số solver:

| Bề mặt | Goal | Lan truyền | Thời gian | Độ dài |
| --- | --- | --- | --- | --- |
| 2.295 đỉnh (lưới 5 m) | 1810 | 49 | 19,6 s | 142,42 m |
| | 1910 | 34 | 14,8 s | 125,64 m |
| | 1518 | 21 | 10,6 s | 86,15 m |
| 3.355 đỉnh (lưới 4 m) | 2708 | 81 | 70,5 s | 142,91 m |
| | 2829 | 66 | 64,5 s | 127,30 m |
| | 2240 | 40 | 51,2 s | 86,19 m |

Lưới 4 m có 1,47 lần số tam giác nhưng cần 1,8 lần số lần lan truyền và 4,1 lần
thời gian (187 so với 104 lần, 186,2 so với 45,0 s). Số đọc từ
`results/runs/cell4/routes.json` và `results/runs/city792e/routes.json`.

Thời gian phụ thuộc tải máy, không phải chỉ số của thuật toán: cùng mission và
cùng mã, hai lần đo khác nhau có thể lệch vài chục phần trăm. Kết luận về thuật
toán dựa vào **số lần lan truyền và độ dài**, không dựa vào giây.

## Kiểm chứng

- Tự kiểm: độ dài dựng lại khớp khoảng cách nội tại trong `1e-6` tương đối.
- Ngoài: 5 fixture khớp reference `data/expected` (sai lệch ≤1,7e-5, xem
  [`compare.md`](plan/compare.md)).
- **Chưa** chứng nhận tối ưu và **chưa** kiểm tra độc lập tuyến nằm trên mặt cho
  mesh không có reference.

## Ví dụ dùng như thư viện

```python
import sys
sys.path.insert(0, 'lib'); sys.path.insert(0, 'algo')
from mesh_off import read_mesh
from funnel_tree import solve_targets

mesh = read_mesh('data/processed/meshes/cliff.off')
paths, stats = solve_targets(mesh, 1, [0, 5], timeout=60)
print(paths[0], stats['propagations'])
```

## Liên quan

- [`lib.md`](lib.md) — `Mesh` và các phép topology thuật toán dựa vào.
- [`plan/run_funnel.md`](plan/run_funnel.md) — nơi `solve_targets` được gọi.
- [`plan/compare.md`](plan/compare.md) — bằng chứng ngoài trên 5 fixture.
- [`reproducibility.md`](reproducibility.md) — số đo hiệu năng và giới hạn.
