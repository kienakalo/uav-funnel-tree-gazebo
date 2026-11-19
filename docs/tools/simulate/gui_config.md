---
title: gui_config.py
aliases:
  - gui_config
type: tool
stage: simulate
source: tools/simulate/gui_config.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/simulate
---

# `tools/simulate/gui_config.py`

> [!abstract] Mục đích
> Ghi `gui.config` riêng cho một phiên Gazebo: chỉ giữ 3D view và
> `MarkerManager`, đặt **camera ban đầu** theo tuyến. Gazebo bỏ qua
> `<gui><camera>` trong SDF nên phải làm ở đây.

> [!info] Vị trí
> **File** `tools/simulate/gui_config.py` — stage `simulate`, chuẩn bị GUI  
> **Thuật toán** Template XML cố định; đổi `roll, pitch, yaw` từ độ sang radian, giữ `x, y, z` là mét  
> **Vào** `world_metadata.json` (có `camera_pose`)  
> **Ra** `$HOME/.gz/sim/10/gui.config` của phiên chạy  
> **Cờ** `--metadata`, `--output`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `build(camera_pose)` | 6 số `x y z roll pitch yaw` (độ) | chuỗi XML `gui.config` | Đổi 3 góc sang radian, giữ `x, y, z` là mét, chèn vào template |
| `main()` | `--metadata`, `--output` | ghi file, in đường dẫn | Đọc `camera_pose` từ metadata rồi gọi `build` |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | `argparse`, `json`, `math`, `re`, `pathlib` | CLI, đổi độ → radian, template |
| Dữ liệu | `generated/simulate/<mission>-<goal>/world_metadata.json` | Nguồn `camera_pose` |
| Do | `run_simulate.sh` gọi | Tạo `HOME` tạm và mount vào container |

## Vì sao cần

Gazebo lấy bố cục GUI và **camera ban đầu** từ
`$HOME/.gz/sim/<version>/gui.config`, không lấy từ SDF: thẻ
`<gui><camera>` trong SDF bị bỏ qua kèm cảnh báo
`<gui><camera> can't be converted yet`.

Nếu để mặc định, camera ở `-6 0 6` nằm giữa thành phố, không thấy tuyến.
Nếu thêm `<plugin>` vào SDF, Gazebo **cộng dồn** với cấu hình mặc định và tạo
panel trùng. Vì vậy `run_simulate.sh` tạo một `HOME` tạm, ghi `gui.config`
riêng, rồi mount vào container.

## Nội dung file

```xml
<window><width>1280</width><height>800</height> … </window>

<plugin filename="MinimalScene" name="3D View">
  <gz-gui>
    <title>3D View</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="string" key="state">docked</property>
  </gz-gui>
  <engine>ogre2</engine>
  <scene>scene</scene>
  <ambient_light>0.6 0.6 0.6</ambient_light>
  <background_color>0.72 0.81 0.9</background_color>
  <camera_pose>x y z roll pitch yaw</camera_pose>
</plugin>

<plugin filename="GzSceneManager" … />
<plugin filename="InteractiveViewControl" … />
<plugin filename="WorldControl" … />
<plugin filename="MarkerManager" … />
```

- Chỉ giữ 3D view + các plugin cần thiết, nên thành phố chiếm gần hết cửa sổ
  (không có panel World/Entity Tree bên phải).
- `MarkerManager` vẽ vệt bay mà plugin publish lên `/marker`.
- `WorldControl` là thanh **play/pause + step** neo ở góc dưới-trái của 3D view:
  bấm pause thì world dừng, plugin bỏ qua tick và `run_simulate.sh` nhận ra world
  đứng yên nên không tính giờ đó vào `--timeout`. `start_paused` để `false` vì
  script tự chạy world bằng `run_to_sim_time`/`pause: false`.

## Camera

`build_world.py` tính `camera_pose` từ bounding box của **waypoint**:

```
d = max(45, span_xy · 0.5)        # span = cạnh dài hơn của hộp bao tuyến
h = 0.5 · d
vị trí = tâm − (d, d) + (0, 0, h)
yaw   = 45°                        # nhìn về phía đông bắc
pitch = atan2(h, d·√2)             # dương = nhìn xuống
```

`world_metadata.json` lưu **độ**; `gui_config.py` chỉ đổi `roll, pitch, yaw`
sang radian, còn `x, y, z` giữ nguyên mét (đổi cả 6 sẽ đưa camera về gần gốc toạ
độ — lỗi đã gặp và sửa).

Ví dụ g1 của mission hiện tại (START 792): `[-38.752, -73.371, 40.5, 0,
19.471, 45]` → camera lùi về phía nam, cao 40,5 m, nhìn xuống 19,5°, thấy trọn
tuyến 142 m. Đổi START/GOAL thì camera phải tính lại từ `world_metadata.json`
của mission mới.

## Chạy tay

```bash
python3 tools/simulate/gui_config.py \
  --metadata generated/simulate/city.standardized.triangulation-g1/world_metadata.json \
  --output /tmp/gui-home/.gz/sim/10/gui.config
```

## Giới hạn

- Đường dẫn phải đúng `$HOME/.gz/sim/10/` của bản Gazebo đang dùng (Jetty =
  `10`).
- File này chỉ đặt camera **ban đầu**; người xem vẫn xoay/zoom được.
- Nếu Gazebo đổi tên plugin GUI, cần cập nhật template.

## Liên quan

- [`build_world.md`](build_world.md) — tính `camera_pose` từ bounding box tuyến.
- [`run_simulate.md`](run_simulate.md) — dựng `HOME` tạm và mount file này.
- [`plugin.md`](plugin.md) — publish vệt bay mà `MarkerManager` vẽ.
