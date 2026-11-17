# `main.py`

| | |
| --- | --- |
| Vai trò | Chạy một hoặc nhiều stage bằng subprocess |
| Vào | Tên stage (`data`, `plan`, `simulate`, `flow`) + cờ |
| Ra | Không có file riêng; chạy các tool và dừng ở lỗi đầu tiên |

## Cách chọn interpreter

```python
VENV = ROOT / '.venv/bin/python'
PYTHON = str(VENV) if VENV.is_file() else sys.executable
```

Mọi lệnh trong `STAGES` dùng `PYTHON` này, nên venv được áp dụng cả khi bạn gõ
`python3 main.py`. Trên Windows, `main.py` không thấy `.venv/bin/python` và rơi
về `sys.executable` — khi đó phải activate venv trước.

## Ba stage

| Stage | Số bước | Nội dung |
| --- | --- | --- |
| `data` | 6 | copy fixtures → standardize → off2glb → triangulation → data_viz → set_start_goal |
| `plan` | 3 | run_funnel → route_viz → compare |
| `simulate` | 3 × số goal | build_world → run_simulate `--no-build` → validate, lặp cho từng goal (mặc định cả g1, g2, g3) |

Không ghi stage nào thì chạy **cả ba theo thứ tự data → plan → simulate**. Muốn
một stage thì ghi tên: `python3 main.py plan`.

Thứ tự trong `data` có chủ đích:

1. `copy_meshes` chạy trước để fixture có mặt trong `data/processed/`.
2. `standardize` tạo scene chuẩn hoá mà `triangulation` đọc.
3. `off2glb` độc lập với 1–2, chỉ tạo bản xem.
4. `triangulation` ghi đè bề mặt (luôn kèm `--force`).
5. `data_viz` render mọi `.off` **sau** khi bề mặt đã có.
6. `set_start_goal` chạy cuối để nếu nó cần hỏi thì các bước trước đã xong.

## Cờ

| Cờ | Tác dụng |
| --- | --- |
| `flow` | In các lệnh rồi thoát |
| `--dry-run` | In lệnh, không chạy |
| `--quiet` | Ẩn output của tool, chỉ in bước + thời gian; output hiện ra khi bước lỗi |
| `--all-meshes` / `--no-all-meshes` | Bước 6 chọn cho mọi mesh (mặc định) hay chỉ bề mặt |
| `--force-missions` | Chỉ với `--all-meshes`: chọn lại cả mesh đã có mission |
| `--mission STEM` | `simulate`: route stem (mặc định `city.standardized.triangulation`) |
| `--goal ID` | `simulate`: chỉ bay một goal; mặc định bay mọi goal của route |
| `--headless` | `simulate`: `gz sim -s -r`, không GUI |
| `--software` | `simulate`: ép software rendering |
| `--show-surface` | `simulate`: `build_world --surface` |
| `--max-error M` | `simulate`: ngưỡng cho `validate` (mặc định 1,0 m) |
| `--no-png` | `simulate`: bỏ `tracking.png` |
| `--container` / `--no-container` | `simulate`: bay trong container (mặc định) hay dùng `gz` trên máy |
| `--image NAME` | `simulate`: image Gazebo (mặc định `ghcr.io/openrobotics/gazebo:jetty-full`) |
| `--gpu auto\|nvidia\|intel\|software` | `simulate`: đường render cho GUI |
| `--keep-open` | `simulate`: không tự đóng cửa sổ khi route xong |
| `--pull` | `simulate`: `docker pull` image trước khi chạy |

`--force-missions` không đi cùng `--no-all-meshes` (báo lỗi), vì chọn lại một
mesh nên gọi trực tiếp `set_start_goal.py --force`.

## Đầu ra trên terminal

Mỗi stage được đóng khung, mỗi bước có nhãn riêng và output của tool được thụt
vào, nên không còn một dòng chảy phẳng:

```text
========================================================================
Stage 2/3: plan — funnel routes, route images and the reference comparison
3 step(s)
========================================================================

[plan 1/3] tools/plan/run_funnel.py
    [1/10] J17: solving
    J17: 9 route(s), dài nhất 3.464, 0.0s
    Save at: generated/routes/J17.json
    ...
    done in 190.4 s

plan: ok in 191.2 s
```

- Đường dẫn tuyệt đối dưới repo được rút thành đường dẫn tương đối.
- Bước dài in tiến trình riêng (ví dụ `[3/10] city...: solving` trước khi giải).
- Cuối mỗi stage in tổng thời gian; chạy nhiều stage in thêm tổng cuối.
- `--quiet` giữ nguyên khung bước nhưng ẩn output tool; nếu bước lỗi thì output
  được in ra để đọc lỗi.

## Hành vi khi lỗi

`run_stage` chạy tuần tự; lệnh nào trả mã khác 0 thì dừng ngay:

```python
completed = subprocess.run(command, cwd=ROOT)
if completed.returncode:
    raise SystemExit(f'Stage {name} failed: {printable}')
```

Không có cơ chế bỏ qua lỗi hay chạy tiếp — muốn bỏ một bước thì sửa `STAGES`
hoặc gọi tool trực tiếp.

## Ví dụ

```bash
python3 main.py                     # data -> plan -> simulate
python3 main.py flow                # xem lệnh
python3 main.py data --dry-run
python3 main.py plan
python3 main.py simulate --goal g2 --headless
python3 main.py data --no-all-meshes
python3 main.py data --force-missions
```

## Mở rộng

Thêm stage = thêm một khóa vào `STAGES` và `DESCRIPTIONS`; mỗi phần tử là một
`list` lệnh tuyệt đối (phần tử đầu là interpreter). Không cần sửa `run_stage`.
