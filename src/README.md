# Mã nguồn dùng chung

Hai module. Đây **không phải package**: không có `__init__.py`, các module được
import trực tiếp theo tên (`from glb import write_glb`) sau khi chương trình
thêm `src/` vào `sys.path`. Tool mới dùng `src/` cần thêm cùng một dòng.

| Module | Vai trò | Import nội bộ |
| --- | --- | --- |
| `funnel_tree.py` | `seeds`, `propagate`, `reconstruct`, `solve`, `clip_children`: lan truyền Funnel và dựng lại tuyến | — (chỉ NumPy) |
| `glb.py` | `read_glb`, `write_glb`, `indexed_from_triangles`: container GLB 2 | — (chỉ stdlib + NumPy) |

## Trạng thái sử dụng

`glb.py` được `tools/data/standardize.py` và `tools/data/off2glb.py` dùng.
`funnel_tree.py` **chưa tool nào import**: `set_start_goal.py` chỉ chọn điểm,
không chạy Funnel, nên phần lõi này đang chờ tool lập tuyến.

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

Không còn lớp `Mesh` dùng chung trong repo. Tool lập tuyến (chưa có) phải tự
dựng đối tượng thoả giao diện trên, ví dụ từ reader OFF trong
`tools/data/set_start_goal.py`, nơi đã có sẵn phần kiểm tra topology: đỉnh trùng
toạ độ, mặt suy biến, cạnh kề hơn hai mặt.

## Chữ ký phụ thuộc mã nguồn

Chưa tool nào ghi chữ ký mã nguồn vào kết quả. Khi thêm tool lập tuyến, hãy ghi
SHA256 của `funnel_tree.py` và chính tool đó vào JSON kết quả: sửa mã phải làm
chữ ký đổi, để tuyến đã lưu không bị hiểu nhầm là do mã hiện tại sinh ra.
