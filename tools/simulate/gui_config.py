# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, json, pathlib, re).
"""Write the Gazebo GUI configuration for one simulation run.

Gazebo reads its GUI layout and the initial camera from
``$HOME/.gz/sim/10/gui.config``; the SDF ``<gui><camera>`` element is not
supported (Gazebo logs "can't be converted yet"). The file written here keeps
only the 3D view, the scene manager, mouse control, the world control toolbar
and the marker manager: the city fills the window instead of half of it, and the
marker manager draws the flight trail published on ``/marker``. The world
control toolbar is the play/pause and step button, so a flight can be stopped
from the GUI as well as from the terminal. The camera pose comes from
``build_world.py`` (degrees in ``world_metadata.json``, radians here).

Example:

    python3 tools/simulate/gui_config.py \
      --metadata generated/simulate/city.standardized.triangulation-g1/world_metadata.json \
      --output /tmp/gui-home/.gz/sim/10/gui.config
"""
import argparse
import json
import math
import re
from pathlib import Path

TEMPLATE = """<?xml version="1.0"?>
<window>
  <width>1280</width>
  <height>800</height>
  <style material_theme="Light" material_primary="DeepOrange" material_accent="LightBlue"/>
</window>
<plugin filename="MinimalScene" name="3D View">
  <gz-gui>
    <title>3D View</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="string" key="state">docked</property>
  </gz-gui>
  <engine>ogre2</engine>
  <scene>scene</scene>
  <ambient_light>0.6 0.6 0.6</ambient_light>
  <background_color>0.72 0.81 0.9</background_color>
  <camera_pose>{pose}</camera_pose>
</plugin>
<plugin filename="GzSceneManager" name="Scene Manager">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
<plugin filename="InteractiveViewControl" name="Interactive view control">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
<plugin filename="WorldControl" name="World control">
  <gz-gui>
    <title>World control</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="bool" key="resizable">false</property>
    <property type="double" key="height">72</property>
    <property type="double" key="z">1</property>
    <property type="string" key="state">floating</property>
    <anchors target="3D View">
      <line own="left" target="left"/>
      <line own="bottom" target="bottom"/>
    </anchors>
  </gz-gui>
  <play_pause>true</play_pause>
  <step>true</step>
  <start_paused>false</start_paused>
  <use_event>true</use_event>
</plugin>
<plugin filename="MarkerManager" name="Marker manager">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
"""


def build(camera_pose):
    x, y, z, roll, pitch, yaw = camera_pose
    # Position stays in metres; only the three angles are degrees in metadata.
    pose = (f'{x:.3f} {y:.3f} {z:.3f} '
            f'{math.radians(roll):.6f} {math.radians(pitch):.6f} {math.radians(yaw):.6f}')
    return TEMPLATE.format(pose=pose)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--metadata', type=Path, required=True,
                        help='world_metadata.json with camera_pose in degrees')
    parser.add_argument('--output', type=Path, required=True,
                        help='Where to write the run-specific gui.config')
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding='utf-8'))
    pose = metadata.get('camera_pose')
    if not pose or len(pose) != 6:
        raise SystemExit(f'{args.metadata} has no six-value camera_pose')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(pose), encoding='utf-8')
    print(f'Save at: {args.output}')


if __name__ == '__main__':
    main()
