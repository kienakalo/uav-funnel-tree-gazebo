---
title: set_start_goal.py
aliases:
  - set_start_goal
type: tool
stage: data
source: tools/data/set_start_goal.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/data
---

# `set_start_goal.py`

> [!abstract] Mục đích
> Chọn **START và GOAL** trên một mesh OFF rồi lưu thành mission JSON. Lựa
> chọn được snap về đỉnh gần nhất và tái dùng ở các lần sau, nên `plan` không bao
> giờ phải hỏi lại.

> [!info] Vị trí
> **File** `tools/data/set_start_goal.py` — stage `data`, bước 7  
> **Thuật toán** Snap về đỉnh gần nhất trong XY (hoặc 3D), kiểm topology bằng `inspect_mesh`, ghi JSON không timestamp  
> **Vào** một `.off` + lựa chọn của người dùng (JSON cũ, cờ, terminal hoặc `--pick`)  
> **Ra** `data/processed/missions/<mesh>.mission.json`  
> **Cờ** `--mesh`, `--mission`, `--output`, `--list-meshes`, `--all-meshes`, `--start`, `--start-vertex`, `--goal`, `--goal-vertex`, `--all-goals`, `--pick`, `--snap`, `--max-snap`, `--refresh-changed`, `--force`  
> **Ghi chú** `--all-meshes` bỏ qua `*.glb2off.off`: đó là bản xem toàn scene, các vỏ lặp toạ độ đỉnh nên không dựng được `Mesh`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `fail(message)` | chuỗi | thoát 1 | In `set_start_goal: …` rồi dừng, dùng chung cho mọi lỗi |
| `relative(path)` | đường dẫn | đường dẫn gọn | Cắt về tương đối repo khi có thể, để JSON không ghi đường dẫn tuyệt đối |
| `read_mesh(path)` | đường dẫn OFF | `Mesh` đã kiểm | Kiểm đỉnh trùng, mặt suy biến, cạnh kề >2 mặt, đỉnh rỗng |
| `vertex_spacing(points)` | mảng đỉnh | mét | Trung vị khoảng cách giữa các cột lưới kề nhau |
| `describe(points, vertex, target=None, distance=0.0)` | đỉnh + toạ độ người nhập | `dict` `vertex/xyz/input/snap` | Ghi lại lựa chọn đã snap để mission truy được về câu trả lời gốc |
| `parse_index(text, count, label)` | chuỗi | chỉ số | Kiểm là số nguyên trong `0..count-1`, sai thì dừng |
| `parse_point(text, label)` | `"x y z"` hoặc `"x,y,z"` | ba float | Kiểm đủ ba số và đều hữu hạn |
| `snap(points, target, mode, max_snap, label)` | toạ độ đích | `(index, distance)` | Snap XY (hoặc 3D), từ chối nếu quá `--max-snap` |
| `resolve(text, points, mode, max_snap, label)` | chuỗi `N` hoặc `x y z` | `(index, snap_record)` | Chuyển lựa chọn người dùng thành đỉnh đã snap |
| `terminal_streams()` | — | `(read_line, write)` | Đọc/ghi `/dev/tty` kể cả khi stdin/stdout bị pipe |
| `print_vertices(points, faces, limit=TABLE_LIMIT, write=print)` | mesh | in bảng | Bảng `# / x / y / z / số mặt kề`; quá `limit` thì in phần đầu và nhắc dùng `--pick` |
| `ask_console(...)` | mesh + quy tắc snap | START/GOAL | Hỏi trên terminal, nhận chỉ số hoặc toạ độ, `all` lấy mọi đỉnh còn lại |
| `gui_backend()` | — | tên backend hoặc `None` | Bọc `plotting.use_interactive` để biết có mở được cửa sổ 3D |
| `ask_pick(points, faces)` | mesh | START/GOAL hoặc `None` | Mở cửa sổ 3D để click; thiếu backend hoặc Matplotlib thì trả `None` |
| `choose_console(path, points, faces, mode, max_snap)` | mesh + quy tắc snap | START/GOAL | In bảng đỉnh rồi hỏi qua `/dev/tty`, dùng khi không có JSON và không có cờ |
| `mission_path(mesh, output, explicit)` | mesh + `--output`/`--mission` | `Path` | Chọn `<mesh>.mission.json` trong thư mục đích |
| `mission_record(...)` | mesh, điểm, chế độ | `dict` mission | Dựng toàn bộ trường JSON (hash, kích thước, snap, selected_by) |
| `check_saved(record, mesh_path, points, faces)` | mission đã lưu | `bool` / lỗi | Từ chối mission khi mesh đổi hash hoặc số đỉnh/mặt |
| `write_json(path, data)` | `dict` mission | ghi file | Ghi `*.tmp` rồi `replace`, không để lại JSON dở khi bị ngắt |
| `summary(record, path)` | mission | in | In mesh, START, từng GOAL, snap và đường dẫn đã lưu |
| `refresh_mission(mesh_path, path, args)` | mission cũ + bề mặt mới | ghi lại JSON | Snap lại START/GOAL đã lưu, giữ id `g1..gN`; điểm quá xa thì dừng |
| `mesh_list(folder)` | thư mục mesh | danh sách `.off` theo tên | Bỏ `*.glb2off.off`: vỏ của bản xem lặp toạ độ nên không dựng được `Mesh` |
| `show_meshes(args)` | cờ | in | Liệt kê mesh kèm số đỉnh/mặt và trạng thái đã có mission hay chưa |
| `process_mesh(mesh_path, args)`, `main()` | một mesh / cả thư mục | mission JSON, `Save at:` | Điều phối đọc → chọn → kiểm → ghi |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy; `argparse`, `json`, `sys`, `pathlib`; Matplotlib chỉ khi `--pick` | Mảng đỉnh, CLI, cửa sổ chọn điểm |
| Nội bộ | `lib/mesh_off.py: read_off, inspect_mesh` (qua `Mesh`) | Đọc và kiểm topology |
| Nội bộ | `lib/plotting.py: use_interactive` | Chọn backend cho `--pick` |
| Dữ liệu | `data/processed/meshes/*.off` | Mesh để chọn điểm |
| Được gọi bởi | `main.py` bước 7 (`--all-meshes --refresh-changed`) | Đồng bộ mission khi bề mặt đổi |

