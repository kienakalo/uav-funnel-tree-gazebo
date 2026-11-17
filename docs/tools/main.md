# `main.py`

| | |
| --- | --- |
| Vai trò | Chạy một hoặc nhiều stage bằng subprocess |
| Vào | Tên stage (`data`, `plan`, `simulate`, `flow`) + cờ |
| Ra | Chạy các tool và dừng ở lỗi đầu tiên; ghi `generated/parameters.json` |

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
| `--dry-run` | In lệnh và câu hỏi tham số, không chạy, không hỏi, không xoá |
| `--fresh` | Xoá kết quả cũ rồi chạy cả ba stage, không hỏi (chỉ dùng khi không ghi stage) |
| `--no-ask` | Không hỏi gì: giữ toàn bộ tham số mặc định |
| `--quiet` | Ẩn output của tool, chỉ in bước + thời gian; output hiện ra khi bước lỗi |
| `--all-meshes` / `--no-all-meshes` | Bước 6 chọn cho mọi mesh (mặc định) hay chỉ bề mặt |
| `--force-missions` | Chỉ với `--all-meshes`: chọn lại cả mesh đã có mission |
| `--mission STEM` | `simulate`: route stem (mặc định `city.standardized.triangulation`) |
| `--goal ID` | `simulate`: chỉ bay một goal; mặc định bay mọi goal của route |
| `--headless` | `simulate`: `gz sim -s -r`, không GUI |
| `--software` | `simulate`: ép software rendering |
| `--show-surface` | `simulate`: `build_world --surface` |
| `--max-error M` | `simulate`: ngưỡng cho `validate`; thành mặc định của câu hỏi chấm điểm (1,0 m) |
| `--no-png` | `simulate`: bỏ `tracking.png` |
| `--container` / `--no-container` | `simulate`: bay trong container (mặc định) hay dùng `gz` trên máy |
| `--image NAME` | `simulate`: image Gazebo (mặc định `ghcr.io/openrobotics/gazebo:jetty-full`) |
| `--gpu auto\|nvidia\|intel\|software` | `simulate`: đường render cho GUI |
| `--keep-open` | `simulate`: không tự đóng cửa sổ khi route xong |
| `--pull` | `simulate`: `docker pull` image trước khi chạy |

`--force-missions` không đi cùng `--no-all-meshes` (báo lỗi), vì chọn lại một
mesh nên gọi trực tiếp `set_start_goal.py --force`.

## Chạy lại từ đầu

Chạy đủ ba stage mà không ghi stage nào, `main.py` hỏi trước khi làm gì:

```text
Trả lời y sẽ xoá và sinh lại:
    generated/  82 file · 36.7 MB
    data/processed/meshes/  11 file · 18.4 MB
    data/processed/scenes/  10 file · 6.1 MB
    Giữ lại: data/processed/missions/ (START/GOAL), data/raw/, data/expected/
    Container Gazebo còn sót: funnel-city_standardized_triangulation_g1-12345
Chạy lại từ đầu? (y/N): 
```

- **Enter = Không**: giữ kết quả cũ và chạy tiếp. Gõ `y` mới xoá.
- `--fresh` bỏ qua câu hỏi và xoá luôn; `--fresh` không đi cùng một stage nào
  (báo lỗi), vì xoá `generated/` rồi chạy riêng `simulate` sẽ mất route của
  g2/g3 và lặng lẽ bay lại chỉ g1.
- stdin không phải terminal (pipe, cron, CI) thì không hỏi: in
  `Không có terminal để hỏi; giữ kết quả cũ (dùng --fresh để xoá).`
- Xoá xong in `Đã xoá <n> file · <MB>` và lệnh khôi phục
  `git checkout -- generated data`.
- `data/processed/missions/` **không bị xoá**: mission ghi lựa chọn START/GOAL,
  không sinh lại được. Muốn chọn lại thì `--force-missions`.
- Container Gazebo còn sót tên `funnel-*` (do lần chạy trước bị kill) bị
  `docker rm -f` cùng lúc.

## Tham số hỏi khi chạy

Bước nào có tham số thì `main.py` hỏi ngay trước khi chạy bước đó. Enter giữ
giá trị trong ngoặc vuông (đúng cấu hình đang commit); gõ số khác thì dùng số
đó. Câu trả lời chỉ hỏi **một lần** cho cả run, nên `simulate` bay g1, g2, g3
bằng cùng bộ tham số.

