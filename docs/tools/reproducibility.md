# Tái lập kết quả

## Nguyên tắc

Mỗi kết quả phải trả lời được: **dữ liệu nào, mã nào, tham số nào**. Vì vậy:

| Kết quả | Định danh được ghi |
| --- | --- |
| Route JSON | SHA256 của mission, của mesh, của `algo/funnel_tree.py` |
| Mission JSON | SHA256 của mesh + số đỉnh/mặt lúc chọn |
| Bề mặt `.off` | SHA256 (ghi trong README của `data/processed`) |
| Scene chuẩn hoá | `source_sha256` trong `extras` |
| Fixture GLB | `source_sha256` trong `extras` |

## Cái gì tất định

| File | Tất định? | Ghi chú |
| --- | --- | --- |
| `data/processed/meshes/*.off` | Có | Copy byte-identical từ `raw/` |
| `data/processed/meshes/city.standardized.triangulation.off` | Có | Phụ thuộc scene + START/GOAL + hằng số |
| `data/processed/scenes/meshes/*.off2glb.glb` | Có | |
| `data/processed/scenes/city.standardized.glb` | Có | Không commit |
| `data/processed/missions/*.json` | Có | Không có timestamp |
| `generated/routes/*.json` | **Không** | `planning_seconds` đổi mỗi lần chạy |
| `generated/compare/*.json` | Có | Không chứa thời gian |

Vì `planning_seconds` là số đo thật, chạy lại `main.py plan` sẽ làm route JSON
dirty trong Git. Đó là lựa chọn có chủ đích: báo cáo cần thời gian chạy.

## Cái gì làm kết quả đổi

| Thay đổi | Ảnh hưởng |
| --- | --- |
| Sửa `city.glb` | Scene chuẩn hoá → bề mặt → mọi route |
| Sửa `cell`, `CLEARANCE`, `HALF_WIDTH`, `MAX_AXIS_SLOPE` | Bề mặt |
| Đổi START/GOAL của triangulation | Bề mặt (lưới và extent) |
| Sửa `algo/funnel_tree.py` | Route + `solver.module_sha256` |
| Đổi mission (START/GOAL) | Route của mission đó |
| Sửa `data/expected/*.paths.json` | Kết quả `compare` |

## Quy trình chạy lại

```bash
python3 main.py data     # tái tạo bề mặt + mission (mission đã có thì giữ)
python3 main.py plan     # route + ảnh + compare
```

Kiểm tra bề mặt không đổi:

```bash
sha256sum data/processed/meshes/city.standardized.triangulation.off
# f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df
```

Nếu khác, ghi SHA cũ/mới + lý do vào
[`../../data/processed/README.md`](../../data/processed/README.md) trước khi
commit.

## Môi trường

- Python 3.14.8, NumPy 2.5.4, Matplotlib 3.11.2, Shapely 2.2.0, Pillow 13.0.0
  (pin trong `requirements.txt`).
- Phiên bản Python và NumPy của lần chạy được ghi trong từng route JSON.
- Gói hệ thống cho cửa sổ 3D: `apt.txt` (Debian/Ubuntu); NixOS dùng `steam-run`
  hoặc symlink `_tkinter` (xem [`../../README.md`](../../README.md)).

## Số liệu để trích dẫn

| Hạng mục | Giá trị |
| --- | --- |
| Bề mặt thành phố | 2.295 đỉnh / 4.400 tam giác / 6.694 cạnh |
| SHA256 bề mặt | `f6e01c6d421f71aec828ae2f71593e7b2d0460604453459eb5e86b2ea47b28df` |
| Route city | 133,71 m · 284,08 m · 140,57 m |
| Thời gian `main.py plan` | ~3 phút 20 giây |
| Đối chiếu reference | 5/5 fixture, sai lệch lớn nhất 1,7e-5 |
| Trạng thái thuật toán | experimental, chưa chứng nhận tối ưu |

## Điều chưa kiểm chứng

Nói rõ khi báo cáo:

1. Tuyến **chưa** được kiểm tra độc lập là nằm trên mặt (chỉ có tự kiểm độ dài
   và đối chiếu reference cho 5 fixture).
2. City và 4 mesh còn lại **không có reference**, nên không có đối chiếu ngoài.
3. Funnel Tree chưa được chứng minh tối ưu trên mặt không lồi.
4. Bề mặt là envelope an toàn, không phải địa hình thật.
