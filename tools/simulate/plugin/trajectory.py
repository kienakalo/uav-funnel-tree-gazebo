# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: bisect, math (Python standard library).
# Catmull-Rom sampling and a trapezoidal speed profile are implemented locally.
"""Smooth time parameterization through the planned waypoints.

The earlier version flew each segment as a quintic 0 -> 0, so the drone came to
a stop at every waypoint. This version samples a Catmull-Rom spline through the
waypoints, measures its arc length, and follows one trapezoidal speed profile
(accelerate, cruise, decelerate) over the whole route. Speed and direction stay
continuous, and the drone only stops at the final point.
"""
import bisect
import math

SAMPLE_SPACING = 0.2  # metres between spline samples


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(a):
    length = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if length <= 1e-12:
        return (0.0, 0.0, 0.0), 0.0
    return (a[0] / length, a[1] / length, a[2] / length), length


def _hermite(p0, p1, m0, m1, u):
    u2 = u * u
    u3 = u2 * u
    h00 = 2 * u3 - 3 * u2 + 1
    h10 = u3 - 2 * u2 + u
    h01 = -2 * u3 + 3 * u2
    h11 = u3 - u2
    return tuple(h00 * a + h10 * b + h01 * c + h11 * d
                 for a, b, c, d in zip(p0, m0, p1, m1))


