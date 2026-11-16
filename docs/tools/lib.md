# `lib/` — thư viện dùng chung

Ba module, không phải package: import theo tên sau khi thêm `lib/` vào
`sys.path`.

## `mesh_glb.py` — container GLB

| Hàm | Việc |
| --- | --- |
| `read_glb(path)` | Đọc file **do repo ghi**: mỗi node có đúng một mesh, một primitive, không transform; trả `[(tên, vertices, faces)]` |
| `write_glb(path, meshes, extras, generator)` | Ghi GLB 2: header, chunk JSON, chunk BIN, mỗi mesh một node, accessor `VEC3`+`SCALAR`, `mode` tam giác |
| `indexed_from_triangles(soup)` | Gộp tam giác rời thành lưới có chỉ số (đỉnh trùng theo giá trị float) |

Chi tiết định dạng:

- Header 12 byte: `glTF`, version 2, tổng độ dài.
- Chunk JSON (`0x4E4F534A`) + chunk BIN (`0x004E4942`), pad 4 byte.
- `write_glb` kiểm `vertices` là `N×3`, `faces` là `M×3`, chỉ số trong phạm vi.
- Toạ độ ghi **float32**; chỉ số `u4`.

`read_glb` không xử lý scene graph, không áp transform — đó là việc của
`tools/data/glb2off.py: iter_scene_meshes`. Nó cũng không đọc primitive thứ hai
của một mesh; đủ cho file repo tự ghi.

## `mesh_off.py` — định dạng OFF + cấu trúc Mesh

| Thành phần | Việc |
| --- | --- |
| `read_off(path)` | Parse `OFF`, header `V F E`, đỉnh, mặt tam giác; kiểm số dòng, chỉ số, toạ độ hữu hạn |
| `write_off(path, points, faces, edges=None)` | Ghi `%.17g`, header có số cạnh thật; trả số cạnh |
| `unique_edge_count(faces)` | Đếm cạnh không định hướng duy nhất |
| `inspect_mesh(points, faces)` | Trả thống kê topology **không** ném lỗi |
| `Point` | `x`, `y`, `z`, `distance` |
| `Mesh` | `points`, `faces`, `vertex_faces`, `edge_faces`, `distance`, `angle`, `other_face`, `third_vertex`, `stats`; kiểm đỉnh trùng, mặt suy biến, cạnh >2 mặt, đỉnh rỗng |
| `read_mesh(path)` | `read_off` + `Mesh` |

`Mesh.stats` gồm: `vertices`, `triangles`, `edges`, `boundary_edges`,
`nonmanifold_edges`, `bad_boundary_vertices`, `disconnected_vertex_fans`,
`degenerate_triangles`, `area`.

`inspect_mesh` cố tình không ném lỗi để `triangulation` tự quyết định; `Mesh`
thì ném lỗi vì thuật toán cần mesh hợp lệ.

## `plotting.py` — chọn backend

| Hàm | Việc |
| --- | --- |
| `use_interactive()` | Trả tên backend đồ hoạ (QtAgg, TkAgg, Qt5Agg, GTK3Agg) hoặc `None` |
| `unavailable_message()` | Câu thông báo nêu cách cài (apt.txt cho Debian/Ubuntu, `steam-run` cho NixOS) |

Matplotlib lặng lẽ rơi về `Agg` khi không nạp được toolkit, và `plt.show()` sau
đó không làm gì. `use_interactive` gọi `matplotlib.use(..., force=True)` trước
khi import `pyplot`, và trả `None` nếu không backend nào nạp được.

Dùng ở: `data_viz --show`, `route_viz --show`, `set_start_goal --pick`.
