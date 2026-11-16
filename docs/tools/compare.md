# `compare.py`

| | |
| --- | --- |
| Stage | `plan` bước 3 |
| Vào | `data/expected/*.paths.json` + mesh tương ứng |
| Ra | `generated/compare/<mesh>.json`, `generated/compare/summary.json` |
| Cờ | `--expected`, `--meshes`, `--output`, `--seconds` (300), `--tolerance` (1e-4) |

## Reference là gì

`data/expected/<mesh>.paths.json` chứa đường tham chiếu cho **mọi đỉnh**:

```json
{
  "mesh": "L",
  "source": 1,
  "coordinate_system": "model units; ...",
  "paths": [[[x,y,z], …], …]
}
```

- `paths[i]` là đường từ `source` tới đỉnh `i`.
- Toạ độ làm tròn **4 chữ số thập phân** — đây là nguồn sai lệch còn lại.
- Có 5 file: `cliff`, `J17`, `L`, `demo_mesh`, `star`.

## Cách so

1. Chạy Funnel từ **`source` ghi trong reference** (không dùng START của mission;
   nhờ vậy so sánh độc lập với lựa chọn mission).
2. Với từng đỉnh:

   ```
   L         = tổng Euclid giữa các waypoint liên tiếp
   rel_error = |L_funnel − L_reference| / L_reference      (L_reference > 0)
             = |L_funnel|                                 (nguồn, L = 0)
   ```

3. `failures` = các đỉnh có `rel_error > tolerance`. Có failure thì ghi file
   xong **thoát khác 0** để stage dừng.

## Ngưỡng

Mặc định `1e-4`. Sai lệch quan sát được là `≤1,7e-5`, phát sinh từ việc reference
làm tròn 4 chữ số (một đoạn dài 2 m sai 1e-4 m đã cho 5e-5 tương đối). Đặt
`--tolerance 1e-5` sẽ bắt đầu báo fail ở `cliff` — đó là kỳ vọng, không phải lỗi.

## Đầu ra từng mesh

```json
{
  "mesh": "cliff",
  "mesh_sha256": "…",
  "reference": "data/expected/cliff.paths.json",
  "source": 1,
  "tolerance": 0.0001,
  "vertices": 7,
  "max_relative_error": 1.72e-05,
  "mean_relative_error": 2.63e-06,
  "failures": [],
  "stats": {"runs": [...], "clipping": true},
  "paths": [
    {"vertex": 5, "reference_length": 2.285536,
     "funnel_length": 2.285575125, "relative_error": 1.7e-05}
  ]
}
```

## `summary.json`

```json
{
  "passed": ["J17", "L", "cliff", "demo_mesh", "star"],
  "failed": [],
  "skipped": ["city.standardized.triangulation", "cube", "dome",
              "icosahedron", "terrain"],
  "tolerance": 0.0001,
  "note": "skipped meshes have no data/expected reference; ..."
}
```

5 mesh bị bỏ qua vì **không có reference**, và dự án không cài solver thứ hai;
một baseline Dijkstra trên đồ thị cạnh chỉ là cận trên, không thay được reference.

## Kết quả hiện tại

| Mesh | Đỉnh | max rel | mean rel |
| --- | --- | --- | --- |
| `L` | 12 | 9,0e-10 | 7,5e-11 |
| `demo_mesh` | 31 | 3,6e-07 | 8,5e-08 |
| `J17` | 10 | 4,8e-06 | 1,7e-06 |
| `star` | 16 | 6,7e-06 | 8,3e-07 |
| `cliff` | 7 | 1,7e-05 | 2,6e-06 |

Tổng 76 đỉnh, 0 failure. Đây là bằng chứng ngoài duy nhất về độ đúng của thuật
toán; các mesh không có reference (kể cả city) chưa có đối chiếu độc lập.

## Giới hạn

- Chỉ so **độ dài**, không so hình học của đường (hai đường khác nhau vẫn có thể
  cùng độ dài).
- Không kiểm tra tuyến nằm trên mặt (việc đó cần một phép kiểm khác).
- `solve` cho mọi đỉnh chỉ hợp với mesh nhỏ; reference hiện tại đều ≤31 đỉnh.