class Trajectory:
    def __init__(self, points, max_speed=5., dwell=0., max_acceleration=3.,
                 descent_speed=None):
        if max_speed <= 0 or dwell < 0 or not points:
            raise ValueError('Invalid trajectory settings.')
        if max_acceleration is None:
            max_acceleration = 3.
        if not math.isfinite(max_acceleration) or max_acceleration <= 0:
            raise ValueError('Invalid trajectory acceleration limit.')
        self.points = [tuple(map(float, point)) for point in points]
        if len(self.points) < 2:
            raise ValueError('A trajectory needs at least two waypoints.')
        self.dwell = dwell
        self.max_speed = float(max_speed)
        self.max_acceleration = float(max_acceleration)
        self.descent_speed = descent_speed

        # Catmull-Rom tangents from centred differences; endpoints use the
        # adjacent segment so the curve starts and ends on the waypoints.
        count = len(self.points)
        tangents = []
        for index in range(count):
            if index == 0:
                tangent = _sub(self.points[1], self.points[0])
            elif index == count - 1:
                tangent = _sub(self.points[-1], self.points[-2])
            else:
                tangent = tuple(0.5 * value for value in
                                _sub(self.points[index + 1], self.points[index - 1]))
            tangents.append(tangent)

        samples = []
        distance = 0.0
        previous = self.points[0]
        for index in range(count - 1):
            p0, p1 = self.points[index], self.points[index + 1]
            m0, m1 = tangents[index], tangents[index + 1]
            steps = max(2, int(math.ceil(_norm(_sub(p1, p0))[1] / SAMPLE_SPACING)))
            for step in range(steps):
                point = _hermite(p0, p1, m0, m1, step / steps)
                distance += _norm(_sub(point, previous))[1]
                samples.append((distance, point, index))
                previous = point
        distance += _norm(_sub(self.points[-1], previous))[1]
        samples.append((distance, self.points[-1], count - 2))
        self.samples = samples
        self.length = distance

        # Unit tangents and dT/ds along the sampled curve: the feedforward uses
        # v^2 * dT/ds as the centripetal acceleration, so the controller does not
        # have to invent it at every corner.
        tangents = []
        for index, (_, point, _) in enumerate(samples):
            if index == 0:
                delta = _sub(samples[1][1], samples[0][1])
            elif index == len(samples) - 1:
                delta = _sub(samples[-1][1], samples[-2][1])
            else:
                delta = _sub(samples[index + 1][1], samples[index - 1][1])
            tangents.append(_norm(delta)[0])
        curvature = []
        for index in range(len(samples)):
            if index == 0:
                span = samples[1][0] - samples[0][0]
                delta = _sub(tangents[1], tangents[0])
            elif index == len(samples) - 1:
                span = samples[-1][0] - samples[-2][0]
                delta = _sub(tangents[-1], tangents[-2])
            else:
                span = samples[index + 1][0] - samples[index - 1][0]
                delta = _sub(tangents[index + 1], tangents[index - 1])
            curvature.append(tuple(value / span for value in delta)
                             if span > 1e-9 else (0.0, 0.0, 0.0))
        self.tangents = tangents
        self.curvature = curvature

        # One trapezoidal profile for the whole route.
        limit = self.max_speed
        accel = self.max_acceleration
        if self.descent_speed and self.points[-2][:2] == self.points[-1][:2]:
            limit = min(limit, self.descent_speed)
        if distance <= 1e-9:
            self.ramp_time = 0.0
            self.cruise_time = 0.0
            self.peak_speed = 0.0
        else:
            ramp_distance = limit * limit / (2 * accel)
            if 2 * ramp_distance <= distance:
                self.ramp_time = limit / accel
                self.cruise_time = (distance - 2 * ramp_distance) / limit
                self.peak_speed = limit
            else:
                self.peak_speed = math.sqrt(accel * distance)
                self.ramp_time = self.peak_speed / accel
                self.cruise_time = 0.0
        self.motion_duration = 2 * self.ramp_time + self.cruise_time
        self.duration = self.motion_duration + self.dwell

    def _profile(self, t):
        """Return (arc length, speed, tangential acceleration) at time t."""
        if t <= 0:
            return 0.0, 0.0, self.max_acceleration
        if t >= self.motion_duration:
            return self.length, 0.0, 0.0
        if t < self.ramp_time:
            return (0.5 * self.max_acceleration * t * t,
                    self.max_acceleration * t, self.max_acceleration)
        accel = self.max_acceleration
        ramp_distance = 0.5 * accel * self.ramp_time ** 2
        t2 = t - self.ramp_time
        if t2 <= self.cruise_time:
            return (ramp_distance + self.peak_speed * t2,
                    self.peak_speed, 0.0)
        t3 = t2 - self.cruise_time
        speed = max(0.0, self.peak_speed - accel * t3)
        length = (ramp_distance + self.peak_speed * self.cruise_time
                  + self.peak_speed * t3 - 0.5 * accel * t3 * t3)
        return min(length, self.length), speed, -accel

    def _sample(self, length):
        """Position, tangent, curvature and segment index at an arc length."""
        distances = [sample[0] for sample in self.samples]
        index = max(1, bisect.bisect_left(distances, length))
        index = min(index, len(self.samples) - 1)
        s0, p0, segment = self.samples[index - 1]
        s1, p1, _ = self.samples[index]
        span = s1 - s0
        ratio = 0.0 if span <= 1e-12 else (length - s0) / span
        position = tuple(a + ratio * (b - a) for a, b in zip(p0, p1))
        tangent = tuple(a + ratio * (b - a)
                        for a, b in zip(self.tangents[index - 1], self.tangents[index]))
        tangent, _ = _norm(tangent)
        curvature = tuple(a + ratio * (b - a)
                          for a, b in zip(self.curvature[index - 1], self.curvature[index]))
        return position, tangent, curvature, segment

    def state(self, t):
        zero = (0.0, 0.0, 0.0)
        if t < 0:
            return self.points[0], zero, zero, -1, 'waiting'
        if t >= self.duration:
            return self.points[-1], zero, zero, len(self.points) - 2, 'complete'
        if t >= self.motion_duration:
            return self.points[-1], zero, zero, len(self.points) - 2, 'dwell'
        length, speed, acceleration = self._profile(t)
        position, tangent, curvature, segment = self._sample(length)
        velocity = tuple(speed * value for value in tangent)
        # The route has sharp corners, so dT/ds spikes there; cap the
        # centripetal term instead of asking for an impossible acceleration.
        centripetal = [max(-3.0, min(3.0, speed * speed * bend))
                       for bend in curvature]
        acceleration_vector = tuple(acceleration * value + bend
                                    for value, bend in zip(tangent, centripetal))
        return position, velocity, acceleration_vector, segment, 'moving'


def control_acceleration(position, velocity, goal, goal_velocity, goal_acceleration):
    """Mass-normalized feedforward + PD tracking; gravity is added by the plugin."""
    return tuple(max(-6., min(6., a + 2.5 * (r - x) + 3.2 * (vr - v)))
                 for x, v, r, vr, a in zip(position, velocity, goal, goal_velocity,
                                           goal_acceleration))
