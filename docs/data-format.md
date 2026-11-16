# Định dạng dữ liệu

Ba định dạng được dùng: **OFF** cho mesh tam giác, **GLB** cho scene và mesh để
xem, **JSON** cho đường tham chiếu. Không có định dạng trung gian nào khác.

## OFF

Lưới tam giác dạng văn bản, toàn bộ là ASCII:

```text
OFF
4 1 6
0 0 0
1 0 0
1 1 0
0 1 0
3 0 1 2
```

- Dòng đầu: `OFF`.
- Dòng hai: `V F E` — số đỉnh, số mặt, số cạnh **khai báo**.
- `V` dòng tiếp: `x y z`.
- `F` dòng tiếp: `3 a b c`, chỉ số đỉnh bắt đầu từ 0.

Quy ước trong repo:

- Chỉ nhận mặt tam giác. Reader trong `tools/` báo lỗi nếu gặp đa giác.
- `E` không dùng để dựng topology; số cạnh thực được suy ra từ danh sách mặt.
  Vài fixture có `E` không chính xác, nên không được tin giá trị này.
- Tệp `.off` được đối xử **byte-exact**: `.gitattributes` đặt `*.off -text`.
- `tools/off_mesh.py: write_off` ghi toạ độ bằng `%.17g` để đọc lại đúng giá trị
  double đã tính, không bị làm tròn khi lưu.
- `tools/set_start_goal.py` kiểm tra thêm topology khi đọc: không đỉnh trùng toạ
  độ, không mặt suy biến, mỗi cạnh kề tối đa hai mặt, mỗi đỉnh thuộc đúng một
  nhóm mặt liên thông.

## GLB

glTF 2 nhị phân: header 12 byte, chunk JSON, chunk BIN. Repo chỉ đọc
primitive tam giác không nén (không Draco, không sparse accessor) — đúng những
gì `data/raw/scenes/city.glb` và các bản dẫn xuất của repo chứa.

Hai lối đọc, khác nhau ở mục đích:

| Hàm | Dùng ở | Trục và đơn vị |
| --- | --- | --- |
| `tools/glb2off.py: read_glb_scene` | `triangulation.py`, `data_viz.py --scene`, tool `glb2off.py` | Bake transform, đổi **Y-up → Z-up**, chuẩn hoá bề rộng 200 m |
| `tools/glb_nodes.py: transformed_objects` | `standardize.py` | Bake transform, **giữ nguyên** trục và đơn vị gốc |

`read_glb_scene` giữ nguyên từng primitive (không weld đỉnh), nên vết nối giữa
các primitive vẫn còn — đúng với scene gốc. Nó cũng là lý do bề mặt dẫn đường
dựng trực tiếp từ scene mà không cần bước trung gian.

## `.paths.json`

Đường tham chiếu để vẽ đè lên ảnh kiểm tra:

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

`paths` là danh sách đường, mỗi đường có ít nhất 2 điểm `[x y z]`. `source` là
đỉnh nguồn đã dùng khi sinh dữ liệu. Toạ độ được làm tròn 4 chữ số thập phân;
sửa mesh thì phải cập nhật cả tệp này.

## Hậu tố tên tệp

| Hậu tố | Ý nghĩa |
| --- | --- |
| `.standardized.glb` | Scene đã bake transform, đổi tên node, bỏ material/texture |
| `.off2glb.glb` | Fixture chuyển sang GLB Y-up để mở bằng viewer |
| `.standardized.triangulation.off` | Bề mặt dẫn đường dựng từ scene chuẩn hoá |
| `.paths.json` | Đường tham chiếu |
| `.off`, `.glb` (không hậu tố) | Nguồn chưa qua xử lý |

Hậu tố mô tả **các bước đã qua, theo đúng thứ tự**: `city.standardized.
triangulation.off` là `city` → standardize → triangulation.

## Vì sao không dùng STL

STL chỉ có tam giác rời, không có chỉ số đỉnh dùng chung: muốn dựng topology
phải weld lại, và weld là một phép xấp xỉ có tham số. Ngoài ra STL lưu float32,
nên ghi ra rồi đọc lại là mất chính xác so với giá trị double vừa tính.

Trước đây `triangulation.py` đi qua STL trung gian; nay nó đọc thẳng scene đã
chuẩn hoá. Hệ quả cần biết: `standardize.py` làm tròn float32 **trước** khi
chuẩn hoá, còn STL làm tròn **sau**, nên bề mặt dựng từ hai nguồn lệch nhau
cỡ `2e-6` m ở cao độ. Hai bản ghi SHA tương ứng nằm trong
[`data/processed/README.md`](../data/processed/README.md).
