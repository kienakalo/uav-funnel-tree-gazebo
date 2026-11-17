# syntax=docker/dockerfile:1
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Ubuntu 24.04 packages; Python 3.12 wheels (numpy, shapely,
# matplotlib, pillow); Gazebo Jetty 10.5.0 from the base image.
# One image for the whole pipeline: Gazebo Jetty for `simulate`, and the Python
# packages `data`, `plan`, `validate` and the figures use.
#
# The base is pinned by digest, because the Gazebo version decides how a route
# flies. Rebuilding from a floating tag would silently change the vehicle
# dynamics behind the numbers in the report. See docs/tools/docker.md for the
# checks this image has to pass before its results may be quoted.
FROM ghcr.io/openrobotics/gazebo@sha256:452ff649281065121a524ef92354091ac069f2c9b0f73f61fd4c77c61bab08c7

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    # The image's interpreter, not a mounted host .venv (main.py honours this).
    FUNNEL_PYTHON=/usr/bin/python3 \
    # gz is installed here, so `main.py simulate` must not start a container.
    FUNNEL_RUNTIME=native

# The base image ships Python 3.12 without pip, and Ubuntu 24.04 marks the
# system environment as externally managed; hence the two apt lines and
# --break-system-packages. --ignore-installed is for the apt numpy 1.26 that
# pip cannot uninstall (no RECORD file): the pinned wheels land in
# /usr/local/lib/python3.12/dist-packages, which Python searches before
# /usr/lib/python3/dist-packages, so the gz bindings stay reachable.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-pip \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m pip install --no-cache-dir --break-system-packages \
      --ignore-installed \
      numpy==2.5.4 \
      shapely==2.2.0 \
      matplotlib==3.11.2 \
      pillow==13.0.0 \
 && python3 -c 'import numpy, shapely, matplotlib; \
print("numpy", numpy.__version__, "shapely", shapely.__version__, \
"matplotlib", matplotlib.__version__)' \
 # The version check above creates the cache as root; a container running as
 # the host user must be able to create it itself.
 && rm -rf /tmp/matplotlib \
 && gz sim --versions

WORKDIR /work
COPY . /work

# Bare `python3 main.py` runs data -> plan -> simulate. The mission files and
# the surface are in the image, so a run needs nothing mounted; mount the
# repository over /work to use your own copy, and mount a host directory over
# generated/ or results/ to keep what the run writes.
CMD ["python3", "main.py"]
