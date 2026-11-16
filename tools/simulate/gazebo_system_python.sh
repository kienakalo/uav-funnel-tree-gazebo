#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main runtime: Bash; local Python plugin directory; Ubuntu system commands.
# Gazebo embeds the system Python and needs the apt-installed gz bindings, so
# the venv is removed from the environment before gz starts.
set -euo pipefail
cd "$(dirname "$0")/../.."
unset VIRTUAL_ENV PYTHONHOME
export PATH="/usr/bin:/bin:$PATH"
export PYTHONPATH="$PWD/tools/simulate/plugin:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONNOUSERSITE=1
exec /usr/bin/gz "$@"
