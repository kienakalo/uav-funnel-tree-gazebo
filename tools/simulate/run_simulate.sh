#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main runtime: Bash; Gazebo Jetty (host or container); system Python with gz
# bindings; local tools/simulate/build_world.py and tools/simulate/plugin.
# Fly one planned route in Gazebo and leave the telemetry on disk.
#
# Usage:
#   bash tools/simulate/run_simulate.sh [--mission STEM] [--goal ID] [--headless]
#                                       [--software] [--show-surface] [--timeout S]
#                                       [--container|--native] [--image NAME]
#                                       [--gpu auto|nvidia|intel|software]
#                                       [--screenshot|--no-screenshot] [--keep-open]
#   bash tools/simulate/run_simulate.sh --check | --no-build
#
# The Gazebo container is the default so the same tree runs on any machine;
# --native uses a Gazebo installed on the host. --check verifies the runtime,
# the plugin import, the world files and the SDF without opening Gazebo.
# Goals are fail-closed, so a route with several goals needs --goal.
usage() {
  cat <<'EOF'
Fly one planned route in Gazebo and leave the telemetry on disk.

Usage:
  bash tools/simulate/run_simulate.sh [--mission STEM] [--goal ID] [--headless]
                                      [--software] [--show-surface] [--timeout S]
                                      [--container|--native] [--image NAME]
                                      [--gpu auto|nvidia|intel|software]
                                      [--screenshot|--no-screenshot] [--keep-open]
  bash tools/simulate/run_simulate.sh --check | --no-build

--check verifies Docker (or a native gz), the gz-sim 10 bindings, the plugin
import, the world files, the SDF and the visual mesh without opening Gazebo.
The default is the container ghcr.io/openrobotics/gazebo:jetty-full; --native
runs the gz found on PATH. The GUI needs a display; --headless does not.
EOF
}
set -euo pipefail
cd "$(dirname "$0")/../.."

mission=city.standardized.triangulation
goal=g1
headless=false
software=false
show_surface=false
check_only=false
no_build=false
timeout_s=900
container=true
image='ghcr.io/openrobotics/gazebo:jetty-full'
gpu=auto
screenshots=auto
keep_open=false
pull=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mission) mission="$2"; shift 2 ;;
    --goal) goal="$2"; shift 2 ;;
    --headless) headless=true; shift ;;
    --software) software=true; shift ;;
    --show-surface) show_surface=true; shift ;;
    --check) check_only=true; shift ;;
    --no-build) no_build=true; shift ;;
    --timeout) timeout_s="$2"; shift 2 ;;
    --container) container=true; shift ;;
    --native) container=false; shift ;;
    --image) image="$2"; shift 2 ;;
    --gpu) gpu="$2"; shift 2 ;;
    --screenshot) screenshots=true; shift ;;
    --no-screenshot) screenshots=false; shift ;;
    --keep-open) keep_open=true; shift ;;
    --pull) pull=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "run_simulate: unknown argument $1" >&2; exit 2 ;;
  esac
done

folder="generated/simulate/${mission}-${goal}"
world="funnel_sim_$(printf '%s_%s' "$mission" "$goal" | sed 's/[^A-Za-z0-9]/_/g')"
sdf="$PWD/$folder/funnel_physics.sdf"
route="$PWD/$folder/route.json"
output="$PWD/$folder"
log="$folder/gazebo.log"
csv="$folder/physics_telemetry.csv"
planner=python3
[[ -x .venv/bin/python ]] && planner=.venv/bin/python
container_name="funnel-$(printf '%s_%s' "$mission" "$goal" | sed 's/[^A-Za-z0-9]/_/g')-$$"
gui_home=''
gazebo_pid=''
screenshot_pid=''

fail() { echo "run_simulate: $*" >&2; exit 1; }

cleanup() {
  [[ -n "$screenshot_pid" ]] && kill "$screenshot_pid" 2>/dev/null || true
  if [[ "$container" == true ]]; then
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
  if [[ -n "$gazebo_pid" ]] && kill -0 "$gazebo_pid" 2>/dev/null; then
    kill "$gazebo_pid" 2>/dev/null || true
  fi
  if [[ -n "$gui_home" ]]; then rm -rf "$gui_home"; fi
  return 0
}
trap cleanup EXIT

