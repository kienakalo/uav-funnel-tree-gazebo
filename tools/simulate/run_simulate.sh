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
#                                       [--keep-open]
#                                       [--pause-at S[,S...]] [--pause-on-error M]
#                                       [--slow R] [--hold S] [--keys]
#   bash tools/simulate/run_simulate.sh --check | --no-build
#
# The Gazebo container is the default so the same tree runs on any machine;
# --native uses a Gazebo installed on the host. --check verifies the runtime,
# the plugin import, the world files and the SDF without opening Gazebo.
# Goals are fail-closed, so a route with several goals needs --goal.
#
# Pausing uses /world/<world>/control, so the plugin sees info.paused and stops
# integrating: simulated time freezes and the telemetry stays consistent. The
# timeout counts only the time the world is running, never the paused part.
usage() {
  cat <<'EOF'
Fly one planned route in Gazebo and leave the telemetry on disk.

Usage:
  bash tools/simulate/run_simulate.sh [--mission STEM] [--goal ID] [--headless]
                                      [--software] [--show-surface] [--timeout S]
                                      [--container|--native] [--image NAME]
                                      [--gpu auto|nvidia|intel|software]
                                      [--keep-open]
                                      [--pause-at S[,S...]] [--pause-on-error M]
                                      [--slow R] [--hold S] [--keys]
  bash tools/simulate/run_simulate.sh --check | --no-build

--check verifies Docker (or a native gz), the gz-sim 10 bindings, the plugin
import, the world files, the SDF and the visual mesh without opening Gazebo.
The default is the container ghcr.io/openrobotics/gazebo:jetty-full; --native
runs the gz found on PATH. The GUI needs a display; --headless does not.

Pausing:
  --pause-at S          pause when simulated time reaches S (repeat or comma)
  --pause-on-error M    pause the first time the tracking error passes M metres
  --slow R              run the physics at R times real time (0.25 = slow motion)
  --hold S              resume by itself after S seconds paused (default: wait)
  --keys                space/p pause or resume, s +1 ms, d +100 ms, q stop
  kill -USR1 <pid>      pause or resume from another terminal; -USR2 steps 100 ms
Paused time does not count towards --timeout, and the telemetry keeps the same
simulated timestamps, so a paused run validates like an unpaused one.
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
keep_open=false
pull=false
pause_at=''
error_limit=''
slow=''
hold_s=''
keys=false

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
    --keep-open) keep_open=true; shift ;;
    --pull) pull=true; shift ;;
    --pause-at) pause_at="${pause_at:+$pause_at,}$2"; shift 2 ;;
    --pause-on-error) error_limit="$2"; shift 2 ;;
    --slow) slow="$2"; shift 2 ;;
    --hold) hold_s="$2"; shift 2 ;;
    --keys) keys=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "run_simulate: unknown argument $1" >&2; exit 2 ;;
  esac
done

folder="generated/simulate/${mission}-${goal}"
world="funnel_sim_$(printf '%s_%s' "$mission" "$goal" | sed 's/[^A-Za-z0-9]/_/g')"
sdf="$PWD/$folder/funnel_physics.sdf"
route="$PWD/$folder/flown_route.json"
output="$PWD/$folder"
log="$folder/gazebo.log"
csv="$folder/physics_telemetry.csv"
planner="${FUNNEL_PYTHON:-python3}"
if [[ -z ${FUNNEL_PYTHON:-} && -x .venv/bin/python ]]; then
  planner=.venv/bin/python
fi
container_name="funnel-$(printf '%s_%s' "$mission" "$goal" | sed 's/[^A-Za-z0-9]/_/g')-$$"
gui_home=''
gazebo_pid=''

fail() { echo "run_simulate: $*" >&2; exit 1; }

is_number() { [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]; }

timeout_ms=$(awk -v s="$timeout_s" 'BEGIN { printf "%d", (s + 0) * 1000 }')
(( timeout_ms > 0 )) || fail '--timeout must be a positive number of seconds'

