---
title: Định dạng dữ liệu
aliases:
  - data-format
  - định dạng
type: reference
stage: all
source:
  - lib/mesh_off.py
  - lib/mesh_glb.py
tags:
  - funnel-tree/reference
  - funnel-tree/data-format
---

# Định dạng dữ liệu

> [!abstract] Mục đích
> Tra cứu nhanh mọi định dạng file trong repo — OFF, GLB, JSON, CSV, SDF,
> STL — cùng quy ước hậu tố tên file và nơi ghi schema chi tiết.

> [!info] Vị trí
> **Phạm vi** file trong `data/`, `generated/`, `results/runs/`  
> **Nguyên tắc** OFF cho lưới tam giác, GLB cho scene/mesh xem được, JSON cho mọi bản ghi  
> **Đọc/ghi bằng** `lib/mesh_off.py` (OFF) và `lib/mesh_glb.py` (GLB)  

## Phụ thuộc

| Định dạng | Đọc/ghi ở | Ghi chú |
| --- | --- | --- |
| OFF | `lib/mesh_off.py` | Chỉ tam giác; `E` trong header không được tin |
| GLB | `lib/mesh_glb.py`, `tools/data/glb2off.py` | glTF 2 nhị phân, float32, không Draco |
| JSON | Từng tool, schema ở bảng cuối | Không có timestamp ở file tất định |
| CSV | `tools/simulate/plugin/` ghi, `validate.py` đọc | Telemetry 10 Hz, 16 cột |
| SDF, STL | `tools/simulate/build_world.py` | World Gazebo và collision mesh |

Ba định dạng dữ liệu chính: **OFF** cho mesh tam giác, **GLB** cho scene và mesh
để xem, **JSON** cho mọi bản ghi (mission, tuyến, đối chiếu, kết quả bay). Kết
quả mô phỏng còn có CSV telemetry, SDF và STL collision; schema từng loại ở bảng
dưới.

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
- `lib/mesh_off.py` là reader/writer duy nhất: `read_off` trả mảng NumPy, `write_off`
  ghi toạ độ bằng `%.17g` để đọc lại đúng giá trị double đã tính.
- `inspect_mesh` trong `lib/mesh_off.py` kiểm topology: không mặt suy biến, mỗi cạnh
  kề tối đa hai mặt, mỗi đỉnh thuộc đúng một nhóm mặt liên thông;
  `set_start_goal` gọi thêm kiểm tra đỉnh trùng toạ độ.

## GLB

glTF 2 nhị phân: header 12 byte, chunk JSON, chunk BIN. Repo chỉ đọc
primitive tam giác không nén (không Draco, không sparse accessor) — đúng những
gì `data/raw/scenes/city.glb` và các bản dẫn xuất của repo chứa.

Hai lối đọc, khác nhau ở mục đích:

| Hàm | Dùng ở | Trục và đơn vị |
| --- | --- | --- |
| `tools/data/glb2off.py: iter_scene_meshes` | `standardize.py` (qua `transformed_objects`) | Bake transform, **giữ nguyên** trục và đơn vị gốc |
| `tools/data/glb2off.py: read_glb_scene` | `triangulation.py`, tool `glb2off.py` | Bake transform, đổi **Y-up → Z-up**, chuẩn hoá bề rộng 200 m |

Cả hai cùng dùng `iter_scene_meshes`, nên chỉ có một chỗ duyệt cây node.

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

## Mission JSON

`data/processed/missions/<mesh>.mission.json` lưu lựa chọn START/GOAL cho một mesh.
Tool tạo file này khi bạn chọn. Repo đã có 10 mission cho các mesh mẫu; mesh
chưa có file thì tool hỏi và ghi thêm:

```json
{
  "mesh": "data/processed/meshes/city.standardized.triangulation.off",
  "mesh_sha256": "f6e01c6d…",
  "mesh_vertices": 2295,
  "mesh_faces": 4400,
  "boundary_edges": 6694,
  "vertex_spacing": 5.0,
  "snap_mode": "xy",
  "max_snap": 3.535534,
  "mode": "explicit",
  "selected_by": "cli",
  "start": {"vertex": 792, "xyz": [-38.752124, 22.103392, 8.643046],
            "input": [-38.752, 22.103, 7.206], "snap": 0.000411},
  "goals": [{"id": "g1", "vertex": 1810,
             "xyz": [74.736587, -55.357157, 8.947593]}]
}
```

- `mode: "all-goals"` nghĩa là mọi đỉnh trừ `start` là goal; khi đó `goals` rỗng
  và mesh phải có tối đa 300 đỉnh.
- `mesh_sha256` và số đỉnh/mặt dùng để từ chối file đã lưu khi mesh thay đổi.
- `input` chỉ có khi người dùng nhập toạ độ; `xyz` luôn là toạ độ đỉnh đã snap.
- Không có timestamp: chạy lại với cùng lựa chọn cho ra đúng byte cũ.

## Route JSON

`generated/routes/<mission>.routes.json` là kết quả của stage `plan`:

```json
{
  "mission": "data/processed/missions/cliff.mission.json",
  "mission_sha256": "…",
  "mesh": "data/processed/meshes/cliff.off",
  "mesh_sha256": "…",
  "source": 0,
  "solver": {
    "name": "funnel_tree",
    "module": "algo/funnel_tree.py",
    "module_sha256": "…",
    "timeout_seconds": 300.0,
    "max_nodes": 200000,
    "clipping": true
  },
  "mode": "all-goals",
  "routes": [
    {"id": "v1", "vertex": 1, "length": 2.828427125,
     "waypoints": [[2.0, 2.0, 0.0], [0.0, 0.0, 0.0]]}
  ],
  "stats": {"sources_considered": 3, "propagations": 2,
            "mode": "combined", "clipping": true},
  "planning_seconds": 0.004,
  "environment": {"python": "3.14.8", "numpy": "2.5.4"}
}
```

