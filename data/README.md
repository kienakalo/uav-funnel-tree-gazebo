# Dữ liệu

Thư mục này có hai tầng: `raw/` giữ nguồn gốc, `processed/` giữ dữ liệu đã
kiểm tra và biến đổi để code dùng. Hướng dẫn chạy nằm trong
[README chính](../README.md); nguồn và giấy phép ở
[ATTRIBUTION.md](../ATTRIBUTION.md).

## `raw/` và `processed/`

| Thư mục | Vai trò | Quy tắc |
| --- | --- | --- |
| `raw/` | Nguồn gốc, giữ nguyên từng byte | Không sửa tay; mọi thay đổi bắt đầu từ đây |
| `processed/` | Đầu vào đã validate/biến đổi cho thuật toán và Gazebo | Không sửa tay; sinh lại bằng công cụ |

```text
raw/scenes/city.glb ──standardize──→ processed/scenes/city.standardized.glb
raw/meshes/*.off ────copy_meshes───→ processed/meshes/*.off
                   └─off2glb────────→ processed/scenes/meshes/*.off2glb.glb

city.standardized.glb + delivery plan
        └─triangulation──→ processed/meshes/city.triangulation.off
```

`check.py`, `plan.py` và `tests/` đọc fixture từ `processed/meshes/`.
`prepare.py`, `prepare_urban.py` và các công cụ dựng bản đồ đọc
`raw/scenes/city.glb`.

## Quy ước tên tệp

| Hậu tố | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| `.standardized.glb` | Scene đã chuẩn hoá: bake transform, đổi tên node, bỏ material/texture, ghi provenance vào `extras` | `city.standardized.glb` |
| `.off2glb.glb` | Kết quả chuyển một fixture `.off` sang GLB cho Gazebo; toạ độ giữ nguyên, xem `axis` | `terrain.off2glb.glb` |
| `.triangulation.off` | Bề mặt dẫn đường đã tam giác phân, hệ Gazebo đã chuẩn hoá, Z-up | `city.triangulation.off` |
| `.triangulation.json` | Manifest tham số và nguồn của bề mặt | `city.triangulation.json` |
| `.paths.json` | Đường đi tham chiếu cho kiểm thử | `L.paths.json` |
| `.off`, `.glb` (không hậu tố) | Nguồn chưa qua xử lý | `L.off`, `city.glb` |
| `<tệp>.json` | Sidecar metadata của đúng tệp đó | `L.off.json` |

Hậu tố mô tả **bước đã qua**, không dùng các từ chung chung như `_final` hay
`_new`. Tham số tam giác phân không nằm trong tên tệp mà nằm trong manifest.

## Sidecar metadata

Mỗi tệp trong `raw/` và mỗi bản sao trong `processed/meshes/` có một sidecar
cùng tên cộng `.json`. Sidecar đi kèm tệp, nên metadata của từng mesh có thể
khác nhau mà không ảnh hưởng mesh khác.

| Trường | Ý nghĩa |
| --- | --- |
| `schema` | Phiên bản schema, hiện là `1`. Tăng khi đổi cấu trúc. |
| `kind` | `raw-asset` hoặc `processed-asset`. Quyết định có trường `source` hay không. |
| `file` | Tên tệp mà sidecar mô tả. |
| `format` | `OFF` hoặc `GLB2`. |
| `sha256` | Hash nội dung tệp, tính lại mỗi lần chạy `--write`. |
| `bytes` | Kích thước tệp. |
| `geometry` | Số đỉnh, tam giác; OFF thêm `declared_edges`/`computed_edges`; GLB thêm `nodes`/`meshes`. |
| `units` | `model-units` cho mọi tệp; không phải mét khảo sát. |
| `axis` | `Y-up`, `Z-up` hoặc `as-authored`. Dùng khi chuyển sang Gazebo. |
| `origin` | `first-party`, `paper-derived` hoặc `third-party`. |
| `license` | SPDX identifier, ví dụ `BSD-3-Clause` hoặc `CC-BY-4.0`. |
| `expected` | Đường dẫn tới `.paths.json`, hoặc `null` nếu chỉ kiểm tra hình học. |
| `notes` | Ghi chú riêng của tệp. |
| `source` | Chỉ có ở `processed-asset`: tệp raw và hash của nó. |

Ví dụ sidecar raw:

