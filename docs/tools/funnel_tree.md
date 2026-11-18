# `algo/funnel_tree.py`

| | |
| --- | --- |
| Vai trò | Thuật toán Funnel Tree trên mặt đa diện |
| Vào | một `Mesh` (không đọc file) + đỉnh nguồn |
| Ra | `paths` (danh sách đường 3D) và `stats` |
| Phụ thuộc | NumPy, stdlib |
| Trạng thái | **experimental** — chưa chứng nhận tối ưu |

## Mô hình dữ liệu

`Funnel` (dataclass) đại diện một "phễu" mở từ nguồn qua dải mặt:

| Trường | Ý nghĩa |
| --- | --- |
| `p`, `q` | hai đỉnh biên của phễu tại mặt hiện tại |
| `x` | đỉnh đang được xét (đầu nhọn) |
| `sequence` | dãy mặt đã đi qua |
| `sp`, `pq`, `spq`, `psw`, `pqv` | độ dài và góc dùng cho phép cắt |
| `deleted`, `children` | trạng thái sau khi bị Procedure 2 loại |

## API

| Hàm | Việc |
| --- | --- |
| `angle_sides(a, b, c)` | góc đối diện cạnh `c` (định luật cos) |
| `cosine_side(a, b, angle)` | cạnh thứ ba từ hai cạnh và góc xen giữa |
| `clip_children` | Procedure 2: quyết định giữ nhánh trái/phải/cả hai |
| `seeds(mesh, source)` | khởi tạo phễu quanh đỉnh nguồn |
| `propagate(mesh, source, deadline, max_nodes, clipping, target_vertices)` | lan truyền theo tầng mặt |
| `reconstruct(mesh, source, funnel, deadline)` | dựng lại đường từ một phễu |
| `solve_targets(mesh, source, targets, timeout, max_nodes, clipping)` | tìm đường tới các đỉnh được hỏi |
| `solve(mesh, source, …)` | `solve_targets` cho mọi đỉnh |

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

Đo trên bề mặt thành phố 2.295 đỉnh, mission START 792 (ba goal của thí nghiệm
3 goal trong repo cũ):

| Goal | Số lần lan truyền | Thời gian | Độ dài |
| --- | --- | --- | --- |
| 1810 | 49 | 27,5 s | 142,42 m |
| 1910 | 34 | 20,2 s | 125,64 m |
| 1518 | 21 | 14,5 s | 86,15 m |

Số đọc từ `results/runs/city792/route.json` (tên cũ của archive lưu trước
18/11/2026; bản sao của `generated/routes/city.standardized.triangulation.routes.json`
lúc lưu): tổng 104 lần lan truyền, 646 source, cả ba goal 62,3 s.

Thời gian phụ thuộc tải máy, không phải chỉ số của thuật toán: cùng mission này
lần khác đo 77,2 s và 88,9 s, từng goal lệch tới 40 % (g1: 27,5 s và 39,3 s);
mission cũ dài hơn đo 188 s (`cell5`) và 295 s (`cell5b`). Kết luận về thuật
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
