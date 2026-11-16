# `copy_meshes.py`

| | |
| --- | --- |
| Stage | `data` bước 1 |
| Vào | `data/raw/meshes/*.off` (9 fixture) |
| Ra | `data/processed/meshes/*.off` |
| Cờ | `--write` hoặc `--check` (bắt buộc một trong hai) |

## Việc nó làm

1. Với mỗi `.off` trong `data/raw/meshes/`, đọc và kiểm bằng
   `lib/mesh_off.py: read_off`:
   - dòng đầu `OFF`, header `V F E` đọc được;
   - `V ≥ 3`, `F ≥ 1`, số dòng = `2 + V + F`;
   - mỗi mặt là tam giác, chỉ số nằm trong `0..V−1`;
   - toạ độ hữu hạn.
2. `shutil.copyfile` sang `data/processed/meshes/` — **byte-identical**, không
   parse lại rồi ghi.
3. `--check` so byte từng cặp raw/processed; lệch thì liệt kê và thoát khác 0.

## Vì sao copy thay vì để tool đọc `raw/`

- Downstream chỉ đọc `data/processed/`; `raw/` là nguồn bất biến.
- Bản copy tách "nguồn" khỏi "đầu vào đã kiểm tra": nếu ai sửa nhầm một bên,
  `--check` phát hiện ngay.
- Không biến đổi hình học, nên hash của fixture trong `raw/` và `processed/`
  trùng nhau.

## Đầu ra

```
Save at: data/processed/meshes/<tên>.off     (9 dòng)
Processed meshes: 9 copies consistent        (khi --check)
```

## Khi nào chạy lại

- Thêm fixture mới vào `data/raw/meshes/`.
- Nghi ngờ `data/processed/` bị sửa tay.

## Giới hạn

Chỉ kiểm cấu trúc file, không kiểm topology (non-manifold, fan rời). Việc đó do
`Mesh` làm khi `set_start_goal` hoặc `run_funnel` đọc mesh.
