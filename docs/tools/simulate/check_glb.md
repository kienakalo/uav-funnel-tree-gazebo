---
title: check_glb.py
aliases:
  - check_glb
type: tool
stage: simulate
source: tools/simulate/check_glb.py
tags:
  - funnel-tree/tool
  - funnel-tree/stage/simulate
---

# `tools/simulate/check_glb.py`

> [!abstract] Mục đích
> Gọi đúng **Assimp 5.3** mà Gazebo dùng để nạp visual, và báo lỗi import
> trước khi bay. Một GLB trình duyệt mở được vẫn có thể bị Assimp từ chối.

> [!info] Vị trí
> **File** `tools/simulate/check_glb.py` — stage `simulate`, kiểm trước khi bay  
> **Thuật toán** `ctypes` gọi `aiImportFile` của `libassimp.so.5`, đọc `mNumMeshes` ở offset 16  
> **Vào** một hoặc nhiều file `.glb`  
> **Ra** dòng `ok`/`fail` cho từng file; mã thoát 1 nếu có file lỗi  
> **Cờ** danh sách đường dẫn; không có cờ khác  
> **Cần** `libassimp.so.5` (có sẵn trong image Gazebo)  

## API chính

| Hàm | Vào | Ra | Việc |
| --- | --- | --- | --- |
| `load_assimp(library='libassimp.so.5')` | tên thư viện | `ctypes.CDLL` | Nạp Assimp và khai báo `aiImportFile`, `aiGetErrorString` |
| `check(lib, path)` | thư viện + file GLB | `(mesh_count, error)` | Import file; `error` rỗng khi thành công, đọc `mNumMeshes` ở offset 16 |
| `main()` | danh sách đường dẫn | in kết quả, mã thoát | Duyệt file, dừng với mã 1 nếu có lỗi |

## Phụ thuộc

| Loại | Tên | Dùng để |
| --- | --- | --- |
| Thư viện | `ctypes`, `sys`, `pathlib` | Gọi C API của Assimp, không cần binding Python |
| Hệ thống | `libassimp.so.5` | Bộ nạp mesh mà `gz-rendering` dùng |
| Được gọi bởi | `run_simulate.sh --check` | Chặn bay khi visual không nạp được |

## Vì sao cần

Gazebo đọc visual qua `gz-rendering` → `AssimpLoader` → **Assimp 5.3**. Một GLB
mà trình duyệt vẫn mở được vẫn có thể bị Assimp từ chối; khi đó Gazebo tạo
entity `city` nhưng **không có hình học**, cửa sổ chỉ còn lưới nền:

```
[error] [AssimpLoader.cc:890] [GUI] Unable to import mesh [.../city.sim.glb]
[error] [Ogre2MeshFactory.cc:597] [GUI] Cannot load mesh with zero sub-meshes
```

Lỗi thực tế đã gặp: `byteLength` của bufferView chỉ số lấy từ mảng `int64`
(gấp đôi), Assimp báo `GLTF: Buffer view ... is out of range`.

## Cách làm

`ctypes` gọi `libassimp.so.5`:

```python
scene = lib.aiImportFile(path, 0)          # None nếu lỗi
count = ctypes.c_uint.from_address(scene + 16).value   # mNumMeshes
error = lib.aiGetErrorString()
```

`aiScene` xếp `mFlags`, con trỏ `mRootNode`, rồi mới tới `mNumMeshes`, nên đọc
số mesh ở offset **16**, không phải 4.

## Chạy

Chỉ chạy được ở nơi có `libassimp5` — trong image Gazebo là đủ:

```bash
docker run --rm -v "$PWD:/work" -w /work \
  ghcr.io/openrobotics/gazebo:jetty-full \
  python3 tools/simulate/check_glb.py \
  generated/simulate/*/city.sim.glb \
  data/processed/scenes/city.standardized.glb
```

`run_simulate.sh --check` tự gọi cho `city.sim.glb` của world sắp bay; nếu lỗi,
script dừng trước khi mở Gazebo.

## Kết quả đã kiểm

| File | Kết quả |
| --- | --- |
| `generated/simulate/*/city.sim.glb` (3 world) | `ok: 1 mesh`, 8.531.220 byte |
| `data/processed/scenes/city.standardized.glb` | `ok: 53 mesh`, 6.104.668 byte |
| 8 fixture `*.off2glb.glb` | `ok: 1 mesh` mỗi file |

## Giới hạn

- Phụ thuộc `libassimp.so.5`; máy không có Assimp thì báo lỗi nạp thư viện.
- Chỉ kiểm **import**, không kiểm material, texture hay kích thước hiển thị.
- Không thay thế `gz sdf -k`: SDF vẫn phải hợp lệ và URI phải trỏ đúng file.

## Liên quan

- [`build_world.md`](build_world.md) — sinh `city.sim.glb` mà bước này kiểm.
- [`run_simulate.md`](run_simulate.md) — `--check` gọi tool này tự động.
- [`../lib.md`](../lib.md) — `write_glb`, nơi từng gây lỗi `byteLength`.
