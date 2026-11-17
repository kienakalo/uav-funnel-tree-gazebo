# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Gazebo Jetty Python bindings (gz.sim10/gz.math9 from a source
# build, gz.sim/gz.math from the Debian/Ubuntu packages); csv, json, math, os,
# pathlib (Python stdlib); trajectory (local project module).
"""Fly one planned Funnel route with a 1 kg point-mass force controller.

Gazebo loads this module through gz-sim-python-system-loader-system. The world
sets the start pose; this plugin reads the route named by FUNNEL_ROUTE, writes
physics_telemetry.csv and telemetry_metadata.json into FUNNEL_OUTPUT_DIR, and
pushes the body with feedforward + PD acceleration, gravity compensated.

Point-mass model with world force at the centre of mass; not a rotor or
autopilot simulation.

Environment:
  FUNNEL_ROUTE        absolute path to route.json (required)
  FUNNEL_OUTPUT_DIR   absolute path for the CSV and metadata (required)
  FUNNEL_RUN_ID       identifier of this session (optional, recorded)
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path

try:  # Debian/Ubuntu packages install the bindings without a version suffix
    from gz.math import Vector3d
    from gz.sim import Model, Link
except ModuleNotFoundError:  # source builds expose gz.math9 and gz.sim10
    from gz.math9 import Vector3d
    from gz.sim10 import Model, Link
try:  # The trail needs gz-transport; the flight itself does not.
    from gz.msgs.marker_pb2 import Marker
    from gz.transport import Node as TransportNode
    TRAIL_AVAILABLE = True
except ModuleNotFoundError:
    TRAIL_AVAILABLE = False
from trajectory import Trajectory, control_acceleration

COLUMNS = ['sim_time', 'x', 'y', 'z', 'target_x', 'target_y', 'target_z', 'error',
           'vx', 'vy', 'vz', 'target_vx', 'target_vy', 'target_vz',
           'segment', 'phase']
MODEL = '1 kg point mass with force feedback; box body collision; decorative rotors'


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError(f'{name} is not set; run the simulate script')
    return Path(value)


class FunnelDroneSystem:
    label = 'Funnel Physics'
    progress_interval = 10.

    def configure(self, entity, sdf, ecm, event_mgr):
        self.link = Link(Model(entity).canonical_link(ecm))
        self.link.enable_velocity_checks(ecm, True)
        route_path = required_env('FUNNEL_ROUTE')
        output_dir = required_env('FUNNEL_OUTPUT_DIR')
        output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = os.environ.get('FUNNEL_RUN_ID')

        data = json.loads(route_path.read_text(encoding='utf-8'))
        self.start_delay = float(data.get('start_delay', 2.))
        if not math.isfinite(self.start_delay) or self.start_delay < 0:
            raise ValueError('Invalid trajectory start delay')
        self.trajectory = Trajectory(data['waypoints'],
                                     max_speed=data.get('speed', 5.),
                                     dwell=data.get('dwell', 1.5),
                                     max_acceleration=data.get('max_acceleration'),
                                     descent_speed=data.get('descent_speed'))
        self.log = (output_dir / 'physics_telemetry.csv').open('w', newline='')
        self.writer = csv.writer(self.log)
        self.writer.writerow(COLUMNS)
        self.last_log = -1.
        self.start_time = None
        self.completed = False
        self.last_progress = -math.inf
        self.marker_period = 0.25
        self.last_marker = -math.inf
        self.trail = None
        self.trail_publisher = None
        self.node = None
        if TRAIL_AVAILABLE and os.environ.get('FUNNEL_TRAIL', '1') != '0':
            self.node = TransportNode()
            self.trail_publisher = self.node.advertise('/marker', Marker)
            trail = Marker()
            trail.ns = 'funnel_trail'
            trail.id = 1
            trail.type = Marker.LINE_STRIP
            trail.action = Marker.ADD_MODIFY
            trail.visibility = Marker.GUI
            trail.scale.x = 0.8
            # Magenta: distinct from the orange planned route and the blue city.
            trail.material.ambient.r = 1.0
            trail.material.ambient.g = 0.05
            trail.material.ambient.b = 0.75
            trail.material.ambient.a = 1.0
            trail.material.diffuse.r = 1.0
            trail.material.diffuse.g = 0.1
            trail.material.diffuse.b = 0.8
            trail.material.diffuse.a = 1.0
            self.trail = trail
        else:
            self.trail_publisher = None

        metadata = {
            'route_sha256': hashlib.sha256(route_path.read_bytes()).hexdigest(),
            'model': MODEL,
            'nominal_duration': self.trajectory.duration + self.start_delay,
            'world': data.get('world'),
            'mission': data.get('mission'),
            'goal': data.get('goal'),
            'run_id': self.run_id,
            'trail': self.trail_publisher is not None,
        }
        (output_dir / 'telemetry_metadata.json').write_text(
            json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        print(f'[{self.label}] {data.get("goal", "?")}: feedforward PD configured; '
              f'route duration about {metadata["nominal_duration"]:.1f} simulated '
              f'seconds; telemetry in {output_dir}', flush=True)

    def pre_update(self, info, ecm):
        if info.paused:
            return
        pose = self.link.world_pose(ecm)
        velocity = self.link.world_linear_velocity(ecm)
        if pose is None or velocity is None:
            return
        t = info.sim_time.total_seconds()
        if self.start_time is None:
            self.start_time = t
        goal, goal_v, goal_a, segment, phase = self.trajectory.state(
            t - self.start_time - self.start_delay)
        p = pose.pos()
        position = (p.x(), p.y(), p.z())
        v = (velocity.x(), velocity.y(), velocity.z())
        a = control_acceleration(position, v, goal, goal_v, goal_a)
        self.link.add_world_force(ecm, Vector3d(a[0], a[1], a[2] + 9.8))
        if t - self.last_log >= .1:
            error = math.dist(position, goal)
            self.writer.writerow([t, *position, *goal, error, *v, *goal_v,
                                  segment, phase])
            self.log.flush()
            self.last_log = t
        if self.trail is not None and t - self.last_marker >= self.marker_period:
            self.last_marker = t
            point = self.trail.point.add()
            point.x, point.y, point.z = position
            if len(self.trail.point) >= 2:
                self.trail_publisher.publish(self.trail)
        if phase == 'complete' and not self.completed:
            print(f'[{self.label}] Route complete; holding final position.',
                  flush=True)
            self.completed = True
        if (self.progress_interval is not None and not self.completed
                and t - self.last_progress >= self.progress_interval):
            print(f'[{self.label}] t={t - self.start_time:.1f}s; segment={segment}; '
                  f'phase={phase}; error={math.dist(position, goal):.6f}', flush=True)
            self.last_progress = t


def get_system():
    return FunnelDroneSystem()
