---
title: build_world.py
aliases:
  - build_world
type: tool
stage: simulate
source: tools/simulate/build_world.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/simulate
---

# `build_world.py`

> [!abstract] Mục đích
> Biến một tuyến đã lập thành **một world Gazebo**: visual GLB, collision STL
> đã decimate, SDF có drone và tuyến, cùng `flown_route.json` làm hợp đồng cho
> plugin bay.

> [!info] Vị trí
> **File** `tools/simulate/build_world.py` — stage `simulate`, bước 1  
> **Thuật toán** Vertex clustering để decimate collision, Douglas–Peucker để rút gọn tuyến, dựng SDF bằng ElementTree  
> **Vào** `generated/routes/<mission>.routes.json`, bề mặt trong `route.mesh`, scene chuẩn hoá  
> **Ra** `generated/simulate/<mission>-<goal>/` — 6 file  
> **Cờ** `--mission`, `--route`, `--goal`, `--list-goals`, `--scene`, `--output`, `--collision-grid`, `--collision {decimated,full}`, `--visual {glb,stl}`, `--simplify M`, `--speed`, `--max-accel`, `--dwell`, `--start-delay`, `--surface`, `--check`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `fail(message)` | chuỗi | thoát 1 | In `build_world: …` rồi dừng |
| `relative(path)`, `sha256(path)` | đường dẫn | đường dẫn gọn / hash | Ghi hash bề mặt, scene và route vào `world_metadata.json` |
| `triangle_areas(points, faces)` | lưới | mảng diện tích `M` | Loại tam giác suy biến (`≤ 1e-12`) và đếm tam giác còn lại sau decimate |
| `load_route(path)` | route JSON | `dict` + hash | Đọc tuyến của stage `plan`, kiểm mesh/SHA |
| `choose_goal(record, goal)` | route + `--goal` | `(goal, vertex, waypoints)` | Fail-closed: thiếu hoặc sai goal thì dừng kèm danh sách |
| `world_name(mission, goal)` | mission + goal | `funnel_sim_<stem>_<goal>` | Đặt tên world và model nhất quán |
| `build_meshes(scene, surface, out, collision_cell, full_collision, visual_format, with_surface)` | scene, bề mặt, thư mục ra, tham số | `dict` thống kê mesh | Ghi `city.sim.glb` (có NORMAL), `city.sim.collision.stl`, `surface.stl` |
| `decimate(points, faces, cell)` | lưới + ô gom | `(points, faces, stats)` | Vertex clustering: gom đỉnh theo ô, bỏ mặt suy biến/trùng |
| `write_stl(path, points, faces)` | lưới | số tam giác | Ghi STL nhị phân; từ chối tam giác suy biến |
| `simplify(points, tolerance)` | polyline 3D + dung sai | polyline rút gọn | Douglas–Peucker, giữ đường trong `tolerance` |
| `camera_pose(waypoints)` | waypoint | 6 số (độ) | Camera phía tây-nam, khung trọn tuyến |
| `build_route(...)` | route, goal, waypoint, tham số bay | `dict` `flown_route.json` | Hợp đồng world ↔ plugin: waypoint, speed, accel, delay, dwell |
| `add_route_line(world_element, waypoints, radius=0.15)` | cây SDF | thêm phần tử | Ống tuyến + chấm màu ở start/goal/waypoint |
| `mesh_element(parent, uri, scale=None)` | cây SDF + URI tương đối | phần tử `<mesh>` | Gắn visual/collision vào file, không nhúng dữ liệu vào SDF |
| `build_sdf(out, world, route, meshes, surface_stl)` | mọi mảnh đã dựng | `funnel_physics.sdf` | Ghép physics, ánh sáng, city, drone, plugin loader |
| `check_world(out, route_record, meshes)` | thư mục run | lỗi hoặc `ok` | Kiểm SDF, URI tương đối, `flown_route.json`, kích thước STL |
| `main()` | cờ dòng lệnh | 6 file + `Save at:` | Điều phối toàn bộ, kể cả `--check` |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy; `argparse`, `hashlib`, `json`, `math`, `xml.etree.ElementTree` | Hình học, hash, dựng SDF |
| Nội bộ | `tools/data/glb2off.py: read_glb_scene` | Tam giác thành phố ở Z-up, rộng 200 m |
| Nội bộ | `lib/mesh_glb.py: write_glb` | Ghi visual GLB float32 có NORMAL |
| Nội bộ | `lib/mesh_off.py: read_off` | Đọc bề mặt cho `surface.stl` |
| Dữ liệu | `generated/routes/<mission>.routes.json`, `data/processed/scenes/city.standardized.glb` | Tuyến và hình học thành phố |

