---
title: main.py
aliases:
  - main
  - pipeline
type: entry point
stage: all
source: main.py
tags:
  - funnel-tree/tool
  - funnel-tree/pipeline
---

# `main.py`

> [!abstract] Mục đích
> Điểm vào duy nhất của pipeline: chạy stage `data` → `plan` → `simulate`
> bằng subprocess, hỏi tham số một lần cho cả run, dọn đúng những thư mục sẽ sinh
> lại và lưu bản kết quả vào `results/runs/` khi cần so sánh.

> [!info] Vị trí
> **File** `main.py` — chạy từ gốc repo, không thuộc stage nào  
> **Thuật toán** Chạy từng bước bằng subprocess, dừng ở lỗi đầu tiên; hỏi tham số một lần cho cả run  
> **Vào** tên stage (`data`, `plan`, `simulate`, `flow`) + cờ  
> **Ra** chạy các tool và dừng ở lỗi đầu tiên; ghi `generated/parameters.json`; `--label`/`--archive` chép kết quả vào `results/runs/<label>/`  
> **Stages** `data` (7 bước) → `plan` (3) → `simulate` (3 × số goal)  

## API chính

| Hàm / lớp | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `Param` | tên, nhãn, mặc định, kiểu, cờ, khoảng khuyến nghị | — | Mô tả một giá trị sẽ hỏi và cờ tương ứng |
| `display(command)`, `short(path)` | lệnh / đường dẫn | chuỗi gọn | Đổi interpreter thành tên ngắn khi in, cắt đường dẫn về tương đối repo |
| `step_label(command)` | lệnh đầy đủ | nhãn bước | Bỏ interpreter và tiền tố repo để tiêu đề bước ngắn |
| `mission_goals(mission)` | tên mission | danh sách goal | Đọc `generated/routes/<mission>.routes.json`; thiếu file thì trả `[DEFAULT_GOAL]` |
| `simulate_folders(args)` | mission + goal | thư mục run | Xác định đúng thư mục `simulate` sẽ ghi đè |
| `copy_step(step)` | một bước trong `STAGES` | bản sao `{run, params, note}` | Sao chép để stage `simulate` sửa lệnh mà không đụng bảng gốc |
| `stage_commands(name, args)` | tên stage + cờ | danh sách lệnh | Dựng lệnh từng bước, nhân bản theo goal và áp cờ cho `simulate` |
| `show_flow(args)` | cờ | in | In stage, từng bước và nhóm tham số sẽ hỏi (`main.py flow`) |
| `run_stage(name, args, index, total, state)` | stage, cờ, vị trí | mã thoát | Chạy tuần tự, dừng ngay ở bước lỗi |
| `stream(command)`, `capture(command)` | lệnh | mã thoát | In output theo dòng, hoặc giữ lại chỉ in khi lỗi (`--quiet`) |
| `default_value(item, group, args)`, `format_default(item, value)`, `format_group(group, values)` | tham số + giá trị | giá trị / chuỗi | Lấy mặc định (`--max-error` ghi đè), định dạng `Y/N` và số, ghép `key=value` |
| `prompt_text(item, default)`, `warn_outside(item, value)` | tham số | câu hỏi / cảnh báo | In câu hỏi kèm mặc định; cảnh báo ngoài khoảng khuyến nghị nhưng vẫn dùng |
| `ask_value(item, default)` | một tham số | giá trị | Enter giữ mặc định; sai kiểu, không hữu hạn hoặc ngoài biên thì hỏi lại; `EOFError` trả mặc định |
| `choose_group(group, args, state)` | nhóm tham số | `dict` giá trị | Hỏi một lần cho cả run, ghi lại nguồn `default`/`answer`/`flag` |
| `group_flags(group, values)` | nhóm + giá trị | danh sách cờ | Dựng `--flag value`, bỏ giá trị rỗng, dùng `false_flag` cho bool sai |
| `cleared_folders(stages, args)` | stage + cờ | danh sách thư mục | Chỉ chọn những gì các stage được chọn sinh lại |
| `folder_stats(folder)`, `stale_containers()` | thư mục / `docker ps` | `(số file, byte)`, danh sách tên | Đo dung lượng sắp xoá, tìm container `funnel-*` còn sót |
| `print_manifest(folders, stages)` | thư mục + stage | `(file, byte, container)` | In bảng sẽ xoá gì, giữ gì, trước khi hỏi |
| `clear_artifacts(args, folders, stages)`, `ask_fresh(args, folders, stages)` | stage + cờ | danh sách đã xoá | `--fresh` xoá ngay; không có terminal thì giữ; `--dry-run` chỉ in lệnh |
| `sha256(path)`, `timestamp()`, `commit()` | đường dẫn / — | hash, ISO time, commit ngắn | Ghi manifest; commit `None` khi không phải repo Git |
| `archive_target(label)` | label | `Path` | Kiểm label chỉ gồm chữ, số, `.`, `_`, `-`; từ chối label lạ |
| `archive_files(mission, goals)`, `archive_details(mission, goals)`, `archive_run(...)` | mission, goal | thư mục archive | Chép số liệu + ảnh vào `results/runs/<label>/`, ghi `manifest.json` |
| `retarget_sidecars(target)` | thư mục archive | sửa sidecar | Trỏ `image` của sidecar sang bản sao, giữ nguyên SHA |
| `report_quality(args, since=0.0)` | `--max-error`, mốc thời gian | in bảng | In `max`/`mean error` từng goal kể cả khi `--quiet` |
| `write_parameters(args, stages, state, cleared, started)` | toàn bộ run | `generated/parameters.json` | Ghi giá trị đã dùng, nguồn của từng giá trị, commit, thời gian |
| `main()` | `sys.argv` | mã thoát | Parse cờ, chọn stage, hỏi tham số, chạy, lưu archive nếu có |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | `argparse` và stdlib khác; `.venv/bin/python` nếu có | CLI và chọn interpreter cho mọi bước |
| Nội bộ | `tools/data/*.py`, `tools/plan/*.py`, `tools/simulate/*` | Các bước của ba stage |
| Nội bộ | `tools/plan/compare_runs.py` | Đọc archive do `--label` tạo |
| Dữ liệu | `data/processed/missions/*.mission.json` | `simulate` lấy danh sách goal mặc định |
| Dữ liệu | `results/runs/<label>/` | Nơi không stage nào xoá |

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
| `data` | 7 | copy fixtures → standardize → glb2off → off2glb → triangulation → data_viz → set_start_goal |
| `plan` | 3 | run_funnel → route_viz → compare |
| `simulate` | 3 × số goal | build_world → run_simulate `--no-build` → validate, lặp cho từng goal (mặc định cả g1, g2, g3) |

