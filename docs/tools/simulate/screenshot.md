# `tools/simulate/screenshot.py`

| | |
| --- | --- |
| Stage | `simulate` — bằng chứng hình ảnh |
| Vào | Cửa sổ Gazebo đang mở, `run_id`, `sim_time`, `phase` |
| Ra | `<tên>.png` + `<tên>.json` (cùng thư mục run) |
| Cờ | `--output`, `--run-id`, `--sim-time`, `--phase`, `--log`, `--list-gazebo` |

## Vì sao có

Báo cáo cần ảnh drone bay trong thành phố. Ảnh phải gắn với một phiên cụ thể và
ghi rõ **cách chụp**, để không bị hiểu nhầm là đầu ra của mô phỏng.

## Cách chụp

1. `hyprctl clients -j` (Hyprland/Wayland) → tìm cửa sổ **class `Gazebo GUI`**
   (hoặc title `Gazebo Sim`). Không dò theo chữ "gazebo" trong title vì cửa sổ
   VS Code chứa tên repo cũng khớp.
2. Bỏ qua các cửa sổ có trong `FUNNEL_IGNORE_WINDOWS` — danh sách cửa sổ Gazebo
   đã mở **trước** phiên, do `run_simulate.sh` ghi lại. Nhờ vậy một cửa sổ cũ
   không bị chụp thay.
3. Nếu có nhiều cửa sổ, chọn cửa sổ diện tích lớn nhất.
4. `grim -g "x,y WxH"` cắt đúng cửa sổ.
5. Không có Hyprland → lùi về ImageMagick `import -window root` (cả màn hình) và
   ghi rõ trong metadata.

## Khi nào chụp

`run_simulate.sh` đọc `nominal_duration` từ `telemetry_metadata.json` và chụp ở
**20 %, 50 %, 80 %** thời lượng, cộng một ảnh khi `phase=complete`:

```
screenshot_t006.png   (g1, 20 % của 30,6 s)
screenshot_t015.png   (50 %)
screenshot_t025.png   (80 %)
screenshot_complete.png
```

Mốc tính theo **thời gian mô phỏng** đọc từ cột `sim_time` của telemetry, không
phải đồng hồ treo tường. Ảnh `complete` được chụp sau khi route kết thúc, trước
khi cửa sổ tự đóng.

## Metadata

```json
{
  "image": "screenshot_t015.png",
  "sha256": "…",
  "bytes": 213052,
  "captured_at": "2026-11-17T14:41:07+07:00",
  "run_id": "20261117_144115-134499",
  "sim_time": 15.0,
  "phase": "moving",
  "display": {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-1"},
  "capture": {"tool": "grim", "command": ["grim", "-g", "21,21 933x1038", "<output>"],
              "window": {"class": "Gazebo GUI", "title": "Gazebo Sim",
                         "at": [21, 21], "size": [933, 1038]}},
  "ignored_windows": [],
  "gazebo_log": "generated/simulate/.../gazebo.log",
  "note": "Screenshot of the Gazebo window; measured results are in
           physics_telemetry.csv and validation.json."
}
```

`--list-gazebo` in address của các cửa sổ đang mở, dùng cho cơ chế bỏ qua ở
trên.

## Giới hạn

- Cần cửa sổ Gazebo thật; chế độ `--headless` không chụp.
- Trên X11 ảnh là cả màn hình (không cắt được cửa sổ), metadata ghi `import`.
- Kích thước/khung ảnh phụ thuộc cách window manager xếp cửa sổ; cùng một máy
  cho cùng kích thước.
- Ảnh **không** thay thế `validation.json`; sai số vẫn đo từ telemetry.
