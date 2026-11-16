# Đầu ra

Stage `data` ghi vào đây. Toàn bộ thư mục nằm trong `.gitignore` (trừ tệp này):
mọi thứ ở đây sinh lại được bằng `python3 main.py data`.

| Đường dẫn | Nội dung | Bước sinh |
| --- | --- | --- |
| `data_viz/<tên>.png` | Ảnh từng mesh, có đường tham chiếu màu đỏ nếu có | 5 |
| `data_viz/<tên>-compare.png` | So sánh scene chuẩn hoá với bề mặt (`--scene`) | 5 (thủ công) |

Lựa chọn START/GOAL **không** nằm ở đây: đó là đầu vào được lưu trong Git tại
`data/processed/missions/<mesh>.json`, để lần chạy sau không phải chọn lại.