resolve_gpu() {
  if [[ "$software" == true ]]; then gpu=software; fi
  if [[ "$gpu" == auto ]]; then
    if [[ "$container" == true && -f /var/run/cdi/nvidia-container-toolkit.json ]] \
        && command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
      gpu=nvidia
    elif [[ -e /dev/dri ]]; then
      gpu=intel
    else
      gpu=software
    fi
  fi
  case "$gpu" in
    nvidia|intel|software) ;;
    *) fail "--gpu must be auto, nvidia, intel or software" ;;
  esac
}

gpu_label() {
  case "$gpu" in
    nvidia)
      local name
      name="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
      echo "nvidia${name:+: $name}" ;;
    intel) echo 'intel: /dev/dri (Mesa)' ;;
    *) echo 'software: llvmpipe' ;;
  esac
}

check_environment() {
  if [[ "$container" == true ]]; then
    command -v docker >/dev/null 2>&1 || fail 'docker not found; install Docker or use --native'
    docker info >/dev/null 2>&1 || fail 'the Docker daemon is not reachable'
    if ! docker image inspect "$image" >/dev/null 2>&1; then
      fail "image $image is missing; run with --pull or: docker pull $image"
    fi
    docker run --rm "$image" gz sim --versions >/dev/null 2>&1 \
      || fail "image $image has no working gz sim"
    docker run --rm "$image" python3 -c '
try:
    from gz.sim import Model, Link
    from gz.math import Vector3d
except ModuleNotFoundError:
    from gz.sim10 import Model, Link
    from gz.math9 import Vector3d
' || fail "image $image has no gz-sim 10 Python bindings"
    docker run --rm -v "$PWD:/work" -w /work \
      -e PYTHONPATH=/work/tools/simulate/plugin "$image" \
      python3 -c 'import funnel_drone_system' >/dev/null 2>&1 \
      || fail 'cannot import funnel_drone_system from tools/simulate/plugin'
  else
    command -v gz >/dev/null 2>&1 || fail 'gz not found; install Gazebo Jetty or use --container'
    # Source builds expose gz.sim10/gz.math9; Debian/Ubuntu packages install the
    # same bindings without a version suffix.
    if ! /usr/bin/python3 -c 'from gz.sim10 import Model, Link; from gz.math9 import Vector3d' >/dev/null 2>&1 &&
       ! /usr/bin/python3 -c 'from gz.sim import Model, Link; from gz.math import Vector3d' >/dev/null 2>&1; then
      fail 'system python3 has no gz-sim 10 bindings (gz.sim10 or gz.sim)'
    fi
    PYTHONPATH="$PWD/tools/simulate/plugin${PYTHONPATH:+:$PYTHONPATH}" \
      /usr/bin/python3 -c 'import funnel_drone_system' >/dev/null 2>&1 \
      || fail 'cannot import funnel_drone_system from tools/simulate/plugin'
  fi
}

check_files() {
  [[ -f "$sdf" ]] || fail "missing $sdf; run tools/simulate/build_world.py"
  [[ -f "$route" ]] || fail "missing $route"
  if [[ "$container" == true ]]; then
    docker run --rm -v "$PWD:/work" -w /work "$image" \
      gz sdf -k "/work/$folder/funnel_physics.sdf" >/dev/null 2>&1 \
      || fail "gz sdf rejects $folder/funnel_physics.sdf"
    if [[ -f "$folder/city.sim.glb" ]]; then
      docker run --rm -v "$PWD:/work" -w /work "$image" \
        python3 tools/simulate/check_glb.py "/work/$folder/city.sim.glb" >/dev/null 2>&1 \
        || fail "Assimp cannot import $folder/city.sim.glb; rebuild the world"
    fi
  else
    gz sdf -k "$sdf" >/dev/null 2>&1 || fail "gz sdf rejects $sdf"
  fi
}

record_open_gazebo_windows() {
  if [[ "$headless" == true ]] || ! command -v hyprctl >/dev/null 2>&1; then
    return 0
  fi
  FUNNEL_IGNORE_WINDOWS="$(python3 tools/simulate/screenshot.py --list-gazebo 2>/dev/null | paste -sd, - || true)"
  export FUNNEL_IGNORE_WINDOWS
}

prepare_gui_home() {
  if [[ "$headless" == true ]]; then return 0; fi
  gui_home="$(mktemp -d "${TMPDIR:-/tmp}/funnel-gui-XXXXXX")"
  "$planner" tools/simulate/gui_config.py \
    --metadata "$folder/world_metadata.json" \
    --output "$gui_home/.gz/sim/10/gui.config" >/dev/null
}

