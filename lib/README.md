# Mã nguồn dùng chung

Hai module. Đây **không phải package**: không có `__init__.py`, các module được
import trực tiếp theo tên (`from mesh_glb import write_glb`) sau khi chương trình
thêm `lib/` vào `sys.path`. Tool mới dùng `lib/` cần thêm cùng một dòng.

| Module | Vai trò | Import nội bộ |
| --- | --- | --- |
| `mesh_glb.py` | `read_glb`, `write_glb`, `indexed_from_triangles`: container GLB 2 | — (chỉ stdlib + NumPy) |
| `mesh_off.py` | `read_off`, `write_off`, `inspect_mesh`, `unique_edge_count` và lớp `Point`/`Mesh` | — (chỉ stdlib + NumPy) |

Lớp `Mesh` trong `mesh_off.py` là cấu trúc dữ liệu thuật toán đi trên: `points`,
`faces`, `vertex_faces`, `edge_faces`, `distance`, `angle`, `other_face`,
`third_vertex`, `stats`. Nó dựng từ mảng, không biết file.

## Trạng thái sử dụng

`mesh_glb.py` được `tools/data/standardize.py` và `tools/data/off2glb.py` dùng;
`mesh_off.py` là reader/writer OFF duy nhất, dùng ở sáu tool của stage `data` và
cả ba tool của stage `plan`. Thuật toán Funnel nằm ở `algo/funnel_tree.py`.

## Chữ ký phụ thuộc mã nguồn

`tools/plan/run_funnel.py` ghi SHA256 của `algo/funnel_tree.py`, của mission và
của mesh vào mỗi file route. Sửa thuật toán là hash đổi, nên một route đã lưu
không thể bị hiểu nhầm là do mã hiện tại sinh ra.