Không ghi stage nào thì chạy **cả ba theo thứ tự data → plan → simulate**. Muốn
một stage thì ghi tên: `python3 main.py plan`.

Thứ tự trong `data` có chủ đích:

1. `copy_meshes` chạy trước để fixture có mặt trong `data/processed/`.
2. `standardize` tạo scene chuẩn hoá mà `triangulation` đọc.
3. `glb2off` xuất cả thành phố ra `.off` để xem và để chụp hình cho báo cáo
   (bước này in nhãn *bản xem thành phố cho báo cáo, không phải đầu vào thuật
   toán*; `triangulation` không đọc file này).
4. `off2glb` độc lập với 1–3, chỉ tạo bản xem ngược lại.
5. `triangulation` ghi đè bề mặt (luôn kèm `--force`).
6. `data_viz` render mọi `.off` trong `data/processed/meshes/` **sau** khi bề
   mặt và bản xem thành phố đã có, nên nó cũng vẽ `city.standardized.glb2off.png`.
7. `set_start_goal` chạy cuối để nếu nó cần hỏi thì các bước trước đã xong;
   `--all-meshes` bỏ qua `*.glb2off.off`.

## Kết thúc stage `simulate`

`validate` chỉ thoát mã 1 khi lần bay **không hợp lệ** (telemetry không kết thúc
ở `complete`, hoặc dừng cách đích quá 0,5 m). Trượt **mốc chất lượng** 1 m chỉ
in cảnh báo, nên `main.py simulate` chạy tiếp goal sau thay vì dừng giữa bộ ba.

Cuối stage, `main.py` luôn in một dòng cho mỗi goal đã bay, kể cả khi dùng
`--quiet` (vì `--quiet` chỉ giữ output của bước lỗi):