unpause_world() {
  local request=(
    service -s "/world/$world/control"
    --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean
    --timeout 5000 --req 'pause: false'
  )
  for _ in 1 2 3; do
    if [[ "$container" == true ]]; then
      if docker exec "$container_name" gz "${request[@]}" 2>/dev/null | grep -q 'data: true'; then
        return 0
      fi
    elif /usr/bin/gz "${request[@]}" 2>/dev/null | grep -q 'data: true'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_screenshots() {
  if [[ "$screenshots" == false || "$headless" == true ]]; then return 0; fi
  if [[ "$screenshots" == auto ]]; then screenshots=true; fi
  # Three moments spread over the planned flight: 20 %, 50 % and 80 % of the
  # nominal duration in telemetry_metadata.json (fallback: fixed seconds).
  local offsets
  offsets="$("$planner" -c 'import json, sys
try:
    duration = json.load(open(sys.argv[1]))["nominal_duration"]
except Exception:
    raise SystemExit(1)
print(" ".join(str(max(1, round(duration * share))) for share in (0.2, 0.5, 0.8)))' \
    "$folder/telemetry_metadata.json" 2>/dev/null || true)"
  if [[ -z "$offsets" ]]; then offsets='10 30 50'; fi
  (
    declare -A taken=()
    while :; do
      if [[ ! -s "$csv" ]]; then sleep 0.5; continue; fi
      local line sim_time phase
      line="$(tail -n 1 "$csv" 2>/dev/null || true)"
      [[ -n "$line" ]] || { sleep 0.5; continue; }
      sim_time="${line%%,*}"
      phase="${line##*,}"
      phase="${phase%$'\r'}"
      for offset in $offsets; do
        if [[ -z "${taken[$offset]:-}" ]] \
            && awk -v t="$sim_time" -v o="$offset" 'BEGIN { exit !(t >= o) }'; then
          taken[$offset]=1
          python3 tools/simulate/screenshot.py \
            --output "$folder/screenshot_t$(printf '%03d' "$offset").png" \
            --run-id "$FUNNEL_RUN_ID" --sim-time "$sim_time" --phase "$phase" \
            --log "$log" || true
        fi
      done
      if [[ "$phase" == complete && -z "${taken[complete]:-}" ]]; then
        taken[complete]=1
        python3 tools/simulate/screenshot.py \
          --output "$folder/screenshot_complete.png" \
          --run-id "$FUNNEL_RUN_ID" --sim-time "$sim_time" --phase "$phase" \
          --log "$log" || true
        break
      fi
      sleep 0.5
    done
  ) &
  screenshot_pid=$!
}

wait_for_completion() {
  local elapsed=0
  while [[ "$elapsed" -lt "$timeout_s" ]]; do
    if [[ -s "$csv" ]] && grep -q ',complete' "$csv"; then
      echo 'Route complete'
      sleep 3
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

resolve_gpu
if [[ "$pull" == true && "$container" == true ]]; then
  docker pull "$image"
fi

if [[ "$check_only" == true ]]; then
  check_environment
  check_files
  echo "check: runtime, plugin, world, SDF and visual mesh are ready"
  echo "runtime: $([[ "$container" == true ]] && echo "container $image" || echo 'native gz')"
  echo "gpu: $(gpu_label)"
  echo "world: $world"
  echo "run:   $folder"
  exit 0
fi

if [[ "$no_build" != true ]]; then
  build_options=(--mission "$mission" --goal "$goal")
  if [[ "$show_surface" == true ]]; then build_options+=(--surface); fi
  "$planner" tools/simulate/build_world.py "${build_options[@]}"
fi
check_environment
check_files

timestamp="$(date +%Y%m%d_%H%M%S)"
for name in physics_telemetry.csv telemetry_metadata.json; do
  if [[ -f "$folder/$name" ]]; then
    stem="${name%.*}"
    suffix="${name##*.}"
    mv "$folder/$name" "$folder/${stem}_${timestamp}.${suffix}"
    echo "Backup: $folder/${stem}_${timestamp}.${suffix}"
  fi
done

export FUNNEL_RUN_ID="${timestamp}-$$"
export FUNNEL_ROUTE="$route"
export FUNNEL_OUTPUT_DIR="$output"
export FUNNEL_GPU="$(gpu_label)"
export PYTHONPATH="$PWD/tools/simulate/plugin:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$software" == true ]]; then export LIBGL_ALWAYS_SOFTWARE=1; fi

sim_args=(-r -v 3)
if [[ "$headless" == true ]]; then sim_args=(-s -r -v 3); fi