pause_targets=()
if [[ -n "$pause_at" ]]; then
  IFS=',' read -r -a pause_targets <<<"$pause_at"
  for target in "${pause_targets[@]}"; do
    is_number "$target" || fail "--pause-at wants seconds, not '$target'"
  done
  if (( ${#pause_targets[@]} > 1 )); then
    # run_to_sim_time only moves forward, so the targets have to be in order.
    mapfile -t pause_targets < <(printf '%s\n' "${pause_targets[@]}" | sort -n)
  fi
fi
for pair in "pause-on-error:$error_limit" "slow:$slow" "hold:$hold_s"; do
  value="${pair#*:}"
  [[ -n "$value" ]] || continue
  is_number "$value" || fail "--${pair%%:*} wants a number, not '$value'"
done
if [[ -n "$error_limit" ]] && ! awk -v m="$error_limit" 'BEGIN { exit !(m + 0 > 0) }'; then
  fail '--pause-on-error must be larger than zero'
fi
if [[ -n "$slow" ]] && ! awk -v r="$slow" 'BEGIN { exit !(r + 0 > 0) }'; then
  fail '--slow must be larger than zero'
fi

# Session state shared by the signal traps and the wait loop.
paused=false
quit=false
held_ms=0
tick=0.25
tick_ms=250
status_ms=10000
target_index=0
last_t=''
stall_ticks=0
# A row appears every 0.1 simulated seconds; --slow stretches that in wall time,
# so the stall limit has to grow with the inverse of the real-time factor.
stall_limit=$(awk -v r="${slow:-1}" 'BEGIN { printf "%d", 5 / (r + 0) + 2 }')

cleanup() {
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

prepare_gui_home() {
  if [[ "$headless" == true ]]; then return 0; fi
  gui_home="$(mktemp -d "${TMPDIR:-/tmp}/funnel-gui-XXXXXX")"
  "$planner" tools/simulate/gui_config.py \
    --metadata "$folder/world_metadata.json" \
    --output "$gui_home/.gz/sim/10/gui.config" >/dev/null
}

world_service() {
  # world_service <service suffix> <request type> <request text>
  # Prints the Boolean reply; empty when the world did not answer.
  local service="/world/$world/$1" reqtype="$2" request="$3"
  if [[ "$container" == true ]]; then
    docker exec "$container_name" gz service -s "$service" --reqtype "$reqtype" \
      --reptype gz.msgs.Boolean --timeout 5000 --req "$request" 2>/dev/null || true
  else
    /usr/bin/gz service -s "$service" --reqtype "$reqtype" \
      --reptype gz.msgs.Boolean --timeout 5000 --req "$request" 2>/dev/null || true
  fi
}

world_control() {
  world_service control gz.msgs.WorldControl "$1" | grep -q 'data: true'
}

world_physics() {
  world_service set_physics gz.msgs.Physics "$1" | grep -q 'data: true'
}

unpause_world() {
  local attempt
  for attempt in 1 2 3; do
    if world_control 'pause: false'; then
      paused=false
      return 0
    fi
    sleep 1
  done
  return 1
}

split_seconds() {
  # split_seconds <seconds>: whole and nanosecond parts in SEC_PART/NANO_PART.
  read -r SEC_PART NANO_PART < <(awk -v v="$1" 'BEGIN {
    n = int((v + 0) * 1e9 + .5); printf "%d %d\n", int(n / 1e9), n % 1000000000 }')
}

arm_target() {
  # Run the world and let it stop by itself at the next --pause-at target, so
  # the pause lands on the requested simulated time instead of one poll later.
  if (( target_index >= ${#pause_targets[@]} )); then
    unpause_world
    return
  fi
  split_seconds "${pause_targets[$target_index]}"
  if world_control "pause: false run_to_sim_time { sec: $SEC_PART, nsec: $NANO_PART }"; then
    paused=false
    return 0
  fi
  return 1
}

set_pause() {
  # set_pause true|false; the plugin ignores ticks while paused, so simulated
  # time stops and the telemetry keeps its normal timestamps.
  local target="$1"
  world_control "pause: $target" || return 1
  paused="$target"
  if [[ "$target" == true ]]; then held_ms=0; fi
  return 0
}

read_sample() {
  # Last telemetry row, in the globals s_t, s_err, s_seg, s_phase.
  [[ -s "$csv" ]] || return 1
  local line
  line="$(tail -c 4000 "$csv" 2>/dev/null | tail -n 1)"
  case "$line" in
    ''|sim_time,*) return 1 ;;
  esac
  IFS=, read -r s_t s_x s_y s_z s_tx s_ty s_tz s_err s_vx s_vy s_vz \
    s_tvx s_tvy s_tvz s_seg s_phase <<<"$line"
  s_phase="${s_phase%$'\r'}"
  [[ -n "$s_t" ]]
}

print_state() {
  [[ -n "${s_t:-}" ]] || return 0
  printf '[funnel]   t=%s s  seg=%s  err=%s m  phase=%s\n' \
    "$(printf '%.1f' "$s_t")" "$s_seg" "$(printf '%.4f' "$s_err")" "$s_phase"
}

at_least() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a + 0 >= b + 0) }'; }

reached() {
  # Rows arrive every 0.1 simulated seconds, so a pause at T freezes the last
  # row slightly before T; 0.15 s of slack is one row plus a little.
  awk -v t="$1" -v target="$2" 'BEGIN { exit !(t + .15 >= target + 0) }'
}

print_keys() {
  echo '[funnel] space/p pause or resume · s +1 ms · d +100 ms · c resume · q stop'
}

resume_hint() {
  if [[ "$keys" == true ]]; then
    print_keys
  else
    echo "[funnel] resume with: kill -USR1 $$"
  fi
}

pause_notice() {
  # pause_notice <reason>
  echo "[funnel] paused: $1"
  read_sample && print_state
  resume_hint
  held_ms=0
}

pause_now() {
  if ! set_pause true; then
    echo "run_simulate: could not pause /world/$world" >&2
    return 1
  fi
  pause_notice "$1"
}

resume_world() {
  # Skip targets that are already behind the frozen time, then let the world
  # run to the next one; a plain resume would cancel a pending target.
  while (( target_index < ${#pause_targets[@]} )) && [[ -n "${last_t:-}" ]] \
      && reached "$last_t" "${pause_targets[$target_index]}"; do
    target_index=$((target_index + 1))
  done
  if ! arm_target; then
    echo "run_simulate: could not resume /world/$world" >&2
    return 1
  fi
  echo '[funnel] resumed'
  return 0
}

toggle_pause() {
  if [[ "$paused" == true ]]; then
    resume_world || true
  else
    pause_now 'requested' || true
  fi
}

step_world() {
  # step_world <milliseconds>; one step is 1 ms because build_world fixes it.
  local ms="$1" request='pause: true step: true'
  if (( ms > 1 )); then request="pause: true multi_step: $ms"; fi
  if [[ "$paused" != true ]] && ! set_pause true; then
    return 1
  fi
  if world_control "$request"; then
    echo "[funnel] stepped ${ms} ms"
    read_sample && print_state
  else
    echo "run_simulate: could not step /world/$world" >&2
    return 1
  fi
}

handle_key() {
  case "$1" in
    ' '|p|P) toggle_pause ;;
    s) step_world 1 ;;
    d|S) step_world 100 ;;
    c|C) resume_world || true ;;
    q|Q) echo '[funnel] stopping; the telemetry flown so far stays on disk'
         quit=true ;;
    h|'?') print_keys ;;
  esac
}

wait_for_session() {
  # 0 complete, 1 timeout, 2 stopped by the user.
  local total_ms=0 since_status=0 key target
  local error_paused=false
  stall_ticks=0
  last_t=''

  while true; do
    if [[ -s "$csv" ]] && grep -q ',complete' "$csv"; then
      echo 'Route complete'
      sleep 3
      return 0
    fi

    if [[ "$keys" == true ]]; then
      if read -r -s -n 1 -t "$tick" key; then
        handle_key "$key"
        if [[ "$quit" == true ]]; then return 2; fi
        continue
      fi
    else
      sleep "$tick"
    fi

    if [[ "$paused" == true ]]; then
      held_ms=$((held_ms + tick_ms))
      if [[ -n "$hold_s" ]] && at_least "$(awk -v ms="$held_ms" 'BEGIN { printf "%.3f", ms / 1000 }')" "$hold_s"; then
        resume_world || true
      fi
    else
      total_ms=$((total_ms + tick_ms))
      if (( total_ms >= timeout_ms )); then
        return 1
      fi
    fi

    read_sample || continue

    # A sample that does not move means the world is frozen: by a --pause-at
    # target, by the GUI pause button or by an error trigger.
    if [[ -n "$last_t" && "$s_t" == "$last_t" ]]; then
      stall_ticks=$((stall_ticks + 1))
      if (( stall_ticks >= stall_limit )) && [[ "$paused" != true ]]; then
        paused=true
        held_ms=0
      fi
    else
      stall_ticks=0
      last_t="$s_t"
      paused=false
    fi

    if (( target_index < ${#pause_targets[@]} )) \
        && reached "$s_t" "${pause_targets[$target_index]}"; then
      target="${pause_targets[$target_index]}"
      target_index=$((target_index + 1))
      paused=true
      pause_notice "--pause-at $target s"
    fi

    if [[ -n "$error_limit" && "$error_paused" != true && "$paused" != true ]] \
        && at_least "$s_err" "$error_limit"; then
      error_paused=true
      pause_now "$(printf -- '--pause-on-error %s m (row t=%.2f s, error %.4f m)' \
        "$error_limit" "$s_t" "$s_err")" || true
    fi

    if [[ "$paused" != true ]]; then
      since_status=$((since_status + tick_ms))
      if (( since_status >= status_ms )); then
        since_status=0
        print_state
      fi
    fi
  done
}

trap 'toggle_pause || true' USR1
trap 'step_world 100 || true' USR2
if [[ "$keys" == true && ! -t 0 ]]; then
  echo 'run_simulate: --keys needs a terminal on stdin; use kill -USR1 instead' >&2
  keys=false
fi

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

if [[ "$container" == true ]]; then
  prepare_gui_home
  docker_args=(--rm --name "$container_name" --user "$(id -u):$(id -g)"
               -v "$PWD:/work" -w /work
               -e FUNNEL_ROUTE="/work/$folder/flown_route.json"
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

if [[ -n "$slow" ]]; then
  if world_physics "real_time_factor: $slow"; then
    echo "[funnel] real-time factor ${slow}x"
  else
    echo "run_simulate: could not set real_time_factor; the world runs at 1x" >&2
  fi
fi

if ! arm_target; then
  if [[ "$headless" == true ]]; then
    fail "could not unpause /world/$world"
  fi
  echo "run_simulate: the world did not answer the unpause request; it already runs (-r)" >&2
fi

if [[ -n "$pause_at" || -n "$error_limit" ]]; then
  echo "[funnel] controls:${pause_at:+ pause-at $pause_at}${error_limit:+ pause-on-error ${error_limit} m}${hold_s:+ hold ${hold_s} s}"
fi
if [[ "$keys" == true ]]; then print_keys; fi

session_status=0
wait_for_session || session_status=$?
case "$session_status" in
  0) ;;
  2) echo 'run_simulate: stopped before the route completed; the telemetry is a partial flight' >&2 ;;
  *) echo "run_simulate: timeout after ${timeout_s}s without a complete phase" >&2 ;;
esac

if [[ "$keep_open" == true && "$headless" != true ]]; then
  echo 'Gazebo is open; close the window to finish the session'
  wait "$gazebo_pid" 2>/dev/null || true
fi
if [[ "$container" == true ]]; then
  docker stop "$container_name" >/dev/null 2>&1 || true
else
  kill "$gazebo_pid" 2>/dev/null || true
fi
wait "$gazebo_pid" 2>/dev/null || true

[[ -f "$folder/physics_telemetry.csv" ]] || fail 'no telemetry was written'
[[ -f "$folder/telemetry_metadata.json" ]] || fail 'no metadata was written'
echo "Telemetry: $(($(wc -l <"$folder/physics_telemetry.csv") - 1)) rows"
echo "Save at: $PWD/$folder/physics_telemetry.csv"
echo "Save at: $PWD/$folder/telemetry_metadata.json"