```text
Mốc bám tuyến (chất lượng, không phải điều kiện hợp lệ):
    g1: max 0.365 m / mốc 1 m · mean 0.068 m — đạt mốc
    g2: max 1.022 m / mốc 1 m · mean 0.110 m — trượt mốc
    g3: max 0.851 m / mốc 1 m · mean 0.091 m — đạt mốc
```

## Cờ

| Cờ | Tác dụng |
| --- | --- |
| `flow` | In các lệnh rồi thoát |
| `--dry-run` | In lệnh và câu hỏi tham số, không chạy, không hỏi, không xoá |
| `--fresh` | Xoá đúng những thư mục mà các stage được chọn sẽ sinh lại, không hỏi |
| `--label NAME` | Chạy xong thì chép số liệu + ảnh vào `results/runs/NAME/` để so sánh giữa các lần chạy |
| `--archive NAME` | Không chạy gì, chỉ chép kết quả đang có vào `results/runs/NAME/` |
| `--no-ask` | Không hỏi gì: giữ toàn bộ tham số mặc định |
| `--quiet` | Ẩn output của tool, chỉ in bước + thời gian; output hiện ra khi bước lỗi |
| `--all-meshes` / `--no-all-meshes` | Bước 7 chọn cho mọi mesh (mặc định) hay chỉ bề mặt |
| `--force-missions` | Chỉ với `--all-meshes`: chọn lại cả mesh đã có mission |
| `--mission STEM` | `simulate`: route stem (mặc định `city.standardized.triangulation`) |
| `--goal ID` | `simulate`: chỉ bay một goal; mặc định bay mọi goal của route |
| `--headless` | `simulate`: `gz sim -s -r`, không GUI |
| `--software` | `simulate`: ép software rendering |
| `--show-surface` | `simulate`: `build_world --surface` |
| `--max-error M` | `simulate`: mốc chất lượng cho `validate` (1,0 m); trượt mốc **không** làm lần bay không hợp lệ |
| `--no-png` | `simulate`: bỏ `tracking.png` |
| `--container` / `--no-container` | `simulate`: bay trong container (mặc định) hay dùng `gz` trên máy |
| `--image NAME` | `simulate`: image Gazebo (mặc định `ghcr.io/openrobotics/gazebo:jetty-full`) |
| `--gpu auto\|nvidia\|intel\|software` | `simulate`: đường render cho GUI |
| `--keep-open` | `simulate`: không tự đóng cửa sổ khi route xong |
| `--pull` | `simulate`: `docker pull` image trước khi chạy |

`--force-missions` không đi cùng `--no-all-meshes` (báo lỗi), vì chọn lại một
mesh nên gọi trực tiếp `set_start_goal.py --force`.

## Xoá và sinh lại theo stage

`main.py` hỏi trước khi chạy, và chỉ liệt kê những thư mục mà **các stage được
chọn** sẽ ghi lại:

```text
Trả lời y sẽ xoá và sinh lại (data, plan):
    data/processed/meshes/  13 file · 18.4 MB
    data/processed/scenes/  10 file · 6.1 MB
    generated/data_viz/  22 file · 2.7 MB
    generated/routes/  30 file · 3.4 MB
    generated/compare/  6 file · 0.0 MB
    Giữ lại: data/processed/missions/ (START/GOAL), data/raw/, data/expected/, results/runs/ (archive)
Chạy lại từ đầu? (y/N): 
```

| Stage được chọn | Xoá | Giữ nguyên |
| --- | --- | --- |
| `data` | `data/processed/meshes/`, `data/processed/scenes/`, `generated/data_viz/` | route, compare, simulate, archive |
| `plan` | `generated/routes/`, `generated/compare/` | ảnh data_viz, simulate, archive |
| `simulate` | `generated/simulate/<mission>-<goal>/` của **đúng các goal sắp bay** | goal khác, route, plan, archive |

- **Enter = Không**: giữ kết quả cũ và chạy tiếp. Gõ `y` mới xoá.
- `--fresh` bỏ qua câu hỏi và xoá luôn, dùng được với một stage: chạy
  `python3 main.py plan --fresh` chỉ dọn route/compare, không mất ảnh bề mặt
  hay lần bay trước.
- stdin không phải terminal (pipe, cron, CI) thì không hỏi: in
  `Không có terminal để hỏi; giữ kết quả cũ (dùng --fresh để xoá).`