record_open_gazebo_windows
if [[ "$container" == true ]]; then
  prepare_gui_home
  docker_args=(--rm --name "$container_name" --user "$(id -u):$(id -g)"
               -v "$PWD:/work" -w /work
               -e FUNNEL_ROUTE="/work/$folder/route.json"
               -e FUNNEL_OUTPUT_DIR="/work/$folder"
               -e FUNNEL_RUN_ID -e FUNNEL_GPU
               -e PYTHONPATH=/work/tools/simulate/plugin:/usr/lib/python3/dist-packages)
  if [[ "$headless" == true ]]; then
    docker_args+=(-e HOME=/tmp -e XDG_RUNTIME_DIR=/tmp)
  else
    docker_args+=(-e DISPLAY -e QT_QPA_PLATFORM=xcb
                  -e HOME=/tmp/gui-home -e XDG_RUNTIME_DIR=/tmp/gui-home
                  -v /tmp/.X11-unix:/tmp/.X11-unix:ro
                  -v "$gui_home:/tmp/gui-home")
  fi
  case "$gpu" in
    nvidia) docker_args+=(--device nvidia.com/gpu=all
                          -e __NV_PRIME_RENDER_OFFLOAD=1
                          -e __GLX_VENDOR_LIBRARY_NAME=nvidia) ;;
    intel) docker_args+=(--device /dev/dri) ;;
    software) docker_args+=(-e LIBGL_ALWAYS_SOFTWARE=1) ;;
  esac
  echo "Running in $image with $(gpu_label)"
  docker run "${docker_args[@]}" "$image" \
    gz sim "${sim_args[@]}" "/work/$folder/funnel_physics.sdf" >"$log" 2>&1 &
  gazebo_pid=$!
else
  prepare_gui_home
  echo "Running native gz with $(gpu_label)"
  if [[ "$headless" == true ]]; then
    bash tools/simulate/gazebo_system_python.sh sim "${sim_args[@]}" "$sdf" >"$log" 2>&1 &
  else
    HOME="$gui_home" XDG_RUNTIME_DIR="$gui_home" \
      bash tools/simulate/gazebo_system_python.sh sim "${sim_args[@]}" "$sdf" >"$log" 2>&1 &
  fi
  gazebo_pid=$!
fi

ready=false
for _ in $(seq 1 40); do
  if ! kill -0 "$gazebo_pid" 2>/dev/null; then
    tail -20 "$log" >&2
    fail "Gazebo exited before the controller loaded; read $log"
  fi
  if [[ -f "$folder/telemetry_metadata.json" ]] \
      && grep -q "\"run_id\": \"$FUNNEL_RUN_ID\"" "$folder/telemetry_metadata.json"; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  tail -20 "$log" >&2
  fail "the plugin did not initialize; read $log"
fi
echo "Controller ready; unpausing $world"

if ! unpause_world; then
  if [[ "$headless" == true ]]; then
    fail "could not unpause /world/$world"
  fi
  echo "run_simulate: the world did not answer the unpause request; it already runs (-r)" >&2
fi

start_screenshots

if [[ "$headless" == true ]]; then
  if ! wait_for_completion; then
    echo "run_simulate: timeout after ${timeout_s}s without a complete phase" >&2
  fi
  if [[ "$container" == true ]]; then
    docker stop "$container_name" >/dev/null 2>&1 || true
  else
    kill "$gazebo_pid" 2>/dev/null || true
  fi
  wait "$gazebo_pid" 2>/dev/null || true
else
  if [[ "$keep_open" == true ]]; then
    echo 'Gazebo is open; close the window to finish the session'
    wait "$gazebo_pid" || true
  elif ! wait_for_completion; then
    echo "run_simulate: timeout after ${timeout_s}s without a complete phase" >&2
  fi
  [[ -n "$screenshot_pid" ]] && wait "$screenshot_pid" 2>/dev/null || true
  if [[ "$container" == true ]]; then
    docker stop "$container_name" >/dev/null 2>&1 || true
  else
    kill "$gazebo_pid" 2>/dev/null || true
  fi
  wait "$gazebo_pid" 2>/dev/null || true
fi

[[ -f "$folder/physics_telemetry.csv" ]] || fail 'no telemetry was written'
[[ -f "$folder/telemetry_metadata.json" ]] || fail 'no metadata was written'
echo "Telemetry: $(($(wc -l <"$folder/physics_telemetry.csv") - 1)) rows"
echo "Save at: $PWD/$folder/physics_telemetry.csv"
echo "Save at: $PWD/$folder/telemetry_metadata.json"
