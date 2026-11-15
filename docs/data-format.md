# Định dạng dữ liệu và kế hoạch chuyển đổi

Tài liệu này chốt hai định dạng dữ liệu của repo và ghi lại kế hoạch chuyển
đổi. Trạng thái: **migration `.geom` → `.off` đã áp dụng**; bước xử lý dữ liệu
đầu vào `scene.glb` vẫn chưa triển khai.

## 1. Quyết định

| Vai trò | Định dạng | Đuôi |
| --- | --- | --- |
| Scene đầu vào, xem hình học, dựng world | glTF binary | `.glb` |
| Mesh dẫn xuất cho thuật toán | OFF | `.off` |
| Đường đi tham chiếu | JSON | `.paths.json` |
| Lưới ô raster | NumPy archive | `.npz` |

Hai định dạng đầu là quyết định chính. Hai định dạng sau đã ổn định và không
nằm trong đợt chuyển đổi này: đường đi là dữ liệu ngữ nghĩa, lưới ô là mảng
số lớn.

## 2. Hiện trạng trước migration

- 18 tệp `.geom` được Git theo dõi: 5 fixture `data/input/`, 5 tham chiếu
  `data/expected/`, 8 mesh dẫn xuất trong `generated/`.
- `.geom` đang mang **hai schema khác nhau**: mesh (`V F E`, toạ độ đỉnh,
  `3 a b c`) và đường đi (`k [x y z] ...`).
- Có **bốn parser độc lập** cho schema mesh: `src/mesh.py`,
  `src/verification.py`, `tools/prepare_funnel_input.py`,
  `tools/build_funnel_topology.py`.
- Khoảng 70 tham chiếu `.geom` trong mã nguồn và 17 trong tài liệu.

## 3. Vì sao GLB cho scene

- Là định dạng duy nhất đồng thời: mở xem được (Blender, MeshLab, trình xem
  glTF), giữ được **44 object** và transform của scene graph, và mang metadata
  trong `extras` (tác giả, giấy phép CC BY 4.0, nguồn).
- `data/source/city.glb` **đã là GLB**; chọn GLB nghĩa là tài sản lớn nhất
  không phải chuyển đổi, không mất gì.
- `src/city.py` đã có reader GLB, nên bước xử lý đầu vào chỉ cần chuẩn hoá
  tên node và bổ sung `extras`, không phải viết lại bộ đọc.
- Gazebo Harmonic dùng Assimp nên thường đọc được glTF/GLB; cần kiểm tra một
  lần trước khi bỏ hẳn `city.stl`.

## 4. Vì sao OFF cho mesh dẫn xuất

- Funnel Tree cần **một mặt liên tục**, đỉnh dùng chung giữa các tam giác và
  toạ độ **double**. glTF quy định `POSITION` là float32 và cho phép tách
  đỉnh theo normal/UV — hai điều này đi ngược yêu cầu của thuật toán.
- OFF có đúng header `V F E` như định dạng hiện tại, thêm dòng `OFF` ở đầu.
  Parser chỉ cần thêm một kiểm tra.
- Là text nên **hash ổn định giữa các môi trường** và diff được trên Git.
  Không phụ thuộc phiên bản zlib hay thư viện nén.
- Ghi bằng `repr(float)` hoặc `%.17g` bảo toàn chính xác giá trị double, nên
  không mất độ chính xác so với `.geom`.

## 5. Vì sao không dùng một định dạng cho cả hai

Scene và mesh dẫn xuất có yêu cầu trái nhau:

| Yêu cầu | Scene | Mesh dẫn xuất |
| --- | --- | --- |
| Con người mở xem | Có | Không cần |
| Giữ object + transform | Có | Không |
| Toạ độ double | Không bắt buộc | Bắt buộc |
| Đỉnh dùng chung | Không bắt buộc | Bắt buộc |
| Hash ổn định | Ưu tiên thấp | Ưu tiên cao |

Ép chung sẽ phải hy sinh một trong hai. GLB làm mesh dẫn xuất bị float32 và
tách đỉnh; OFF làm scene mất object, transform và metadata.

