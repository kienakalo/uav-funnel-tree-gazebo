---
title: run_funnel.py
aliases:
  - run_funnel
type: tool
stage: plan
source: tools/plan/run_funnel.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/plan
---

# `run_funnel.py`

> [!abstract] Mục đích
> Chạy Funnel Tree trên các mission đã lưu và ghi **một file route cho mỗi
> mission**, kèm hash của mission/mesh/module và giới hạn tài nguyên, để một con
> số luôn truy được về đúng đầu vào sinh ra nó.

> [!info] Vị trí
> **File** `tools/plan/run_funnel.py` — stage `plan`, bước 1  
> **Thuật toán** Funnel Tree: Dijkstra trên secondary source, mỗi source một lần `propagate`, dựng lại bằng `reconstruct`  
> **Vào** `data/processed/missions/*.mission.json` và mesh ghi trong mission  
> **Ra** `generated/routes/<mission>.routes.json`  
> **Cờ** `--mission` (lặp lại), `--input`, `--output`, `--seconds` (300), `--max-nodes` (200 000), `--no-clipping`  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `mission_id(path)` | đường dẫn mission | stem | `cliff.mission.json → cliff`; chấp nhận cả file không hậu tố |
| `load_mission(path)` | JSON mission | `dict` đã kiểm | Kiểm `mesh_sha256`, số đỉnh/mặt và ít nhất một GOAL |
| `route_length(waypoints)` | danh sách `[x, y, z]` | mét | Tổng khoảng cách Euclid giữa các waypoint liên tiếp trên mặt |
| `plan_mission(path, seconds, max_nodes, clipping)` | mission + giới hạn tài nguyên | `dict` route của mission | Gọi `solve_targets` (mỗi goal một lượt với `explicit` nhiều goal), gom `solver`, `routes`, `stats`, `planning_seconds`, `environment` |
| `sha256(path)`, `relative(path)`, `fail(message)` | đường dẫn / chuỗi | hash, đường dẫn gọn, thoát 1 | Ghi hash và in lỗi theo cùng một kiểu |
| `main()` | cờ dòng lệnh | route JSON + `Save at:` | Duyệt mission theo tên, in `[i/N] <tên>: solving` |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | NumPy; `argparse`, `hashlib`, `json`, `math`, `platform`, `time` | Mảng đỉnh, hash, đồng hồ, phiên bản môi trường |
| Nội bộ | `algo/funnel_tree.py: solve_targets` | Tìm đường ngắn nhất tới các goal |
| Nội bộ | `lib/mesh_off.py: read_mesh` | Dựng `Mesh` có kề, góc, khoảng cách |
| Dữ liệu | `data/processed/missions/*.mission.json` | Nguồn START/GOAL duy nhất |

## Quy trình

1. **Đọc mission**, kiểm:
   - `mesh_sha256` khớp file hiện tại;
   - `mesh_vertices`/`mesh_faces` khớp;
   - có ít nhất một GOAL.
2. **Dựng `Mesh`** từ OFF (kề, góc, khoảng cách).
3. **Chạy `solve_targets`** (xem [`funnel_tree.md`](../funnel_tree.md)):
   - `explicit` nhiều goal: **mỗi goal một lượt**;
   - một goal hoặc `all-goals`: một lượt chung.
4. **Ghi JSON** với hash, tham số, số đo.

Mission id lấy từ tên file sau khi bỏ `.mission.json`: `cliff.mission.json` →
`cliff`, route ghi vào `generated/routes/cliff.routes.json` và world là
`cliff-<goal>`. Đặt tên khác (ví dụ `--mission my.cliff.json`) thì id là
`my.cliff`.

Trước mỗi mission, tool in `[i/N] <tên>: solving` để thấy tiến trình. Mission
`city.standardized.triangulation` là ngoại lệ về thời gian: 3 goal, mỗi goal một
lượt tìm kiếm với clipping. Lần đo 18/11/2026 mất **45,0 s** (g1 19,6 s · g2
14,8 s · g3 10,6 s); các fixture còn lại dưới 1 s. Vì vậy `python3 main.py plan`
mất khoảng 1 phút, phần lớn là city — máy chậm hoặc đang tải thì lâu hơn, nên
đừng dùng số giây để so thuật toán.

