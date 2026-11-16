# Dữ liệu

Thư mục này có hai tầng: `raw/` giữ nguồn gốc, `processed/` giữ dữ liệu đã
kiểm tra và biến đổi để code dùng. Hướng dẫn chạy nằm trong
[README chính](../README.md); nguồn và giấy phép ở
[ATTRIBUTION.md](../ATTRIBUTION.md).

## `raw/` và `processed/`

| Thư mục | Vai trò | Quy tắc |
| --- | --- | --- |
| `raw/` | Nguồn gốc, giữ nguyên từng byte | Không sửa tay; mọi thay đổi bắt đầu từ đây |
| `processed/` | Đầu vào đã validate/biến đổi cho thuật toán | Không sửa tay; sinh lại bằng công cụ |

```text
raw/scenes/city.glb ──standardize──→ processed/scenes/city.standardized.glb
raw/meshes/*.off ────copy_meshes───→ processed/meshes/*.off
                   └─off2glb────────→ processed/scenes/meshes/*.off2glb.glb

city.standardized.glb
        └─triangulation──→ processed/meshes/city.standardized.triangulation.off
```

Sau bước `data`, mọi công cụ trong `tools/` chỉ đọc `processed/`:
`set_start_goal.py` và `data_viz.py` đọc fixture trong `processed/meshes/`.

## Quy ước tên tệp

| Hậu tố | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| `.standardized.glb` | Scene đã chuẩn hoá: bake transform, đổi tên node, bỏ material/texture, ghi provenance vào `extras` | `city.standardized.glb` |
| `.off2glb.glb` | Fixture Z-up chuyển sang GLB Y-up cho viewer; `--keep-z-up` nếu world cần Z-up | `terrain.off2glb.glb` |
| `.standardized.triangulation.off` | Bề mặt tam giác phân từ scene đã chuẩn hoá; Z-up | `city.standardized.triangulation.off` |
| `.paths.json` | Đường đi tham chiếu cho kiểm thử | `L.paths.json` |
| `.off`, `.glb` (không hậu tố) | Nguồn chưa qua xử lý | `L.off`, `city.glb` |

Hậu tố mô tả **các bước đã qua, theo đúng thứ tự**. `city.standardized.triangulation.off`
nghĩa là `city` → standardize → triangulation. Không dùng các từ chung chung
như `_final` hay `_new`. Tham số tam giác phân nằm trong `processed/README.md`.

## Thông tin từng tệp

Không dùng sidecar JSON cho từng tệp. Thông tin cần cho giấy phép, trục và dữ
liệu tham chiếu nằm trong bảng dưới đây và trong
[ATTRIBUTION.md](../ATTRIBUTION.md). Hash và số đỉnh/mặt có thể tính lại từ
tệp; kết quả stage `data` in số đỉnh/mặt/cạnh ra console mỗi lần chạy.

| Tệp | Nguồn | Giấy phép | Axis | Expected |
| --- | --- | --- | --- | --- |
| `raw/scenes/city.glb` | third-party, Saigon 3D City | CC BY 4.0 | Y-up | — |
| `raw/meshes/cliff.off` | first-party | BSD-3-Clause | as-authored | `expected/cliff.paths.json` |
| `raw/meshes/demo_mesh.off` | first-party | BSD-3-Clause | as-authored | `expected/demo_mesh.paths.json` |
| `raw/meshes/J17.off` | first-party | BSD-3-Clause | as-authored | `expected/J17.paths.json` |
| `raw/meshes/L.off` | first-party | BSD-3-Clause | as-authored | `expected/L.paths.json` |
| `raw/meshes/star.off` | first-party | BSD-3-Clause | as-authored | `expected/star.paths.json` (nguồn 0) |
| `raw/meshes/cube.off` | paper-derived | BSD-3-Clause | as-authored | — |
| `raw/meshes/dome.off` | paper-derived | BSD-3-Clause | Z-up | — |
| `raw/meshes/icosahedron.off` | paper-derived | BSD-3-Clause | as-authored | — |
| `raw/meshes/terrain.off` | paper-derived | BSD-3-Clause | Z-up | — |

