#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main runtime: Bash; Gazebo Jetty; system Python with gz bindings; local
# tools/simulate/build_world.py and tools/simulate/plugin.
# Build one world, fly it in Gazebo and leave the telemetry on disk.
#
# Usage:
#   bash tools/simulate/run_simulate.sh [--mission STEM] [--goal ID] [--headless]
#                                       [--software] [--show-surface] [--timeout S]
#   bash tools/simulate/run_simulate.sh --check
#
# --check verifies the environment (gz, gz.sim10 bindings, plugin import), the
# world files and the SDF without opening Gazebo. The default mission is
# city.standardized.triangulation and the default goal is g1; goals are
# fail-closed, so a route with several goals needs --goal.
usage() {
  cat <<'EOF'
Build one world, fly it in Gazebo and leave the telemetry on disk.

Usage:
  bash tools/simulate/run_simulate.sh [--mission STEM] [--goal ID] [--headless]
                                      [--software] [--show-surface] [--timeout S]
  bash tools/simulate/run_simulate.sh --check

--check verifies gz, the gz.sim10 bindings, the plugin import, the world files
and the SDF without opening Gazebo.
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
timeout_s=900

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mission) mission="$2"; shift 2 ;;
    --goal) goal="$2"; shift 2 ;;
    --headless) headless=true; shift ;;
    --software) software=true; shift ;;
    --show-surface) show_surface=true; shift ;;
    --check) check_only=true; shift ;;
    --timeout) timeout_s="$2"; shift 2 ;;
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
planner=python3
[[ -x .venv/bin/python ]] && planner=.venv/bin/python

fail() { echo "run_simulate: $*" >&2; exit 1; }

check_environment() {
  command -v gz >/dev/null 2>&1 || fail "gz not found; install Gazebo Jetty"
  # Source builds expose gz.sim10/gz.math9; Debian/Ubuntu packages install the
  # same bindings without a version suffix.
  if ! /usr/bin/python3 -c 'from gz.sim10 import Model, Link; from gz.math9 import Vector3d' >/dev/null 2>&1 &&
     ! /usr/bin/python3 -c 'from gz.sim import Model, Link; from gz.math import Vector3d' >/dev/null 2>&1; then
    fail "system python3 has no gz-sim 10 bindings (gz.sim10 or gz.sim)"
  fi
  PYTHONPATH="$PWD/tools/simulate/plugin${PYTHONPATH:+:$PYTHONPATH}" \
    /usr/bin/python3 -c 'import funnel_drone_system' >/dev/null 2>&1 \
    || fail "cannot import funnel_drone_system from tools/simulate/plugin"
}

check_files() {
  [[ -f "$sdf" ]] || fail "missing $sdf; run tools/simulate/build_world.py"
  [[ -f "$route" ]] || fail "missing $route"
  gz sdf -k "$sdf" >/dev/null 2>&1 || fail "gz sdf rejects $sdf"
}

if [[ "$check_only" == true ]]; then
  check_environment
  check_files
  echo "check: gz, gz.sim10/gz.sim, plugin, world and SDF are ready"
  echo "world: $world"
  echo "run:   $folder"
  exit 0
fi

build_options=(--mission "$mission" --goal "$goal")
[[ "$show_surface" == true ]] && build_options+=(--surface)
"$planner" tools/simulate/build_world.py "${build_options[@]}"
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
export PYTHONPATH="$PWD/tools/simulate/plugin:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
[[ "$software" == true ]] && export LIBGL_ALWAYS_SOFTWARE=1

if [[ "$headless" == true ]]; then
  sim_args=(-s -r -v 3)
else
  sim_args=(-r -v 3)
fi

bash tools/simulate/gazebo_system_python.sh sim "${sim_args[@]}" "$sdf" >"$log" 2>&1 &
gazebo_pid=$!
trap 'kill "$gazebo_pid" 2>/dev/null || true' EXIT

ready=false
for _ in $(seq 1 30); do
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

started=false
for _ in 1 2 3; do
  if /usr/bin/gz service -s "/world/$world/control" \
      --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean \
      --timeout 5000 --req 'pause: false' 2>/dev/null | grep -q 'data: true'; then
    started=true
    break
  fi
  sleep 1
done
[[ "$started" == true ]] || fail "could not unpause /world/$world"

if [[ "$headless" == true ]]; then
  elapsed=0
  while [[ "$elapsed" -lt "$timeout_s" ]]; do
    kill -0 "$gazebo_pid" 2>/dev/null || break
    if [[ -f "$folder/physics_telemetry.csv" ]] \
        && grep -q ',complete$' "$folder/physics_telemetry.csv"; then
      echo "Route complete; stopping the server"
      sleep 3
      break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  kill "$gazebo_pid" 2>/dev/null || true
  wait "$gazebo_pid" 2>/dev/null || true
  if [[ "$elapsed" -ge "$timeout_s" ]]; then
    echo "run_simulate: timeout after ${timeout_s}s without a complete phase" >&2
  fi
else
  echo "Gazebo is open; close the window to finish the session"
  wait "$gazebo_pid" || true
fi

[[ -f "$folder/physics_telemetry.csv" ]] || fail "no telemetry was written"
[[ -f "$folder/telemetry_metadata.json" ]] || fail "no metadata was written"
echo "Telemetry: $(($(wc -l <"$folder/physics_telemetry.csv") - 1)) rows"
echo "Save at: $PWD/$folder/physics_telemetry.csv"
echo "Save at: $PWD/$folder/telemetry_metadata.json"
