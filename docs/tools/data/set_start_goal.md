# `set_start_goal.py`

| | |
| --- | --- |
| Stage | `data` bước 7 |
| Vào | Một `.off` + lựa chọn của người dùng |
| Ra | `data/processed/missions/<mesh>.json` |
| Cờ | `--mesh`, `--mission`, `--output`, `--list-meshes`, `--all-meshes`, `--start`, `--start-vertex`, `--goal`, `--goal-vertex`, `--all-goals`, `--pick`, `--snap`, `--max-snap`, `--force` |
| Ghi chú | `--all-meshes` bỏ qua `*.glb2off.off`: đó là bản xem toàn scene, các vỏ lặp toạ độ đỉnh nên không dựng được `Mesh` |

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
5. **Ghi JSON** (đường dẫn mặc định `data/processed/missions/<mesh>.json`).

## Giao diện chọn điểm

| Cách | Lệnh | Ghi chú |
| --- | --- | --- |
| Bàn phím | `set_start_goal.py` | Gõ chỉ số hoặc `x y z`; dòng trống kết thúc danh sách GOAL; `all` cho mọi đỉnh còn lại |
| Chuột | `set_start_goal.py --pick` | `s` = START, `g` = GOAL, `u` = bỏ GOAL cuối, Enter = lưu |
| Không tương tác | `--start-vertex 1 --all-goals` | Dùng cho script/CI |

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
data/processed/missions/city.standardized.triangulation.json: bề mặt đã đổi, cập nhật lại lựa chọn cũ
  START đỉnh 182 -> 182 (0.000 m)
  g1 đỉnh 1275 -> 1275 (0.000 m)
  ...
Save at: data/processed/missions/city.standardized.triangulation.json

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

10 file trong `data/processed/missions/`: city START 182 → 3 GOAL
(1275, 2112, 1147); 5 fixture START 1 (theo reference); 4 fixture còn lại START 0
all-goals.
