# Đầu ra

Stage `data` ghi vào đây. Toàn bộ thư mục nằm trong `.gitignore` (trừ tệp này):
mọi thứ ở đây sinh lại được bằng `python3 main.py data`.

| Đường dẫn | Nội dung | Bước sinh |
| --- | --- | --- |
| `data_viz/<tên>.png` | Ảnh từng mesh, có đường tham chiếu màu đỏ nếu có | 5 |
| `data_viz/<tên>-compare.png` | So sánh scene chuẩn hoá với bề mặt (`--scene`) | 5 (thủ công) |
| `missions/data-demo/plan.json` | START/GOAL đã snap, waypoints, độ dài, hash đầu vào | 6 |
| `missions/data-demo/routes.png` | Ảnh 3D tuyến Funnel | 6 |
| `missions/data-demo/funnel_cache.json` | Cache từng source; xoá được, chỉ tốn thời gian | 6 |

`funnel_cache.json` có thể lớn (hàng chục MB) và không phải kết quả: xoá nó chỉ
khiến lần chạy sau lan truyền lại. Manifest kết quả nằm trong `plan.json`.
