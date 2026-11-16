# Mã nguồn dùng chung

Ba module. Đây **không phải package**: không có `__init__.py`, các module được
import trực tiếp theo tên (`from funnel_tree import propagate`) sau khi chương
trình thêm `src/` vào `sys.path`. Mọi tool đều làm việc này; tool mới cần thêm
cùng một dòng.

| Module | Vai trò | Import nội bộ |
| --- | --- | --- |
| `funnel_tree.py` | `seeds`, `propagate`, `reconstruct`, `solve`, `clip_children`: lan truyền Funnel và dựng lại tuyến | — (chỉ NumPy) |
| `verification.py` | `read_paths`, `path_length`, `edge_distances`, `segment_on_mesh`: kiểm tra đường đi | — (chỉ stdlib) |
| `glb.py` | `read_glb`, `write_glb`, `indexed_from_triangles`: container GLB 2 | — (chỉ stdlib + NumPy) |

## Giao diện `Mesh`

`funnel_tree.py` không import lớp mesh nào. Nó chỉ gọi các thuộc tính và phương
thức sau của đối tượng truyền vào:

```text
points            danh sách đỉnh, mỗi đỉnh có .x .y .z
faces             danh sách tam giác (a, b, c)
vertex_faces[v]   các mặt chứa đỉnh v
edge_faces[(a,b)] các mặt chứa cạnh đã sắp xếp (a, b)
other_face(a, b, f)
third_vertex(f, a, b)
distance(a, b)
angle(a, b, c)
```

Hiện `tools/set_start_goal.py` cung cấp lớp `Point`/`Mesh` đó, kèm reader OFF
và kiểm tra topology (đỉnh trùng, mặt suy biến, cạnh kề hơn hai mặt). Đổi tên
hoặc bỏ một thuộc tính của `Mesh` sẽ làm hỏng `funnel_tree.py` dù không có lỗi
import.

## Chữ ký phụ thuộc mã nguồn

`tools/set_start_goal.py` băm `src/funnel_tree.py`, `src/verification.py` và
chính nó để tạo chữ ký cache (`generated/missions/<tên>/plan.json` →
`input_sha256`). Sửa một trong ba tệp sẽ đổi chữ ký, cache cũ bị bỏ và lần chạy
sau lan truyền lại từ đầu. Đây là hành vi mong muốn: tuyến phải tương ứng với
đúng mã đã sinh ra nó.
