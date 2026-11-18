---
title: Công cụ trong pipeline
aliases:
  - tools
  - mục lục tool
type: index
stage: all
source: docs/tools/
tags:
  - funnel-tree/index
---

# Công cụ trong pipeline

> [!abstract] Mục đích
> Mục lục các tool của pipeline, sơ đồ dữ liệu giữa ba stage và quy ước chung
> áp dụng cho mọi trang trong `docs/`.

> [!info] Vị trí
> **Phạm vi** 25 trang: 7 tool `data`, 4 tool `plan`, 6 tool `simulate`, 8 trang chung (mục lục, `main.py`, `figures.py`, thuật toán, thư viện, Docker, tái lập, định dạng)  
> **Cách đọc** mỗi trang có callout mục đích, bảng `API chính`, bảng `Phụ thuộc`, rồi phần thuật toán/đo đạc  
> **Định dạng** Markdown chuẩn + YAML frontmatter + callout, đọc được cả trên GitHub và trong Obsidian  

## Cách đọc một trang tool

Mỗi trang trả lời năm câu, theo cùng một thứ tự:

| Phần | Trả lời |
| --- | --- |
| `[!abstract] Mục đích` | File này sinh ra để làm gì, trong 1–2 câu |
| `[!info] Vị trí` | Đường dẫn, stage, dữ liệu vào/ra, cờ, thư viện cần |
| `## API chính` | Từng hàm: đầu vào, đầu ra, việc nó làm |
| `## Phụ thuộc` | Thư viện ngoài, module nội bộ, file dữ liệu |
| `## Liên quan` | Trang trước/sau trong pipeline và trang tham chiếu |

Phần thân giữ thuật toán, số đo và giới hạn — những gì cần trích dẫn khi viết
báo cáo. Frontmatter có `source`, `stage` và `tags` để Obsidian lọc theo stage.

## Luồng dữ liệu

```text
data/raw/scenes/city.glb ──standardize──► data/processed/scenes/city.standardized.glb
                                                  │
                                                  ├─glb2off───────► city.standardized.glb2off.off (+ .params.json)
                                                  └─triangulation──► city.standardized.triangulation.off
                                                                          │
data/processed/missions/<mesh>.mission.json ──────────────────────────────────────┤
                                                                          ▼
                                                                    run_funnel ──► generated/routes/<mission>.routes.json
                                                                                        │
                                                                    route_viz ──────────┴──► .png
                                                                    compare   ──► generated/compare/*.compare.json

data/raw/meshes/*.off ──copy_meshes──► data/processed/meshes/*.off
                      └─off2glb──────► data/processed/scenes/meshes/*.off2glb.glb

generated/routes/*.routes.json ──build_world──► generated/simulate/<mission>-<goal>/
                                          (city.sim.glb, collision.stl,
                                           funnel_physics.sdf, flown_route.json)
                                            │
                               run_simulate ─┴─► physics_telemetry.csv
                                                 telemetry_metadata.json
                                                 gazebo.log
                                            │
                                validate ───┴─► validation.json
                                                 tracking.png (map + error)

Mỗi ảnh .png ở trên đều có sidecar .png.json và chân ảnh ghi tham số sinh ra nó
(lib/figstamp.py); tools/figures.py kiểm tra lại.

main.py --label <tên> ──► results/runs/<tên>/manifest.json + số liệu + ảnh
                          routes.json, routes.png, gN/flown_route.json
                          (không stage nào xoá; compare_runs.py đọc để so sánh)
```

Ba stage một chiều: `plan` đọc kết quả `data`, `simulate` đọc route của `plan`;
không stage nào ghi ngược lại kết quả của stage trước.
Stage `simulate` cần Gazebo nên chạy được riêng (`main.py simulate`), và bare run
vẫn chạy cả ba theo thứ tự.

## Mục lục

| Stage | Tool | File |
| --- | --- | --- |
| — | Chạy pipeline | [`main.md`](main.md) |
| data | Copy fixture | [`copy_meshes.md`](data/copy_meshes.md) |
| data | Chuẩn hoá scene | [`standardize.md`](data/standardize.md) |
| data | OFF → GLB | [`off2glb.md`](data/off2glb.md) |
| data | GLB → OFF (bản xem cho báo cáo) | [`glb2off.md`](data/glb2off.md) |
| data | Dựng bề mặt | [`triangulation.md`](data/triangulation.md) |
| data | Ảnh kiểm tra | [`data_viz.md`](data/data_viz.md) |
| data | Chọn START/GOAL | [`set_start_goal.md`](data/set_start_goal.md) |
| plan | Lập tuyến | [`run_funnel.md`](plan/run_funnel.md) |
| plan | Ảnh tuyến | [`route_viz.md`](plan/route_viz.md) |
| plan | Đối chiếu reference | [`compare.md`](plan/compare.md) |
| plan | So sánh các lần chạy đã lưu | [`compare_runs.md`](plan/compare_runs.md) |
| — | Kiểm tra ảnh ↔ tham số | [`figures.md`](figures.md) |
| — | Đóng gói cả pipeline trong Docker | [`docker.md`](docker.md) |
| simulate | Dựng world + mesh | [`build_world.md`](simulate/build_world.md) |
| simulate | Plugin bay (trajectory + controller) | [`plugin.md`](simulate/plugin.md) |
| simulate | Bay trong Gazebo (+ backup telemetry cũ) | [`run_simulate.md`](simulate/run_simulate.md) |
| simulate | Camera + MarkerManager cho GUI | [`gui_config.md`](simulate/gui_config.md) |
| simulate | Kiểm GLB bằng Assimp | [`check_glb.md`](simulate/check_glb.md) |
| simulate | Chấm kết quả | [`validate.md`](simulate/validate.md) |
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
| Tên tệp | `<stem>.<kind>.json` (`mission`, `routes`, `compare`, `params`); `flown_route.json` cho tuyến plugin bay; archive lưu trước 18/11/2026 giữ `route.json`/`route.png` |
| Ảnh | 150 dpi, `bbox_inches='tight'`, backend `Agg` trừ khi có `--show` |
| World Gazebo | Z-up, tên `funnel_sim_<mission>_<goal>`; visual GLB (có NORMAL), collision STL; URI tương đối |
| Runtime | Container `ghcr.io/openrobotics/gazebo:jetty-full`, GPU NVIDIA qua CDI hoặc Intel qua `/dev/dri` |
| Ảnh Gazebo | Chụp cửa sổ GUI theo thời gian mô phỏng; metadata ghi cách chụp, không phải đầu ra đo |
| Tài liệu | Markdown chuẩn + YAML frontmatter (`title`, `type`, `stage`, `source`, `tags`) + callout; link tương đối, không wikilink, để GitHub và Obsidian cùng đọc được |

Định dạng file: [`../data-format.md`](../data-format.md).

## Liên quan

- [`../data-format.md`](../data-format.md) — định dạng file giữa các stage.
- [`reproducibility.md`](reproducibility.md) — truy vết số liệu.
- [`../../README.md`](../../README.md) — hướng dẫn cài đặt và chạy nhanh.