## Việc nó làm

1. **Quét mesh.** Đọc bằng `Mesh` (`lib/mesh_off.py`): kiểm đỉnh trùng toạ độ,
   mặt suy biến, cạnh kề >2 mặt, đỉnh không thuộc mặt nào. In kích thước, số
   cạnh biên, bước lưới, bounds; nếu ≤200 đỉnh thì in bảng `# / x / y / z / faces`.
2. **Lấy lựa chọn** theo thứ tự ưu tiên:

   | Thứ tự | Nguồn | Điều kiện |
   | --- | --- | --- |
   | 1 | JSON đã lưu | File tồn tại và khớp mesh (hash + số đỉnh/mặt) |
   | 2 | Tham số dòng lệnh | `--start[-vertex]`, `--goal[-vertex]`, `--all-goals` |
   | 3 | Hỏi terminal | Không có JSON, không có cờ; đọc từ `/dev/tty` nếu stdout bị pipe |
   | 4 | `--pick` | Cửa sổ 3D; thiếu backend thì lùi về bàn phím |

3. **Snap.** Toạ độ nhập được snap về đỉnh gần nhất trong XY (hoặc 3D với
   `--snap 3d`), sai số in ra; quá `--max-snap` (mặc định nửa đường chéo ô) thì
   từ chối.
4. **Kiểm tra.** START không trùng GOAL, hai GOAL không trùng nhau, `all-goals`
   chỉ cho mesh ≤300 đỉnh.
5. **Ghi JSON** (đường dẫn mặc định `data/processed/missions/<mesh>.mission.json`).

## Giao diện chọn điểm

| Cách | Lệnh | Ghi chú |
| --- | --- | --- |
| Bàn phím | `set_start_goal.py` | Gõ chỉ số hoặc `x y z`; dòng trống kết thúc danh sách GOAL; `all` cho mọi đỉnh còn lại |
| Chuột | `set_start_goal.py --pick` | `s` = START, `g` = GOAL, `u` = bỏ GOAL cuối, Enter = lưu |
| Không tương tác | `--start-vertex 1 --all-goals` | Dùng cho script/CI |

Mỗi câu hỏi được in thành **một dòng riêng** trước khi đọc câu trả lời. Cần vậy
vì `main.py` chuyển output của từng bước theo dòng: prompt không có `\n` nằm lại
trong pipe, người dùng không thấy câu hỏi và tool trông như bị treo dù nó đang
chờ gõ.

## Mission của thành phố

Bề mặt `city.standardized.triangulation.off` dùng START/GOAL của thí nghiệm
delivery trong repo cũ (`generated/city_three_goals/cases.json`, commit
`acc040b`), trùng với `DEFAULT_START`/`DEFAULT_GOAL` của
[`triangulation.py`](triangulation.md):

| | Đỉnh | xyz (m) | Vai trò |
| --- | --- | --- | --- |
| START | 2015 | −38,7521 · 22,1034 · 6,6338 | xuất phát, phía tây-trung tâm |
| g1 | 4762 | 74,7366 · −55,3572 · 7,7729 | đích xa, góc đông-nam |
| g2 | 4997 | 81,0000 · −9,0000 · 7,4556 | đích phía đông |
| g3 | 3923 | 39,0000 · 51,0000 · 9,3299 | đích phía bắc |

