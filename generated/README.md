# Đầu ra

Stage `data` và `plan` ghi vào đây. Phần lớn nằm trong `.gitignore`; chỉ
`routes/`, `compare/` và tệp này được giữ trong Git vì là kết quả của stage
`plan`.

| Đường dẫn | Nội dung | Bước sinh |
| --- | --- | --- |
| `data_viz/<tên>.png` | Ảnh từng mesh, có đường tham chiếu màu đỏ nếu có | `data` 5 |
| `routes/<mission>.json` | Tuyến Funnel: waypoint, độ dài, hash, tham số, thời gian | `plan` 1 |
| `routes/<mission>.png` | Ảnh bề mặt + các tuyến | `plan` 2 |
| `compare/<mesh>.json` | So từng đỉnh với `data/expected` | `plan` 3 |
| `compare/summary.json` | Mesh đạt / không đạt / bị bỏ qua | `plan` 3 |

Lựa chọn START/GOAL **không** nằm ở đây: đó là đầu vào được lưu trong Git tại
`data/processed/missions/<mesh>.json`, để lần chạy sau không phải chọn lại.
