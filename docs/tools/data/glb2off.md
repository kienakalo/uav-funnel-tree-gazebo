# `glb2off.py`

| | |
| --- | --- |
| Stage | `data` bước 4 (dùng gián tiếp) — cũng là tool độc lập |
| Vào | GLB 2 bất kỳ (mặc định `data/processed/scenes/city.standardized.glb`) |
| Ra | `data/processed/meshes/<stem>.glb2off.off` |
| Cờ | `--output`, `--width` (200), `--force` |
| Được import bởi | `triangulation.py`, `data_viz.py`, `standardize.py` |

## Vai trò kép

1. **Thư viện đọc scene**: hàm `read_glb_scene` trả toàn bộ tam giác ở hệ của dự
   án (Z-up, rộng 200 m), dùng cho `triangulation`.
2. **Tool chuyển đổi**: ghi ra `.off` để xem hoặc kiểm tra bằng công cụ khác.

## Các tầng xử lý

| Hàm | Việc |
| --- | --- |
| `read_document` | Tách header 12 byte, chunk JSON (`0x4E4F534A`), chunk BIN (`0x004E4942`); từ chối file không phải GLB 2 hoặc thiếu chunk |
| `_accessor` | Đọc accessor thành mảng NumPy; hỗ trợ `u1/u2/u4/f4`, `SCALAR/VEC2/VEC3/VEC4`; từ chối sparse |
| `_node_matrix` | Dựng ma trận 4×4 cục bộ: `matrix` có sẵn, hoặc ghép `rotation` (quaternion) × `scale` + `translation` |
| `iter_scene_meshes` | Duyệt cây node, `M = parent × local`, trả `(tên node, vertices, faces)` ở **world**, giữ trục/đơn vị gốc |
| `transformed_objects` | Như trên nhưng trả **triangle soup** (`vertices[faces]`) — dùng cho `standardize` |
| `read_glb_scene` | Gộp mọi node, đổi trục và chuẩn hoá (dưới đây) |

## Chuẩn hoá

Sau khi đổi trục:

```
(x, y, z)_glTF → (x, z, −y)_Z-up

low, high  = min/max theo từng trục
scale      = width / max(high.x − low.x, high.y − low.y)
origin     = ((low.x + high.x)/2, (low.y + high.y)/2, low.z)
vertices   = (vertices − origin) × scale
```

- `width` mặc định 200 m, đặt bằng `--width`.
- Trục lớn hơn của XY quyết định tỉ lệ; z giữ tỉ lệ theo.
- Đáy (z nhỏ nhất) về 0.

## Đầu ra OFF

- Ghi bằng `lib/mesh_off.py: write_off` với `%.17g`.
- Số cạnh trong header là số cạnh **thật** (đếm unique), không khai báo.
- Tool tự kiểm số dòng = `2 + V + F`.

Với `city.standardized.glb`:

```
Input:  204682 vertices, 301490 triangles
Bounds: x [-100.00, 100.00] y [-87.78, 87.78] z [0.00, 18.54]
Output: 498767 edges, 18.3 MB
```

## Đặc điểm cần nói khi báo cáo

- **Không weld** đỉnh giữa các primitive: vết nối của scene gốc vẫn còn, nên số
  đỉnh (204.682) lớn hơn số đỉnh của một lưới weld.
- **Không sửa hình học**: chỉ bake transform, đổi trục, chuẩn hoá.
- Bản OFF này chỉ dùng để xem/đối chiếu, **không** phải đầu vào của thuật toán
  (đầu vào là bề mặt tam giác phân).

## Giới hạn

- Chỉ primitive tam giác, không Draco, không sparse, không buffer ngoài.
- Không đọc material/texture/camera/animation.
- Kết quả nằm cạnh các mesh đã xử lý và **được commit** (18 MB với city).