## Vì sao mỗi goal một lượt

Một lượt chung giữ frontier theo goal xa nhất; trên bề mặt thành phố (646
secondary source) điều đó làm số lần lan truyền tăng mạnh. Cấu hình hiện tại
chạy mỗi goal một lượt và ghi trong route JSON:

| Goal | Số lần lan truyền | Thời gian |
| --- | --- | --- |
| g1 | 49 | 19,4 s |
| g2 | 34 | 14,9 s |
| g3 | 21 | 10,7 s |
| Tổng | 104 | 45,0 s |

Số đọc từ `generated/routes/city.standardized.triangulation.routes.json`
(`stats.propagations`, `routes[].search.seconds`). Thời gian phụ thuộc tải máy,
nên khi so sánh chỉ dùng số lần lan truyền và độ dài.

## Schema đầu ra

```json
{
  "mission": "data/processed/missions/city.standardized.triangulation.mission.json",
  "mission_sha256": "…",
  "mesh": "data/processed/meshes/city.standardized.triangulation.off",
  "mesh_sha256": "…",
  "source": 792,
  "solver": {
    "name": "funnel_tree",
    "module": "algo/funnel_tree.py",
    "module_sha256": "…",
    "timeout_seconds": 300.0,
    "max_nodes": 200000,
    "clipping": true
  },
  "mode": "explicit",
  "routes": [
    {"id": "g1", "vertex": 1810, "length": 142.42, "waypoints": [[x,y,z], …],
     "search": {"propagations": 49, "seconds": 39.34}}
  ],
  "stats": {"sources_considered": 646, "propagations": 104,
            "mode": "per-goal", "clipping": true},
  "planning_seconds": 77.2,
  "environment": {"python": "3.14.8", "numpy": "2.5.4"}
}
```

| Trường | Ý nghĩa |
| --- | --- |
| `length` | Tổng Euclid giữa các waypoint liên tiếp (đường trên mặt) |
| `waypoints` | Toạ độ 3D của các điểm gãy trên mặt, gồm cả START và đích |
| `source` | Đỉnh START |
| `solver.module_sha256` | Hash của `algo/funnel_tree.py` lúc chạy |
| `stats.propagations` | Tổng số lần lan truyền của cả mission (chỉ số đo hiệu năng) |
| `routes[].search` | Chi phí riêng của goal đó (`propagations`, `seconds`); có khi mission nhiều goal, nhờ vậy một dòng trong bảng đo tái lập được từ một lần chạy |
| `planning_seconds` | Thời gian tường; làm file đổi mỗi lần chạy |

## Giới hạn

- `--seconds` áp **mỗi lượt tìm**, nên mission 3 goal có thể chạm 3×300 s.
- `--max-nodes` chặn lan truyền bùng nổ; vượt thì `TimeoutError`/`RuntimeError`.
- Mission `all-goals` dùng một lượt chung cho mọi đỉnh — chỉ hợp với mesh nhỏ
  (fixture ≤49 đỉnh).
- Không kiểm chứng độc lập rằng tuyến nằm trên mặt; thuật toán chỉ tự so độ dài
  dựng lại với khoảng cách nội tại.

## Ví dụ

```bash
.venv/bin/python tools/plan/run_funnel.py                      # mọi mission
.venv/bin/python tools/plan/run_funnel.py --mission data/processed/missions/cliff.mission.json
.venv/bin/python tools/plan/run_funnel.py --seconds 600
```

## Liên quan

- [`../funnel_tree.md`](../funnel_tree.md) — thuật toán `solve_targets` mà bước này gọi.
- [`route_viz.md`](route_viz.md) — vẽ route đã lập mà không chạy lại solver.
- [`compare.md`](compare.md) — đối chiếu độ dài với reference.
- [`../../data-format.md`](../../data-format.md) — schema `routes.json`.
