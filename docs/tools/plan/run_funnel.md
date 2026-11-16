# `run_funnel.py`

| | |
| --- | --- |
| Stage | `plan` bước 1 |
| Vào | `data/processed/missions/*.json` và mesh ghi trong mission |
| Ra | `generated/routes/<mission>.json` |
| Cờ | `--mission` (lặp lại), `--input`, `--output`, `--seconds` (300), `--max-nodes` (200 000), `--no-clipping` |

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

## Vì sao mỗi goal một lượt

Một lượt chung giữ frontier theo goal xa nhất; trên bề mặt thành phố (646
secondary source) điều đó làm số lần lan truyền tăng mạnh. Đo được:

| Cách | Số lần lan truyền | Thời gian |
| --- | --- | --- |
| Gộp 3 goal | 395 | ~257 s |
| Mỗi goal một lượt | 253 | ~187 s |

## Schema đầu ra

```json
{
  "mission": "data/processed/missions/city.standardized.triangulation.json",
  "mission_sha256": "…",
  "mesh": "data/processed/meshes/city.standardized.triangulation.off",
  "mesh_sha256": "…",
  "source": 182,
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
    {"id": "g1", "vertex": 1275, "length": 133.71, "waypoints": [[x,y,z], …]}
  ],
  "stats": {"sources_considered": 647, "propagations": 253,
            "mode": "per-goal", "clipping": true},
  "planning_seconds": 189.4,
  "environment": {"python": "3.14.8", "numpy": "2.5.4"}
}
```

| Trường | Ý nghĩa |
| --- | --- |
| `length` | Tổng Euclid giữa các waypoint liên tiếp (đường trên mặt) |
| `waypoints` | Toạ độ 3D của các điểm gãy trên mặt, gồm cả START và đích |
| `source` | Đỉnh START |
| `solver.module_sha256` | Hash của `algo/funnel_tree.py` lúc chạy |
| `stats.propagations` | Số lần lan truyền thực tế (chỉ số đo hiệu năng) |
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
.venv/bin/python tools/plan/run_funnel.py --mission data/processed/missions/cliff.json
.venv/bin/python tools/plan/run_funnel.py --seconds 600
```