## 6. Các lựa chọn đã loại

| Định dạng | Lý do loại |
| --- | --- |
| NPZ cho scene | Không mở xem trực tiếp được; phải viết viewer riêng |
| OBJ cho scene | Không có header, không giữ metadata; thành phố thành text ~22 MB |
| PLY cho scene | Không giữ object/transform; metadata chỉ ở comment |
| JSON cho mesh | File phình 2–3 lần, không phù hợp mesh 301.490 tam giác |
| STL cho thuật toán | Không có chỉ số đỉnh dùng chung, phải weld lại |

NPZ vẫn là lựa chọn đúng cho **lưới ô** vì đó là mảng số lớn, không cần đọc
bằng mắt, và là dữ liệu dẫn xuất.

## 7. Kiến trúc đích

```text
data/source/city.glb ─┐
data/input/*.off     ─┴→ [xử lý dữ liệu đầu vào] → scene.glb
                                                      │
                        ┌─────────────────────────────┤
                        ▼                             ▼
              xem hình học (viewer)          build_navigation_surface
                                                      │
                                                      ▼
                                            navigation_y2p00.off
                                                      │
                                                      ▼
                                            funnel_input_y2p00.off
                                                      │
                                                      ▼
                                                Funnel Tree
```

`scene.glb` là output của bước xử lý đầu vào và là input của bước tạo lưới.
Funnel Tree **không** đọc `scene.glb`; nó chỉ nhận mesh `.off` đã dựng.

## 8. Phạm vi thay đổi

### 8.1 Tệp dữ liệu

| Hiện tại | Sau chuyển đổi |
| --- | --- |
| `data/input/{cliff,demo_mesh,J17,L,star}.geom` | `.off` |
| `data/expected/{cliff,demo_mesh,J17,L,star}.geom` | `.paths.json` |
| `generated/funnel_input_y2p00.geom` | `.off` |
| `generated/funnel_physics/surface_delivery/surface.geom` | `.off` |
| `generated/city_three_goals/g{1,2,3}/surface.geom` | `.off` |
| `generated/surface_sensitivity/cell_{5,7.5,15}/surface.geom` | `.off` |
| `generated/navigation_y2p00.geom` (sinh lại) | `.off` |
| `generated/flight_surface.geom` (sinh lại) | `.off` |
| Output của `plan.py`: `<mesh>_s<N>.geom` | `<mesh>_s<N>.paths.json` |

### 8.2 Mã nguồn

- Gộp bốn parser mesh về một: `src/mesh.py::read_off`.
- Bỏ `read_mesh` trùng trong `src/verification.py`; `read_paths` đọc JSON.
- Đổi `write_geom` thành `write_off` trong `tools/build_navigation_surface.py`.
- Cập nhật writer ở `plan.py`, `prepare.py`, `prepare_urban.py`,
  `tools/plan_surface_delivery.py`, `tools/run_surface_sensitivity.py`.
- Cập nhật đường dẫn đọc/ghi ở khoảng 20 tệp còn lại, gồm `check.py`,
  `tests/`, `tools/*.py` và `tools/dev/*.py`.

### 8.3 Cấu hình

- `.gitattributes`: `*.geom -text` → `*.off -text`.
- `.gitignore`: bốn dòng whitelist `surface.geom` và
  `funnel_input_y2p00.geom` → `.off`.

### 8.4 Tài liệu

- `README.md`: mục định dạng dữ liệu, cây thư mục, các ví dụ lệnh.
- `data/README.md`: mô tả schema OFF và `.paths.json`.
- `src/README.md`: tên hàm `read_off`.
- `docs/experiments/*.md`: các chỗ nhắc `.geom`.
- `tools/dev/README.md` nếu có nhắc định dạng.

## 9. Ảnh hưởng chuỗi hash

Đổi định dạng không đổi hình học nhưng đổi byte, nên các giá trị sau phải
được tính lại:

| Giá trị | Nơi ghi |
| --- | --- |
| Chữ ký benchmark `T` | `generated/funnel_benchmark/*.json`, `funnel_reference/reference_comparison.json` |
| Chữ ký cache ba đích `S` | `generated/city_three_goals/g*/planning_stats.json`, `results.json` |
| `input_sha256` | `surface_plan.json`, `horizontal_plan.json` |
| `mesh_sha256` | `*_validation.json`, `*/reference/comparison.json`, `cases.json`, `results.json` |
| Hash mã nguồn | `generated/source_header_audit.json` cho các `.py` bị sửa |

Hai cách xử lý:

- **A (khuyến nghị khi đổi hình học):** chạy lại `run_funnel_benchmark.py`,
  `plan_surface_delivery.py`, `compare_surface_geodesic.py`,
  `run_city_three_goals.py --stage plan`, `run_surface_sensitivity.py` trong
  môi trường Ubuntu có NumPy/Shapely. Không cần chạy lại Gazebo vì STL và
  telemetry không đổi.
- **B:** propagate hash cơ học kèm script chứng minh từng đỉnh và từng mặt
  khớp tuyệt đối trước/sau chuyển đổi.

Đợt migration này dùng **cách B**: chuyển đổi chỉ thêm dòng `OFF` vào mesh và
đổi container của đường đi sang JSON, nên hình học giữ nguyên từng đỉnh và
từng mặt. Hash được propagate có kiểm chứng; không chạy lại Gazebo.

## 10. Thứ tự thực hiện

1. Viết `tools/dev/migrate_geom_to_off.py`: đọc legacy, ghi OFF, đọc lại và
   so khớp từng đỉnh, từng mặt; in báo cáo.
2. Chuyển 5 fixture và 5 tệp đường đi bằng script; đổi tên 8 mesh dẫn xuất.
3. Sửa parser, writer và toàn bộ đường dẫn.
4. Chạy `check.py` trong môi trường có NumPy.
5. Chạy lại pipeline hoặc propagate hash theo mục 9.
6. `tools/verify_project_results.py` phải in `Project results: READY`.
7. `grep -rn "\.geom"` phải rỗng, trừ script migration và ghi chú lịch sử.
8. Commit một lần, ghi rõ định dạng cũ/mới và cách bảo toàn hình học.

Tiêu chí hoàn thành:

- `git ls-files '*.geom'` rỗng.
- Chỉ còn một parser mesh (`src/mesh.py`) và một parser path
  (`src/verification.py`).
- `check.py` pass và `verify_project_results.py` báo `READY`.
- `data/README.md` mô tả đúng OFF và `.paths.json`.

## 11. Rủi ro

- **Sai số khi ghi**: mesh chỉ được thêm dòng `OFF` nên giữ nguyên văn bản gốc;
  đường đi được JSON hoá trực tiếp từ float đã đọc, không làm tròn lại.
- **`mesh_sha256` là định danh hình học**: đổi byte là đổi hash dù hình học y
  nguyên; phải cập nhật đồng bộ.
- **GLB float32**: fixture `demo_mesh` có toạ độ double (~300), chuyển sang
  GLB sẽ làm tròn còn khoảng 7 chữ số. Giữ `.off` làm nguồn gốc double và
  coi GLB là bản dẫn xuất để tránh thay đổi ngữ nghĩa của kiểm thử.
- **Gazebo và GLB**: cần kiểm tra một lần với `scene.glb` trước khi bỏ STL.
- **Không có NumPy trong môi trường hiện tại**: không thể chạy `check.py`
  hoặc regenerate; migration phải thực hiện trong môi trường Ubuntu của dự án.

## 12. Trạng thái

- Định hướng: đã chốt.
- Migration `.geom` → `.off` và `.paths.json`: đã áp dụng.
- Bước xử lý dữ liệu đầu vào (`scene.glb`): chưa triển khai; sẽ quyết định sau.
- Kiểm chứng sau migration: `check.py` pass và
  `tools/verify_project_results.py` báo `Project results: READY`.