- Xoá xong in `Đã xoá <n> file · <MB>` và lệnh khôi phục
  `git checkout -- generated data`.
- `data/processed/missions/` **không bị xoá**: mission ghi lựa chọn START/GOAL,
  không sinh lại được. Muốn chọn lại thì `--force-missions`.
- `results/runs/` **không bị xoá** ở bất kỳ stage nào: đó là nơi giữ số liệu của
  những lần chạy đã lưu.
- Container Gazebo còn sót tên `funnel-*` bị `docker rm -f` khi stage
  `simulate` được chọn.

## Lưu một lần chạy để so sánh

Đổi `cell` từ 5 m sang 4 m làm bề mặt, route và kết quả bay đều khác, nhưng mọi
tool ghi vào cùng tên file. Muốn so sánh hai cấu hình sau khi đã chạy xong thì
lưu từng lần chạy lại:

```bash
python3 main.py --label grid5          # chạy theo cấu hình hiện tại rồi lưu
python3 main.py --label grid4          # lần chạy thứ hai, không cần --fresh
python3 tools/plan/compare_runs.py     # bảng grid5 vs grid4 cho báo cáo
```

`--archive` dùng khi kết quả đã có sẵn trên đĩa và không muốn chạy lại:

```bash
python3 main.py --archive grid5-b
```

Mỗi archive là một thư mục trong `results/runs/<label>/`:

| File | Nội dung |
| --- | --- |
| `manifest.json` | tham số + nguồn, `commit` (HEAD lúc lưu), SHA scene/bề mặt/route, START/GOAL đã snap, độ dài route từng goal, thời lượng bay, `max_error`, `mean_error`, `valid`, `passed`, danh sách file kèm SHA |
| `parameters.json` | bản sao `generated/parameters.json` của lần chạy `main.py` **cuối cùng** (với `--archive` có thể chỉ là một goal) |
| `surface.params.json` | tham số + SHA của bề mặt đã dùng |
| `mission.json`, `routes.json`, `routes.png`, `routes.png.json` | mission, route đã lập và ảnh tuyến |
| `plan-summary.json` | `generated/compare/summary.json` (đối chiếu reference) |
| `g1/`, `g2/`, `g3/` | `validation.json`, `world_metadata.json`, `flown_route.json` (tuyến đã rút gọn), `tracking.png` + sidecar, `telemetry_metadata.json` |

- Label chỉ gồm chữ, số, dấu chấm, gạch dưới, gạch ngang; label đã có thì tool
  **dừng**, không ghi đè archive cũ.
- Archive chụp toàn bộ kết quả đang có, kèm `stages` của lần chạy và danh sách
  `missing`; muốn bảng đầy đủ thì chạy cả ba stage rồi mới lưu.
- File nào thiếu thì manifest ghi vào `missing` và in ra, archive vẫn được tạo.
- `parameters` trong manifest là những nhóm mà lần chạy đó thực sự hỏi (ví dụ
  chỉ chạy `simulate` thì có `world`, `flight`, `gazebo`, `validate`); tham số
  hình học và solver vẫn truy được qua `surface.params.json` và `routes.solver`,
  và `compare_runs.py` tự gộp lại.
- `commit` là `HEAD` **lúc lưu archive**, không phải lúc bay. Với `--label` hai
  thời điểm trùng nhau; với `--archive` thì không, và `parameters.json` chỉ là
  log của lần `main.py` cuối cùng. Số liệu vẫn truy được qua `route_sha256` và
  `telemetry_sha256` trong `validation.json`.

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
| `run_funnel` | thời gian tối đa mỗi goal (s) | 300 | Chặn tìm kiếm; 30–900, city g2 cần khoảng 20 | `--seconds` |
| | số node tối đa | 200 000 | Giới hạn bộ nhớ; 50 000–1 000 000 | `--max-nodes` |
| | `clipping` | Y | Procedure 2; Y cho route ngắn hơn, N để so sánh | `--no-clipping` khi N |
| `build_world` | `simplify` (m) | 0,1 | Dung sai rút gọn waypoint; 0–1, 0 giữ mọi điểm | `--simplify` |
| | `collision grid` (m) | 1,0 | Ô gom đỉnh cho collision; 0,5–2, lớn = nhẹ hơn | `--collision-grid` |
| | tốc độ (m/s) | 5 | Tốc độ cruise; 2–8, cao quá dễ vượt sai số cho phép | `--speed` |
| | gia tốc tối đa (m/s²) | 3 | Gia tốc của profile; 1–6 | `--max-accel` |
| | dừng tại waypoint (s) | 0 | Dừng ở mỗi waypoint; 0–2, 0 là bay xuyên qua | `--dwell` |
| | trễ khởi động (s) | 2 | Chờ trước khi bay; 0–5 | `--start-delay` |
| `run_simulate.sh` | `timeout` (s) | 900 | Chặn Gazebo treo; 300–1800, route city bay 40–70 s | `--timeout` |
| `validate` | mốc chất lượng bám tuyến (m) | 1,0 | Số đo để báo cáo, không phải điều kiện hợp lệ; 0,2–2, 1 m = 20 % ô lưới và 2/3 clearance | `--max-error` |

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

