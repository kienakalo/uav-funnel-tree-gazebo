---
title: glb2off.py
aliases:
  - glb2off
type: tool
stage: data
source: tools/data/glb2off.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/data
---

# `glb2off.py`

> [!abstract] Mục đích
> Đọc một scene GLB và xuất ra OFF: vừa là **thư viện đọc scene** cho
> `triangulation`, vừa là tool tạo **bản xem thành phố** cho báo cáo. Bản OFF này
> không phải đầu vào của thuật toán.

> [!info] Vị trí
> **File** `tools/data/glb2off.py` — stage `data`, bước 3 (bản xem cho báo cáo)  
> **Thuật toán** Duyệt cây node glTF, bake transform, đổi Y-up → Z-up, chuẩn hoá tâm XY và đáy `z = 0`  
> **Vào** GLB 2 bất kỳ (mặc định `data/processed/scenes/city.standardized.glb`)  
> **Ra** `data/processed/meshes/<stem>.glb2off.off` + `<stem>.params.json`  
> **Cờ** `--output`, `--width` (200), `--force`  
> **Được import bởi** `triangulation.py`, `data_viz.py`, `standardize.py`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `read_document(filename)` | đường dẫn GLB | `(document, binary)` | Tách header 12 byte, chunk JSON (`0x4E4F534A`), chunk BIN (`0x004E4942`); từ chối GLB 1 hoặc thiếu chunk |
| `_accessor(document, binary, index)` | JSON + BIN + chỉ số accessor | mảng NumPy | Hỗ trợ `u1/u2/u4/f4`, `SCALAR/VEC2/VEC3/VEC4`; từ chối sparse |
| `_node_matrix(node)` | một node glTF | ma trận 4×4 | Dùng `matrix` có sẵn, hoặc ghép `rotation` (quaternion) × `scale` + `translation` |
| `iter_scene_meshes(filename)` | đường dẫn GLB | generator `(tên, vertices, faces)` ở world | Duyệt cây node, `M = parent × local`; **giữ** trục và đơn vị gốc |
| `transformed_objects(filename)` | đường dẫn GLB | generator `(tên, triangle soup)` | Như trên nhưng trả `vertices[faces]`, dùng cho `standardize` |
| `read_glb_scene(filename, width)` | GLB + bề rộng mét | `(vertices, faces)` ở Z-up | Gộp mọi node, đổi `(x, y, z) → (x, z, −y)`, chuẩn hoá tâm XY và đưa đáy về `z = 0` |
| `main()` | `--output`, `--width`, `--force` | `.off` + `.params.json` | Gọi `read_glb_scene`, `write_off`, ghi sidecar tham số |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy; `argparse`, `json`, `struct`, `pathlib` | Đọc buffer nhị phân, CLI |
| Nội bộ | `lib/mesh_off.py: write_off` | Ghi OFF với `%.17g` và số cạnh thật |
| Nội bộ | `lib/figstamp.py: relative, sha256` | Đường dẫn tương đối và hash cho sidecar |
| Được gọi bởi | `standardize.py`, `triangulation.py`, `data_viz.py` | Dùng chung một chỗ duyệt cây node |

## Chạy

```bash
.venv/bin/python tools/data/glb2off.py                       # city, rộng 200 m
.venv/bin/python tools/data/glb2off.py --width 100           # đổi tỉ lệ chuẩn hoá
.venv/bin/python tools/data/glb2off.py --output /tmp/city.glb2off.off --force
```

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

## Sidecar `<stem>.params.json`

Tool ghi kèm file OFF một sidecar để ảnh `data_viz` và người đọc truy được bản
xem về đúng scene và tham số:

```json
{
  "output": "data/processed/meshes/city.standardized.glb2off.off",
  "output_sha256": "83690adb…",
  "scene": "data/processed/scenes/city.standardized.glb",
  "scene_sha256": "cdd605ee…",
  "parameters": {"width": 200.0},
  "result": {"vertices": 204682, "triangles": 301490,
             "edges": 498767, "bytes": 19232106},
  "script": "tools/data/glb2off.py",
  "script_sha256": "…"
}
```

Không có dấu thời gian nên chạy lại với cùng scene và `--width` cho ra cùng
byte. Sidecar được commit cùng OFF.

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

## Liên quan

- [`standardize.md`](standardize.md) — nơi `transformed_objects` được dùng để bake transform.
- [`triangulation.md`](triangulation.md) — nơi `read_glb_scene` cấp tam giác thành phố.
- [`data_viz.md`](data_viz.md) — đọc sidecar `.params.json` bên cạnh bản OFF này.
- [`../../data-format.md`](../../data-format.md) — hai lối đọc GLB và hệ trục.
