# `build_world.py`

| | |
| --- | --- |
| Stage | `simulate` bước 1 |
| Vào | `generated/routes/<mission>.json`, bề mặt trong `route.mesh`, scene chuẩn hoá |
| Ra | `generated/simulate/<mission>-<goal>/` (6 file) |
| Cờ | `--mission`, `--route`, `--goal`, `--list-goals`, `--scene`, `--output`, `--collision-grid`, `--collision {decimated,full}`, `--visual {glb,stl}`, `--surface`, `--check` |

## Input

| File | Vai trò | Bắt buộc |
| --- | --- | --- |
| `generated/routes/<mission>.json` | Tuyến của stage `plan`; chứa `waypoints`, `mesh`, `mesh_sha256`, `mission` | Có |
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

## Đầu ra

```
generated/simulate/city.standardized.triangulation-g1/
├── city.sim.glb               5,8 MB   301.482 tam giác (visual, Z-up)
├── city.sim.collision.stl     1,3 MB    26.296 tam giác (collision, decimate 1 m)
├── surface.stl                220 KB    chỉ khi --surface
├── funnel_physics.sdf         2,9 KB
├── route.json                 5,0 KB    72 waypoint
└── world_metadata.json        1,1 KB
```

## Xử lý

### 1. Đọc scene và bỏ tam giác suy biến

`read_glb_scene(scene, 200.)` trả 204.682 đỉnh / 301.490 tam giác ở Z-up, rộng 200 m.
Scene gốc có **8 tam giác diện tích 0**; chúng bị bỏ một lần cho cả visual và
collision, còn **301.482** tam giác.

### 2. Visual: GLB Z-up

`write_glb` ghi một mesh duy nhất (float32) với `extras`: frame, hash scene, số
đỉnh/mặt. Vì Gazebo **không** xoay glTF từ Y-up, phải dùng bản Z-up này thay
cho scene chuẩn hoá. `--visual stl` ghi `city.sim.stl` nếu assimp của Gazebo
không đọc được `.glb`.

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

`write_stl` ghi STL nhị phân: header 80 byte, `uint32` số tam giác, mỗi tam
giác 50 byte (normal 3×f4, 3 đỉnh 9×f4, attribute u2). Hàm **từ chối** tam
giác suy biến và toạ độ không hữu hạn.

### 4. Route cho plugin

Chọn goal, ghi `route.json`:

```json
{
  "mission": "data/processed/missions/city.standardized.triangulation.json",
  "goal": "g1", "goal_vertex": 1275,
  "world": "funnel_sim_city_standardized_triangulation_g1",
  "waypoints": [[x, y, z], …],
  "speed": 5.0, "max_acceleration": 3.0,
  "start_delay": 2.0, "dwell": 1.5
}
```

Waypoint lấy nguyên từ route của stage `plan` (đã kiểm: khớp 100%, 72 điểm,
133,71 m).

### 5. SDF

World gồm:

| Thành phần | Chi tiết |
| --- | --- |
| Physics | `max_step_size 0.001`, RTF 1, plugin `gz-sim-physics-system` |
| Hệ thống | `user-commands`, `scene-broadcaster` |
| `city` (static) | collision = `city.sim.collision.stl`, visual = `city.sim.glb`, URI `file://` tuyệt đối |
| `navigation_surface` (tuỳ chọn) | visual-only, `surface.stl` |
| `drone` | pose = waypoint đầu; link `body`: khối lượng 1 kg, quán tính 0,01; collision box `0.9×0.6×0.25`; locator cầu phát sáng ở `z+2,1` |
| Plugin | `gz-sim-python-system-loader-system`, `module_name = funnel_drone_system` |

### 6. `world_metadata.json`

Hash của route/surface/scene, goal, world name, chế độ collision + thống kê
decimate, số waypoint và độ dài. Không chứa timestamp → chạy lại cho đúng byte.

## `--check`

Không ghi gì, chỉ kiểm:

1. SDF parse được, có `world`, model `city` và `drone`, plugin đúng tên.
2. Mọi `<uri>` là `file://` tuyệt đối và file tồn tại.
3. `route.json` có ≥2 waypoint, `world` khớp tên world trong SDF, `mission`
   khớp route gốc.
4. Kích thước STL khớp số tam giác trong header (`84 + 50·F`).

## Kiểm chứng tại chỗ (đã chạy)

| Kiểm | Kết quả |
| --- | --- |
| GLB đọc lại | 204.682 đỉnh / 301.482 tam giác |
| STL đọc lại | 26.296 tam giác, kích thước khớp header, 0 suy biến |
| Bounds STL vs GLB | lệch ≤ 0,221 m (cell 1 m) |
| Waypoint vs route plan | khớp tuyệt đối |
| Chạy lại 2 lần | 5/5 file cùng SHA256 |
| `--collision full` | 15.074.184 byte, `--check` pass |
| `--visual stl` | 15.074.184 byte, `--check` pass |
| `--surface` | `surface.stl` 220.084 byte |
| Thiếu `--goal` | lỗi kèm danh sách 3 goal |
| `--route` một tuyến | tự dùng, in rõ |

## Giới hạn

- **Chưa chạy Gazebo**: máy hiện tại không có `gz`, nên SDF/GLB mới chỉ được
  kiểm bằng parse và đọc lại, chưa được Gazebo nạp thử.
- Phụ thuộc assimp của Gazebo Jetty có đọc `.glb`; nếu không, dùng `--visual stl`.
- Vertex clustering có thể tạo lỗ nhỏ trên vỏ công trình; `--collision full`
  là đường lui.
- Plugin `funnel_drone_system` chưa được port (bước 2); SDF đã trỏ tới nó.