## Tham số của bề mặt

`processed/meshes/city.standardized.triangulation.off` được dựng với ô 5, phủ toàn thành
phố, khe hở dọc 1,5, dự phòng ngang 1,6 và độ dốc tối đa 0,5. Bảng tham số
đầy đủ nằm trong
[processed/README.md](processed/README.md). Không có file metadata đi kèm;
`tools/data/triangulation.py` in tham số ra console và yêu cầu `--force` nếu tệp
đích đã tồn tại.

## Định dạng `.off`

`raw/meshes/*.off` là lưới tam giác dạng văn bản theo chuẩn OFF:

- Dòng đầu: `OFF`.
- Dòng tiếp theo: `V F E` — số đỉnh, số mặt, số cạnh khai báo.
- `V` dòng tiếp theo: `x y z`.
- `F` dòng tiếp theo: `3 a b c` — một tam giác, chỉ số đỉnh bắt đầu từ 0.

Các reader trong `tools/` chỉ nhận mặt tam giác. Giá trị `E` không được dùng
để dựng topology; số cạnh thực được suy ra từ danh sách mặt.

## Định dạng `.paths.json`

`expected/*.paths.json` lưu đường đi tham chiếu:

```json
{
  "mesh": "L",
  "source": 1,
  "coordinate_system": "model units; values carried over unchanged from the legacy fixtures",
  "paths": [
    [[0.0, 0.0, 1.0], [0.5, 0.5, 1.0], [1.0, 1.0, 1.0]]
  ]
}
```

`paths` là danh sách đường, mỗi đường có ít nhất 2 điểm `[x y z]`. `source`
ghi đỉnh nguồn đã dùng khi sinh dữ liệu tham chiếu.

## Chín mesh mẫu

| Mesh | Kích thước | Nguồn | Expected |
| --- | --- | --- | --- |
| `cliff` | 7 đỉnh, 10 mặt | first-party | `cliff.paths.json` |
| `demo_mesh` | 31 đỉnh, 62 mặt | first-party | `demo_mesh.paths.json` |
| `J17` | 10 đỉnh, 16 mặt | first-party | `J17.paths.json` |
| `L` | 12 đỉnh, 20 mặt | first-party | `L.paths.json` |
| `star` | 16 đỉnh, 28 mặt | first-party | `star.paths.json` (nguồn 0) |
| `cube` | 8 đỉnh, 12 mặt | paper-derived | không có |
| `dome` | 25 đỉnh, 40 mặt | paper-derived | không có |
| `icosahedron` | 12 đỉnh, 20 mặt | paper-derived | không có |
| `terrain` | 49 đỉnh, 72 mặt | paper-derived | không có |

Bốn mesh `paper-derived` được dựng từ ý tưởng của bài báo gốc về Funnel Tree,
nên chúng không có dữ liệu tham chiếu; đường đi sinh trên chúng chỉ được kiểm
tra hình học (nằm trên lưới, độ dài giữa cận dưới Euclid và cận trên).

## Quy tắc sửa dữ liệu

- Không sửa tay `raw/` hoặc `processed/`. Sửa nguồn rồi chạy lại công cụ.
- Các file `.off` được đối xử **byte-exact**: `.gitattributes` đặt
  `*.off -text` để Git không đổi kiểu xuống dòng.
- `expected/` được làm tròn 4 chữ số thập phân; sửa toạ độ phải cập nhật cả
  mesh lẫn expected.
- Muốn thêm mesh: thêm `raw/meshes/<tên>.off`, thêm dòng vào bảng
  *Thông tin từng tệp*, rồi chạy `python3 tools/data/copy_meshes.py --write`.
- Muốn thêm bề mặt khác: chạy `tools/data/triangulation.py --cell ... --output ...
  --force`; tham số được in ra console và nên ghi vào `processed/README.md`.