Sau khi hỏi, `main.py` in lại `→ cell=5 clearance=1.5 ...`, thêm `(đã đổi)`
nếu có giá trị khác mặc định, kèm dòng `$ <lệnh đầy đủ>` để chép vào báo cáo.

Đổi tham số hình học (`cell`, `clearance`, `half-width`, `max-slope`) làm bề
mặt có SHA khác. Bước 7 của `data` chạy
`set_start_goal.py --all-meshes --refresh-changed`: mission cũ được snap lại
vào bề mặt mới theo đúng toạ độ START/GOAL đã lưu, nên `plan` không dừng với
lỗi *"mesh changed since the mission was saved"*.

Bước nào hỏi trên terminal (`set_start_goal.py`) in mỗi câu hỏi thành **một dòng
riêng**, nên đọc được trong output của `main.py`. Trước đây prompt không có `\n`
nên bị pipe giữ lại: câu hỏi không hiện ra và tool trông như bị treo.

## parameters.json

Cuối mỗi run (kể cả khi lỗi) `main.py` ghi `generated/parameters.json`:

```json
{
  "command": "main.py data",
  "stages": ["data"],
  "label": null,
  "cleared": ["data/processed/meshes", "data/processed/scenes",
              "generated/data_viz"],
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
định, từ câu trả lời hay từ cờ dòng lệnh; `cleared` là những thư mục đã xoá ở
đầu run (rỗng nếu giữ kết quả cũ). File này không commit (mỗi run ghi đè); muốn
trích vào báo cáo thì lấy từ đây, hoặc lấy bản đã lưu trong archive.

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
    Save at: generated/routes/J17.routes.json
    ...
    done in 63.0 s

plan: ok in 63.7 s
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
python3 main.py                     # hỏi xoá gì, hỏi tham số, rồi chạy
python3 main.py --fresh             # xoá những gì các stage sẽ sinh lại
python3 main.py --no-ask            # không hỏi, dùng mặc định
python3 main.py flow                # xem lệnh
python3 main.py data --dry-run      # xem câu hỏi + lệnh, không đổi gì
python3 main.py plan
python3 main.py simulate --goal g2 --headless
python3 main.py data --no-all-meshes
python3 main.py data --force-missions
python3 main.py --label grid4       # chạy rồi lưu kết quả vào results/runs/grid4
python3 main.py --archive grid4-b   # chỉ lưu kết quả đang có
```

## Mở rộng

Thêm stage = thêm một khóa vào `STAGES`, `DESCRIPTIONS` và (nếu có thư mục
riêng cần xoá) `CLEARED`; mỗi phần tử là một dict
`{'run': [...], 'params': [...], 'note': '...'}` — `run` là lệnh tuyệt đối
(phần tử đầu là interpreter), `params` là danh sách nhóm trong `PARAM_GROUPS`,
`note` là nhãn in cạnh tên bước. Thêm một nhóm tham số = thêm một khóa vào
`PARAM_GROUPS` và `GROUP_TITLES`, không cần sửa `run_stage`.

## Liên quan

- [`../data-format.md`](../data-format.md) — định dạng file giữa các stage.
- [`reproducibility.md`](reproducibility.md) — archive và môi trường đo.
- [`docker.md`](docker.md) — chạy `main.py` trong image.
- [`README.md`](README.md) — mục lục toàn bộ tool.
