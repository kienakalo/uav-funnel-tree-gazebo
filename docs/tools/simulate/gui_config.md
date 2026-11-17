# `tools/simulate/gui_config.py`

| | |
| --- | --- |
| Stage | `simulate` — chuẩn bị GUI |
| Vào | `world_metadata.json` (có `camera_pose`) |
| Ra | `$HOME/.gz/sim/10/gui.config` của phiên chạy |
| Cờ | `--metadata`, `--output` |

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
<plugin filename="MarkerManager" … />
```

- Chỉ giữ 3D view + các plugin cần thiết, nên thành phố chiếm gần hết cửa sổ
  (không có panel World/Entity Tree bên phải).
- `MarkerManager` vẽ vệt bay mà plugin publish lên `/marker`.
- Không có `WorldControl`: world đã chạy bằng `-r`.

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

Ví dụ g1 của lần bay đã lưu (`results/runs/cell5`, mission cũ START 182 tại
−100, −95): `[-100, -122.5, 39.519, 0, 19.471, 45]` → camera ở góc tây nam, cao
39,5 m, nhìn xuống 19,5°, thấy trọn tuyến 134 m. Đổi START/GOAL thì camera phải
tính lại từ `world_metadata.json` của mission mới.

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