## Chạy

```bash
.venv/bin/python tools/simulate/build_world.py \
    --mission city.standardized.triangulation --goal g1
.venv/bin/python tools/simulate/build_world.py \
    --mission city.standardized.triangulation --list-goals
.venv/bin/python tools/simulate/build_world.py --mission city.standardized.triangulation --goal g1 --check
```

## Input

| File | Vai trò | Bắt buộc |
| --- | --- | --- |
| `generated/routes/<mission>.routes.json` | Tuyến của stage `plan`; chứa `waypoints`, `mesh`, `mesh_sha256`, `mission` | Có |
| `data/processed/meshes/<...>.off` | Bề mặt: kiểm SHA khớp route, dùng cho `surface.stl` | Có (đường dẫn lấy từ route) |
| `data/processed/scenes/city.standardized.glb` | Hình học thành phố cho visual + collision | Có (`--scene` đổi) |

Không đọc: mission JSON, STL, world cũ, file Gazebo.

## Chọn goal (fail-closed)

| Tình huống | Hành vi |
| --- | --- |
| `--goal g2` tồn tại | Dùng tuyến đó |
| `--goal` không tồn tại | Lỗi, liệt kê `id (độ dài)` |
| Không có `--goal`, route có 1 tuyến | Dùng luôn, in `Only one route: using --goal …` |
| Không có `--goal`, route có nhiều tuyến | Lỗi, liệt kê `id, vertex, độ dài` |
| `--list-goals` | In bảng rồi thoát, không dựng world |

Lý do: một phiên Gazebo bay một tuyến; đoán hộ sẽ tốn vài phút và có thể bay sai goal.

## Tham số bay

`flown_route.json` là hợp đồng giữa world và plugin; bốn giá trị dưới đây quyết định
cách bay và đều ghi trong file đó (và trong `world_metadata.json`, khóa
`flight`):

