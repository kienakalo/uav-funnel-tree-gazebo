# Dữ liệu

Thư mục này chứa cả dữ liệu của bên thứ ba và dữ liệu do nhóm tạo. Hướng dẫn
chạy nằm trong [README chính](../README.md); nguồn và giấy phép chi tiết ở
[ATTRIBUTION.md](../ATTRIBUTION.md).

Định hướng định dạng: GLB cho scene, OFF cho mesh dẫn xuất; xem
[docs/data-format.md](../docs/data-format.md). Migration `.geom` → `.off` đã
được áp dụng.

## Cấu trúc

| Thư mục | Nội dung | Nguồn | Giấy phép |
| --- | --- | --- | --- |
| `raw/scenes/` | `city.glb`, mô hình thành phố 20 MB | Saigon 3D City | CC BY 4.0 |
| `raw/meshes/` | Chín mesh `.off` cho kiểm thử hồi quy | Nhóm tác giả | BSD-3-Clause |
| `processed/standardized/` | Scene chuẩn hoá `city.standardized.glb` | Sinh tự động | BSD-3-Clause |
| `processed/off2glb/` | Fixture `*.off2glb.glb` cho Gazebo | Sinh tự động | BSD-3-Clause |
| `processed/triangulation/` | Bề mặt dẫn đường `.off` + manifest | Sinh tự động | BSD-3-Clause |
| `expected/` | Đường đi tham chiếu `.paths.json` | Nhóm tác giả | BSD-3-Clause |

Ba quy trình sinh `processed/` được mô tả trong
[processed/README.md](processed/README.md). Không sửa tay thư mục đó.

`raw/scenes/city.glb` là **input của pipeline**, không phải asset trình diễn:
`prepare.py`, `prepare_urban.py` và các công cụ dựng miền bay đọc trực tiếp
file này. Không sửa file gốc; mọi dẫn xuất nằm trong `generated/`.

Một bản `city.glb` đặt ở `data/raw/meshes/` sẽ bị `.gitignore` bỏ qua để tránh
chép trùng mô hình; đường dẫn chuẩn duy nhất là `data/raw/scenes/city.glb`.

## Định dạng `.off`

`data/raw/meshes/*.off` là lưới tam giác dạng văn bản theo chuẩn OFF:

- Dòng đầu: `OFF`.
- Dòng tiếp theo: `V F E` — số đỉnh, số mặt, số cạnh khai báo.
- `V` dòng tiếp theo: `x y z`.
- `F` dòng tiếp theo: `3 a b c` — một tam giác, chỉ số đỉnh bắt đầu từ 0.

`src/mesh.py` chỉ nhận mặt tam giác. Giá trị `E` **không được dùng**: vài file
mẫu khai báo sai, nên số cạnh thực được suy ra từ danh sách mặt.

## Định dạng `.paths.json`

`data/expected/*.paths.json` lưu đường đi tham chiếu:

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

`paths` là danh sách đường, mỗi đường có ít nhất 2 điểm `[x y z]`. Trường
`source` ghi đỉnh nguồn đã dùng khi sinh dữ liệu tham chiếu. Dấu ngoặc vuông
trong định dạng cũ không còn cần thiết.

## Năm mesh mẫu

| Mesh | Kích thước | Dùng ở |
| --- | --- | --- |
| `cliff` | 7 đỉnh, 10 mặt | `check.py`, `plan.py` (mặc định), `tests/test_funnel_target_scope.py` |
| `demo_mesh` | 31 đỉnh, 62 mặt | `check.py` |
| `J17` | 10 đỉnh, 16 mặt | `check.py` |
| `L` | 12 đỉnh, 20 mặt | `check.py`, `tests/test_funnel_target_scope.py` |
| `star` | 16 đỉnh, 28 mặt | `check.py` (nguồn 0 và 1), `tests/test_funnel_target_scope.py` |
| `cube` | 8 đỉnh, 12 mặt | `check.py`, `plan.py` — không có expected |
| `dome` | 25 đỉnh, 40 mặt | `check.py`, `plan.py` — không có expected |
| `icosahedron` | 12 đỉnh, 20 mặt | `check.py`, `plan.py` — không có expected |
| `terrain` | 49 đỉnh, 72 mặt | `check.py`, `plan.py` — không có expected |

`check.py` đối chiếu chiều dài đường đi với `expected/`, trừ cặp `star` nguồn
1 vì không có dữ liệu tham chiếu cho trường hợp đó.

Bốn mesh `cube`, `dome`, `icosahedron`, `terrain` được bổ sung từ ý tưởng của
bài báo gốc về Funnel Tree. Chúng **không có tệp `expected/`** tương ứng, nên
`check.py` chỉ chạy kiểm tra hình học: đường đi nằm trên lưới và độ dài nằm
giữa cận dưới Euclid và cận trên, không so sánh với dữ liệu tham chiếu.

## Quy tắc sửa dữ liệu

- Các file `.off` được đối xử **byte-exact**: `.gitattributes` đặt
  `*.off -text` để Git không đổi kiểu xuống dòng. Đừng chạy formatter trên
  chúng.
- `check.py` so sánh chiều dài với dung sai dựa trên việc làm tròn 4 chữ số
  thập phân trong `expected/`. Sửa toạ độ phải cập nhật cả `input/` lẫn
  `expected/`, hoặc chấp nhận kiểm thử thất bại.
- Muốn thêm mesh: thêm `input/<tên>.off`, `expected/<tên>.paths.json`, rồi
  khai báo cặp `(tên, nguồn)` trong `check.py`.