- `length` là tổng khoảng cách Euclid giữa các waypoint liên tiếp, trên mặt.
- `mode: all-goals` giữ mọi đỉnh trừ `source`; `explicit` chỉ giữ các goal
  trong mission.
- `stats.mode` là `per-goal` khi mission có nhiều goal (mỗi goal một lượt tìm,
  nhanh hơn một lượt gộp) và `combined` khi chỉ có một goal hoặc all-goals.
- Ba hash khoá kết quả vào đúng mission, đúng mesh và đúng mã thuật toán.
- `planning_seconds` là số đo, nên chạy lại sẽ làm tệp thay đổi.

## Compare JSON

`generated/compare/<mesh>.compare.json` so độ dài từng đỉnh với
`data/expected/<mesh>.paths.json`:

```json
{
  "mesh": "cliff",
  "source": 1,
  "reference": "data/expected/cliff.paths.json",
  "tolerance": 0.0001,
  "vertices": 7,
  "max_relative_error": 1.72e-05,
  "mean_relative_error": 2.63e-06,
  "failures": [],
  "paths": [
    {"vertex": 5, "reference_length": 2.285536,
     "funnel_length": 2.285575125, "relative_error": 1.7e-05}
  ]
}
```

`summary.json` gộp các mesh: `passed`, `failed`, `skipped`. Toạ độ tham chiếu
làm tròn 4 chữ số nên sai lệch cỡ `1e-5`; `--tolerance` mặc định `1e-4`.

## Hậu tố tên tệp

| Hậu tố | Ý nghĩa |
| --- | --- |
| `.standardized.glb` | Scene đã bake transform, đổi tên node, bỏ material/texture |
| `.off2glb.glb` | Fixture chuyển sang GLB Y-up để mở bằng viewer |
| `.standardized.triangulation.off` | Bề mặt dẫn đường dựng từ scene chuẩn hoá |
| `.mission.json` | Lựa chọn START/GOAL của một mesh |
| `.routes.json` | Tuyến stage `plan` lập: waypoint, độ dài, thống kê solver |
| `.compare.json` | Đối chiếu từng đỉnh với `data/expected/<mesh>.paths.json` |
| `.params.json` | Tham số + SHA của bề mặt hoặc scene đã sinh ra file bên cạnh |
| `.png.json` | Sidecar của ảnh: tham số, SHA, dòng lệnh |
| `.paths.json` | Đường tham chiếu |
| `.off`, `.glb` (không hậu tố) | Nguồn chưa qua xử lý |

Hậu tố mô tả **các bước đã qua, theo đúng thứ tự**: `city.standardized.
triangulation.off` là `city` → standardize → triangulation.

`<stem>` là tên mesh hoặc mission, không gồm hậu tố: `cliff.mission.json` →
mission id `cliff`. `flown_route.json` là tên cố định trong
`generated/simulate/<mission>-<goal>/`: tuyến đã rút gọn mà plugin thật sự bay,
khác với bản đầy đủ `<mission>.routes.json`. `generated/compare/summary.json` là
bảng gộp duy nhất nên không mang tên mesh. Archive trong `results/runs/` lưu
trước 18/11/2026 giữ tên cũ `route.json`/`route.png`; archive mới dùng
`routes.json`/`routes.png`.

## Schema từng loại JSON

| Tệp | Schema ở |
| --- | --- |
| `<mesh>.mission.json`, `<mission>.routes.json`, `<mesh>.compare.json` | trang này |
| `flown_route.json`, `world_metadata.json` | [`tools/simulate/build_world.md`](tools/simulate/build_world.md) |
| `validation.json` | [`tools/simulate/validate.md`](tools/simulate/validate.md) |
| `manifest.json`, `parameters.json` | [`tools/main.md`](tools/main.md) |
| `.png.json` (sidecar ảnh) | [`tools/figures.md`](tools/figures.md) |

## Vì sao không dùng STL

STL chỉ có tam giác rời, không có chỉ số đỉnh dùng chung: muốn dựng topology
phải weld lại, và weld là một phép xấp xỉ có tham số. Ngoài ra STL lưu float32,
nên ghi ra rồi đọc lại là mất chính xác so với giá trị double vừa tính.

Trước đây `triangulation.py` đi qua STL trung gian; nay nó đọc thẳng scene đã
chuẩn hoá. Hệ quả cần biết: `standardize.py` làm tròn float32 **trước** khi
chuẩn hoá, còn STL làm tròn **sau**, nên bề mặt dựng từ hai nguồn lệch nhau
cỡ `2e-6` m ở cao độ. Hai bản ghi SHA tương ứng nằm trong
[`data/processed/README.md`](../data/processed/README.md).

## Liên quan

- [`tools/lib.md`](tools/lib.md) — reader/writer OFF và GLB.
- [`tools/data/glb2off.md`](tools/data/glb2off.md) — hai lối đọc GLB.
- [`tools/simulate/build_world.md`](tools/simulate/build_world.md) — SDF, STL, `flown_route.json`.
- [`tools/simulate/validate.md`](tools/simulate/validate.md) — schema `validation.json`.