| Bước | Tham số | Mặc định | Nghĩa và khoảng nên dùng | Cờ |
| --- | --- | --- | --- | --- |
| `triangulation` | `cell` (m) | 5 | Cạnh ô lưới; 3–10, dưới 5 thì plan rất chậm | `--cell` |
| | `clearance` (m) | 1,5 | Khe hở dọc trên nóc công trình; 0,5–3 | `--clearance` |
| | `half-width` (m) | 1,6 | Nới ngang khi truy vấn; 0,2–1,6, nhỏ = bám footprint | `--half-width` |
| | `max-slope` (m/m) | 0,5 | Độ dốc ramp; 0,5–2, lớn = lên/xuống dốc hơn | `--max-slope` |
| `run_funnel` | thời gian tối đa mỗi goal (s) | 300 | Chặn tìm kiếm; 60–900, city g2 cần khoảng 190 | `--seconds` |
| | số node tối đa | 200 000 | Giới hạn bộ nhớ; 50 000–1 000 000 | `--max-nodes` |
| | `clipping` | Y | Procedure 2; Y cho route ngắn hơn, N để so sánh | `--no-clipping` khi N |
| `build_world` | `simplify` (m) | 0,1 | Dung sai rút gọn waypoint; 0–1, 0 giữ mọi điểm | `--simplify` |
| | `collision grid` (m) | 1,0 | Ô gom đỉnh cho collision; 0,5–2, lớn = nhẹ hơn | `--collision-grid` |
| | tốc độ (m/s) | 5 | Tốc độ cruise; 2–8, cao quá dễ vượt sai số cho phép | `--speed` |
| | gia tốc tối đa (m/s²) | 3 | Gia tốc của profile; 1–6 | `--max-accel` |
| | dừng tại waypoint (s) | 0 | Dừng ở mỗi waypoint; 0–2, 0 là bay xuyên qua | `--dwell` |
| | trễ khởi động (s) | 2 | Chờ trước khi bay; 0–5 | `--start-delay` |
| `run_simulate.sh` | `timeout` (s) | 900 | Chặn Gazebo treo; 300–1800, route city bay 40–70 s | `--timeout` |
| `validate` | sai số cho phép (m) | 1,0 | Ngưỡng bám quỹ đạo; 0,2–2, 1 m là ngưỡng đã dùng | `--max-error` |

Dòng hỏi in kèm nghĩa và khoảng nên dùng, nên không phải mở tài liệu mới biết
đang đổi cái gì:

```text
      cell (m) — cạnh ô lưới, nên 3–10; dưới 5 thì plan rất chậm [5]: 
      half-width (m) — nới ngang khi truy vấn, nên 0,2–1,6; nhỏ = bám footprint [1.6]: 
```

Giá trị ngoài khoảng nên dùng **vẫn được chấp nhận** (đó là khuyến nghị, không
phải giới hạn cứng) nhưng in thêm một dòng cảnh báo:

```text
      (!) cell=1 ngoài khoảng nên dùng 3–10; vẫn dùng giá trị này.
```

Chỉ giá trị vô lý mới bị hỏi lại: số âm, 0 với tham số phải dương, chữ không
phải số.

Nhập sai (chữ, số âm, 0) thì tool báo và hỏi lại. Sau khi hỏi in lại
`→ cell=5 clearance=1.5 ...`, thêm `(đã đổi)` nếu có giá trị khác mặc định,
kèm dòng `$ <lệnh đầy đủ>` để chép vào báo cáo.

Đổi tham số hình học (`cell`, `clearance`, `half-width`, `max-slope`) làm bề
mặt có SHA khác. Bước 6 của `data` chạy
`set_start_goal.py --all-meshes --refresh-changed`: mission cũ được snap lại
vào bề mặt mới theo đúng toạ độ START/GOAL đã lưu, nên `plan` không dừng với
lỗi *"mesh changed since the mission was saved"*.

## parameters.json

Cuối mỗi run (kể cả khi lỗi) `main.py` ghi `generated/parameters.json`:

```json
{
  "command": "main.py data",
  "stages": ["data"],
  "cleared": false,
  "interactive": true,
  "parameters": {"triangulation": {"cell": 5.0, "clearance": 1.5,
                                   "half_width": 1.6, "max_slope": 0.5}},
  "sources": {"triangulation": {"cell": "default", "clearance": "default",
                                "half_width": "default", "max_slope": "default"}},
  "commit": "e6db303",
  "seconds": 9.328
}
```

`parameters` là giá trị đã dùng; `sources` cho biết mỗi giá trị đến từ mặc
định, từ câu trả lời hay từ cờ dòng lệnh. File này không commit (mỗi run ghi
đè); muốn trích vào báo cáo thì lấy từ đây.

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
code = capture(command) if args.quiet else stream(command)
if code:
    raise SystemExit(f'Stage {name} failed at step {step_number}: '
                     f'{step_label(command)}')
```

`stream` đọc từng dòng để output hiện ngay (không đợi bước xong); `capture`
giữ output và chỉ in khi lỗi.

Không có cơ chế bỏ qua lỗi hay chạy tiếp — muốn bỏ một bước thì sửa `STAGES`
hoặc gọi tool trực tiếp.

## Ví dụ

```bash
python3 main.py                     # hỏi chạy lại từ đầu, hỏi tham số, rồi chạy
python3 main.py --fresh             # xoá kết quả cũ rồi chạy cả ba
python3 main.py --no-ask            # không hỏi, dùng mặc định
python3 main.py flow                # xem lệnh
python3 main.py data --dry-run      # xem câu hỏi + lệnh, không đổi gì
python3 main.py plan
python3 main.py simulate --goal g2 --headless
python3 main.py data --no-all-meshes
python3 main.py data --force-missions
```

## Mở rộng

Thêm stage = thêm một khóa vào `STAGES` và `DESCRIPTIONS`; mỗi phần tử là một
dict `{'run': [...], 'params': [...]}` — `run` là lệnh tuyệt đối (phần tử đầu là
interpreter), `params` là danh sách nhóm trong `PARAM_GROUPS`. Thêm một nhóm
tham số = thêm một khóa vào `PARAM_GROUPS` và `GROUP_TITLES`, không cần sửa
`run_stage`.