| Cờ | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--speed` | 5 m/s | Tốc độ cruise của quỹ đạo tham chiếu |
| `--max-accel` | 3 m/s² | Gia tốc giới hạn của profile tốc độ |
| `--dwell` | 0 s | Dừng bao lâu tại mỗi waypoint; 0 là bay xuyên qua |
| `--start-delay` | 2 s | Chờ trước khi bắt đầu chạy tuyến |

Đổi một trong bốn giá trị này **không** đổi hình học world, chỉ đổi quỹ đạo
tham chiếu, nên phải bay lại và chấm lại thì `validation.json` mới đúng.

## Đầu ra

```
generated/simulate/city.standardized.triangulation-g1/
├── city.sim.glb               8,5 MB   301.482 tam giác, có NORMAL (visual, Z-up)
├── city.sim.collision.stl     1,3 MB    26.296 tam giác (collision, decimate 1 m)
├── surface.stl                220 KB    chỉ khi --surface
├── funnel_physics.sdf          20 KB    world + route + drone
├── flown_route.json           1,5 KB    18 waypoint (đã rút gọn)
└── world_metadata.json        1,3 KB
```

## Xử lý

### 1. Đọc scene và bỏ tam giác suy biến

`read_glb_scene(scene, 200.)` trả 204.682 đỉnh / 301.490 tam giác ở Z-up, rộng
200 m. Scene gốc có **8 tam giác diện tích 0**; chúng bị bỏ một lần cho cả visual
và collision, còn **301.482** tam giác.

### 2. Visual: GLB Z-up có normals

`write_glb(..., normals=True)` ghi một mesh duy nhất (float32) gồm `POSITION`,
`NORMAL` (trung bình có trọng số diện tích) và chỉ số `uint32`.

Hai chi tiết quyết định việc thành phố có hiện trong Gazebo hay không:

1. **Normals**: Ogre2 không tô sáng một mesh chỉ có `POSITION`; thành phố sẽ đen.
2. **`byteLength` của bufferView**: phải là số byte **thực ghi** (chỉ số `uint32`).
   Trước đây trường này lấy từ mảng `int64`, gấp đôi độ dài thật, và Assimp từ
   chối cả file:

   ```
   GLTF: Buffer view with offset/length (2456184/7235568) is out of range.
   ```

   Gazebo vẫn tạo entity `city` nhưng bỏ geometry, nên cửa sổ trống. `write_glb`
   giờ tự kiểm `offset + byteLength ≤ len(buffer)` trước khi ghi.

URI trong SDF là **tên file tương đối** (`city.sim.glb`), nên thư mục run mount ở
đâu cũng chạy: host, máy ảo hay `/work` trong container. `--visual stl` ghi
`city.sim.stl` (≈15 MB) làm đường lui.

### 3. Collision: STL, decimate bằng vertex clustering

`decimate(points, faces, cell)`:

1. `key = floor(points / cell)` — gom đỉnh vào ô lưới.
2. Đại diện mỗi ô = **trung bình** các đỉnh trong ô.
3. Ánh xạ mặt, bỏ mặt có hai đỉnh trùng.
4. Bỏ mặt trùng (giữ hướng của lần xuất hiện đầu).
5. Bỏ mặt diện tích ≤ `1e-12`, đánh lại chỉ số, trả thống kê.

Với `cell = 1 m`: 301.482 → **26.296 tam giác**, 204.682 → **12.402 đỉnh**
(giảm 91,3% tam giác). Bounds lệch tối đa **0,221 m** so với visual (ngưỡng
chấp nhận: `cell`). `--collision full` giữ đủ 301.482 tam giác
(STL 15.074.184 byte ≈ 15 MB) khi cần hình dạng chính xác.

`write_stl` ghi STL nhị phân: header 80 byte, `uint32` số tam giác, mỗi tam giác
50 byte. Hàm **từ chối** tam giác suy biến và toạ độ không hữu hạn.

### 4. Route cho plugin

Chọn goal, ghi `flown_route.json`:

```json
{
  "mission": "data/processed/missions/city.standardized.triangulation.mission.json",
  "goal": "g1", "goal_vertex": 1275,
  "world": "funnel_sim_city_standardized_triangulation_g1",
  "waypoints": [[x, y, z], …],
  "speed": 5.0, "max_acceleration": 3.0,
  "start_delay": 2.0, "dwell": 0.0
}
```

Waypoint lấy từ route của stage `plan`, sau đó **rút gọn Douglas–Peucker** với
`--simplify` (mặc định **0,1 m**); `--simplify 0` tắt.

Số của lần chạy đang lưu (lưới 4 m, START 1133 → 2708 / 2829 / 2240), đọc từ
`world_metadata.json` và `validation.json` của ba lần bay đã lưu ở
`results/runs/cell4`:

| Goal | Trước | Sau | Độ dài polyline (đã rút gọn) | Thời gian bay |
| --- | --- | --- | --- | --- |
| g1 | 50 | **27** | 142,90 m | 35,9 s |
| g2 | 59 | **24** | 127,28 m | 33,2 s |
| g3 | 48 | **26** | 86,16 m | 25,1 s |

(`world_metadata.json` không ghi độ dài cung spline, nên cột đó đã bỏ thay vì
chép lại số của mission cũ.)

`dwell = 0`: plugin bay liên tục, chỉ dừng ở điểm cuối (xem `plugin.md`). Trước
khi làm mượt quỹ đạo, mỗi đoạn là quintic 0 → 0 nên drone dừng ở từng waypoint;
với mission cũ, chuyến g1 khi đó mất 92 s.

### 5. SDF

| Thành phần | Chi tiết |
| --- | --- |
| Physics | `max_step_size 0.001`, RTF 1, plugin `gz-sim-physics-system` |
| Hệ thống | `user-commands`, `scene-broadcaster` |
| Ánh sáng | `sun` directional, `cast_shadows`, diffuse 0.9, hướng `-0.3 -0.5 -1` |
| Scene | ambient 0.7, nền sáng, bật shadow |
| `city` (static) | collision = `city.sim.collision.stl`, visual = `city.sim.glb`, URI tương đối, material xanh `.45 .65 .78` |
| `navigation_surface` (tuỳ chọn) | visual-only, `surface.stl` |
| `planned_route` (static) | ống 0,15 m màu cam giữa các waypoint + cầu 0,45 m (0,7 m ở start/goal); start xanh, goal hồng, giữa vàng cam |
| `drone` | pose = waypoint đầu; link `body`: 1 kg, quán tính 0,1; collision box `0.9×0.6×0.25`; visual quadcopter: thân, 2 cánh tay, 4 rotor cyan |
| Plugin | `gz-sim-python-system-loader-system`, `module_name = funnel_drone_system` |

Không có ground plane: bề mặt đường của city mesh nằm quanh `z ≈ 2,9 m`, nên một
mặt phẳng ở `z = 0` sẽ tạo cảm giác thành phố bị kê cao. Lưới nền của Gazebo vẫn
giúp định hướng.

### 6. `world_metadata.json`

Hash của route/surface/scene, goal, world name, chế độ collision + thống kê
decimate, số waypoint, độ dài, `visual_normals`, `lighting`, và `camera_pose`
(6 số, **độ**; `gui_config.py` đổi 3 góc sang radian khi ghi `gui.config`).
Không chứa timestamp → chạy lại cho đúng byte.

## `--check`

Không ghi gì, chỉ kiểm:

1. SDF parse được, có `world`, model `city` và `drone`, plugin đúng tên.
2. Mọi `<uri>` là **tên file tương đối** và tồn tại cạnh SDF.
3. `flown_route.json` có ≥2 waypoint, `world` khớp tên world trong SDF, `mission`
   khớp route gốc.
4. Kích thước STL khớp số tam giác trong header (`84 + 50·F`).

## Kiểm chứng tại chỗ (đã chạy)

| Kiểm | Kết quả |
| --- | --- |
| GLB đọc lại | 204.682 đỉnh / 301.482 tam giác |
| Assimp 5.3 (trong image Gazebo) đọc `city.sim.glb` | `ok: 1 mesh`, không lỗi bufferView |
| `gz sdf -k` | 3/3 world hợp lệ |
| GUI Gazebo Jetty 10.5.0 | thành phố hiện, có nắng/đổ bóng, route và drone đúng |
| STL đọc lại | 26.296 tam giác, kích thước khớp header, 0 suy biến |
| Bounds STL vs GLB | lệch ≤ 0,221 m (cell 1 m) |
| Rút gọn Douglas–Peucker 0,1 m | 41→27, 46→25, 40→24 điểm |
| Chạy lại 2 lần | 6/6 file cùng SHA256 (trừ `camera_pose` khi đổi tham số) |
| `--collision full` | 15.074.184 byte, `--check` pass |
| `--visual stl` | 15.074.184 byte, `--check` pass |
| `--surface` | `surface.stl` 220.084 byte |
| Thiếu `--goal` | lỗi kèm danh sách 3 goal |
| `--route` một tuyến | tự dùng, in rõ |

## Giới hạn

- Assimp của Gazebo **không** đọc GLB thiếu normals/ sai `byteLength`; dùng
  `check_glb.py` trước khi bay.
- Bề mặt thành phố và lưới nền Gazebo không cùng độ cao (mesh thấp nhất 0 m,
  đường phố ≈ 2,9 m) nên không thêm ground plane.
- Vertex clustering có thể tạo lỗ nhỏ trên vỏ công trình; `--collision full` là
  đường lui.
- Quỹ đạo làm mượt (Catmull-Rom) có thể bo góc khác polyline vài decimet; nếu
  cần bám tuyệt đối, giảm `speed` hoặc dùng `--simplify 0`.
- `camera_pose` chỉ là góc nhìn ban đầu; người xem vẫn xoay/zoom được trong GUI.

## Liên quan

- [`run_simulate.md`](run_simulate.md) — chạy world vừa dựng.
- [`plugin.md`](plugin.md) — đọc `flown_route.json` do bước này ghi.
- [`check_glb.md`](check_glb.md) — kiểm visual bằng đúng Assimp của Gazebo.
- [`gui_config.md`](gui_config.md) — dùng `camera_pose` trong `world_metadata.json`.