Bảng trên là bề mặt lưới 3 m (`results/runs/cell3close`), cấu hình đang chạy. Với
lưới 4 m (`results/runs/cell4`) các đỉnh là 1133 / 2708 / 2829 / 2240; với lưới
5 m (`results/runs/city792e`) là 792 / 1810 / 1910 / 1518 — cùng toạ độ được yêu
cầu, khác z vì mission ghi z của bề mặt tại thời điểm chọn.

Hai đích phía đông và phía bắc lệch **1,414 m** so với toạ độ yêu cầu (`y = −10`
và `y = 50`), vì lưới 3 m không có đỉnh đúng ở đó; `refresh_mission` snap sang
đỉnh gần nhất và ghi khoảng cách vào trường `snap`. Trên lưới 4 m khoảng cách đó
là 2 m; trên lưới 5 m hai đích nằm đúng đỉnh.

- Bề mặt **không** phụ thuộc mission: đổi START/GOAL chỉ đổi route, SHA bề mặt
  giữ nguyên.
- Các lần bay cũ nằm trong [`results/runs/`](../../../results/README.md).

## Schema JSON

| Trường | Nội dung |
| --- | --- |
| `mesh`, `mesh_sha256` | Mesh đã chọn điểm; hash để phát hiện mesh đổi |
| `mesh_vertices`, `mesh_faces`, `boundary_edges` | Kích thước lúc chọn |
| `vertex_spacing`, `snap_mode`, `max_snap` | Bước lưới và quy tắc snap |
| `mode` | `explicit` hoặc `all-goals` |
| `selected_by` | `cli`, `console` hoặc `pick` |
| `start` | `vertex`, `xyz`, `input` (nếu nhập toạ độ), `snap` |
| `goals` | `id`, `vertex`, `xyz`, `input`, `snap`; rỗng khi `all-goals` |

Không có timestamp → chạy lại với cùng lựa chọn cho ra đúng byte cũ.

## Cập nhật mission khi bề mặt đổi

Mission ghi `mesh_sha256` của bề mặt lúc chọn, nên bề mặt sinh lại với tham số
khác sẽ làm `plan` dừng với *"mesh changed since the mission was saved"*.
`--refresh-changed` (chỉ đi với `--all-meshes`) xử lý việc đó mà không cần chọn
lại tay: toạ độ START/GOAL đã lưu được snap vào đỉnh gần nhất của bề mặt mới,
id `g1..g3` giữ nguyên, rồi ghi lại SHA/kích thước.

```bash
.venv/bin/python tools/data/set_start_goal.py --all-meshes --refresh-changed
```

```text
data/processed/missions/city.standardized.triangulation.mission.json: bề mặt đã đổi, cập nhật lại lựa chọn cũ
  START đỉnh 792 -> 792 (0.000 m)
  g1 đỉnh 1810 -> 1810 (0.000 m)
  ...
Save at: data/processed/missions/city.standardized.triangulation.mission.json

1 mission(s) cập nhật theo bề mặt mới.
```

- Mission không đổi SHA thì bỏ qua, không ghi lại.
- Điểm nào rơi xa hơn `--max-snap` so với mọi đỉnh mới thì tool **dừng**, không
  tự dịch mission.
- `--refresh-changed` không đi cùng `--force` (một bên giữ điểm cũ, một bên
  chọn lại).
- `main.py` luôn thêm cờ này vào bước 7 của stage `data`.

## Quản lý nhiều mesh

```bash
# xem mesh nào đã có mission
.venv/bin/python tools/data/set_start_goal.py --list-meshes

# chọn cho một mesh khác
.venv/bin/python tools/data/set_start_goal.py \
  --mesh data/processed/meshes/cliff.off --pick

# chọn cho mọi mesh còn thiếu
.venv/bin/python tools/data/set_start_goal.py --all-meshes
```

`--all-meshes` duyệt theo tên, bỏ qua mesh đã có mission; `--force` để làm lại.

## Chạy không có bàn phím

Nếu không có JSON, không có cờ và không có terminal, tool dừng với:

```
set_start_goal: no saved mission and no terminal to ask on: pass --start X Y Z /
--goal X Y Z, --start-vertex/--goal-vertex or --all-goals
```

Vì vậy `main.py data` trên máy không có bàn phím cần mission đã commit sẵn.

## Đầu ra hiện tại

10 file trong `data/processed/missions/`: city START 792 → 3 GOAL
(1810, 1910, 1518); 2 fixture START 1 theo reference (cliff, demo_mesh); 7 fixture
còn lại START 0 all-goals (J17, L, cube, dome, icosahedron, star, terrain).

## Liên quan

- [`triangulation.md`](triangulation.md) — sinh bề mặt mà mission trỏ tới.
- [`../plan/run_funnel.md`](../plan/run_funnel.md) — đọc mission để lập tuyến.
- [`../../data-format.md`](../../data-format.md) — schema `mission.json`.
- [`../main.md`](../main.md) — stage `data` gọi bước này với `--refresh-changed`.
