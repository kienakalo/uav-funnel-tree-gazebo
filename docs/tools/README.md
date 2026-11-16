# Công cụ trong pipeline

Mỗi tool một file, mô tả dữ liệu vào/ra, cờ dòng lệnh, thuật toán và giới hạn —
đủ để trích dẫn khi viết báo cáo.

## Luồng dữ liệu

```text
data/raw/scenes/city.glb ──standardize──► data/processed/scenes/city.standardized.glb
                                                  │
                                                  └─triangulation──► city.standardized.triangulation.off
                                                                          │
data/processed/missions/<mesh>.json ──────────────────────────────────────┤
                                                                          ▼
                                                                    run_funnel ──► generated/routes/<mission>.json
                                                                                        │
                                                                    route_viz ──────────┴──► .png
                                                                    compare   ──► generated/compare/*.json

data/raw/meshes/*.off ──copy_meshes──► data/processed/meshes/*.off
                      └─off2glb──────► data/processed/scenes/meshes/*.off2glb.glb
```

Hai stage độc lập một chiều: `plan` chỉ đọc kết quả của `data`.

## Mục lục

| Stage | Tool | File |
| --- | --- | --- |
| — | Chạy pipeline | [`main.md`](main.md) |
| data | Copy fixture | [`copy_meshes.md`](copy_meshes.md) |
| data | Chuẩn hoá scene | [`standardize.md`](standardize.md) |
| data | OFF → GLB | [`off2glb.md`](off2glb.md) |
| data | GLB → OFF | [`glb2off.md`](glb2off.md) |
| data | Dựng bề mặt | [`triangulation.md`](triangulation.md) |
| data | Ảnh kiểm tra | [`data_viz.md`](data_viz.md) |
| data | Chọn START/GOAL | [`set_start_goal.md`](set_start_goal.md) |
| plan | Lập tuyến | [`run_funnel.md`](run_funnel.md) |
| plan | Ảnh tuyến | [`route_viz.md`](route_viz.md) |
| plan | Đối chiếu reference | [`compare.md`](compare.md) |
| — | Thuật toán | [`funnel_tree.md`](funnel_tree.md) |
| — | Thư viện dùng chung | [`lib.md`](lib.md) |
| — | Tái lập | [`reproducibility.md`](reproducibility.md) |

## Quy ước chung

| Chủ đề | Quy ước |
| --- | --- |
| Trục | GLB giữ **Y-up** (glTF); mọi tính toán dùng **Z-up** |
| Đơn vị | Mét sau chuẩn hoá; scene gốc giữ đơn vị của nó |
| Bề rộng chuẩn | 200 m (trục lớn hơn của XY) |
| OFF | Chỉ mặt tam giác; `E` trong header không được tin, cạnh thật suy từ mặt |
| Ghi số | `%.17g` trong OFF, float32 trong GLB |
| Sai số so sánh | Độ dài: tương đối `1e-6` (nội bộ), `1e-4` (reference, do làm tròn 4 chữ số) |
| Hash | SHA256 của mesh, mission, module thuật toán được ghi trong kết quả |
| Ảnh | 150 dpi, `bbox_inches='tight'`, backend `Agg` trừ khi có `--show` |

Định dạng file: [`../data-format.md`](../data-format.md).