```json
{
  "schema": 1,
  "kind": "raw-asset",
  "file": "terrain.off",
  "format": "OFF",
  "sha256": "7a6cc43c...",
  "bytes": 2115,
  "geometry": {
    "vertices": 49,
    "triangles": 72,
    "declared_edges": 108,
    "computed_edges": 120
  },
  "units": "model-units",
  "axis": "Z-up",
  "origin": "paper-derived",
  "license": "BSD-3-Clause",
  "expected": null,
  "notes": "Height field; z is elevation."
}
```

Bản trong `processed/meshes/` giữ nguyên các trường trên, đổi `kind` thành
`processed-asset` và thêm:

```json
"source": {
  "file": "data/raw/meshes/terrain.off",
  "sha256": "7a6cc43c..."
}
```

Với OFF, `declared_edges` là giá trị `E` trong header còn `computed_edges` là
số cạnh suy ra từ danh sách mặt. Hai giá trị có thể lệch vì vài fixture khai
báo `E` chưa chính xác; ví dụ `terrain.off` khai báo 108 nhưng thực tế có 120.

Sinh hoặc cập nhật:

```bash
python3 tools/raw_sidecars.py --write
python3 tools/copy_meshes.py --write
```

`tools/verify_project_results.py` gọi cả hai bước `--check`, nên sửa tay một
mesh mà không cập nhật sidecar sẽ làm kiểm tra cuối thất bại.

## Manifest của bước tam giác phân

`processed/meshes/city.triangulation.json` không phải sidecar của một tệp mà
là manifest của **quá trình** sinh ra `city.triangulation.off`:

| Trường | Ý nghĩa |
| --- | --- |
| `process`, `method` | Tên bước và cách dựng bề mặt |
| `parameters` | `cell`, `coverage`, `vertical_clearance`, `horizontal_half_width`, `max_axis_slope` |
| `scene` | Scene đầu vào, hash, `scale`, `origin` |
| `stl` | STL chuẩn đã dùng, hash, `mode` (canonical hoặc dựng lại từ scene) |
| `plan` | Kế hoạch giao hàng, hash, START/GOAL |
| `result` | Số đỉnh/mặt/cạnh, `surface_source`, `surface_target`, `nonmanifold_edges` |
| `coordinates` | Hệ toạ độ: Gazebo đã chuẩn hoá, Z-up |
| `scope` | Bề mặt bao an toàn phía trên thành phố, không phải mái nhà |

Vì tham số quyết định hình học, công cụ dừng nếu chạy lại với tham số khác mà
tệp đích đã tồn tại; dùng `--force` để ghi đè có chủ đích.

## Định dạng `.off`

`raw/meshes/*.off` là lưới tam giác dạng văn bản theo chuẩn OFF:

- Dòng đầu: `OFF`.
- Dòng tiếp theo: `V F E` — số đỉnh, số mặt, số cạnh khai báo.
- `V` dòng tiếp theo: `x y z`.
- `F` dòng tiếp theo: `3 a b c` — một tam giác, chỉ số đỉnh bắt đầu từ 0.

`src/mesh.py` chỉ nhận mặt tam giác. Giá trị `E` không được dùng để dựng
topology; số cạnh thực được suy ra từ danh sách mặt.

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
nên `check.py` chỉ kiểm tra hình học: đường nằm trên lưới và độ dài nằm giữa
cận dưới Euclid và cận trên, không so sánh với dữ liệu tham chiếu.

## Quy tắc sửa dữ liệu

- Không sửa tay `raw/` hoặc `processed/`. Sửa nguồn rồi chạy lại công cụ.
- Các file `.off` được đối xử **byte-exact**: `.gitattributes` đặt
  `*.off -text` để Git không đổi kiểu xuống dòng.
- `check.py` so sánh chiều dài với dung sai dựa trên việc làm tròn 4 chữ số
  thập phân trong `expected/`. Sửa toạ độ phải cập nhật cả mesh lẫn expected.
- Muốn thêm mesh: thêm `raw/meshes/<tên>.off`, thêm mục vào `CURATED` trong
  `tools/raw_sidecars.py`, chạy `raw_sidecars.py --write` và
  `copy_meshes.py --write`, rồi cập nhật `check.py`.
- Muốn thêm bề mặt khác: chạy `tools/triangulation.py --cell ... --output ...`;
  manifest sẽ ghi tham số tương ứng.
