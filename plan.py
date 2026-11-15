# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python standard library; NumPy (via src/funnel_tree.py).
# City/Gazebo workflow: Shapely, Matplotlib, Gazebo Sim 10 / gz.math9;
# independent MMP reference: pygeodesic (not used by the Funnel planner).
# Versions and module roles: README.md, requirements*.txt.
"""Run experimental Funnel Tree on the bundled geom meshes."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from mesh import read_off
from funnel_tree import solve


def main():
    p=argparse.ArgumentParser();p.add_argument('mesh',nargs='?',default='cliff');p.add_argument('--source',type=int,default=1)
    p.add_argument('--timeout',type=float,default=20);p.add_argument('--no-clip',action='store_true');args=p.parse_args()
    mesh_path=Path(args.mesh)
    if not mesh_path.exists():mesh_path=ROOT/'data/processed/meshes'/(args.mesh.removesuffix('.off')+'.off')
    paths,stats=solve(read_off(mesh_path),args.source,timeout=args.timeout,clipping=not args.no_clip)
    out=ROOT/'generated';out.mkdir(exist_ok=True)
    stem=f'{mesh_path.stem}_s{args.source}'
    with (out/(stem+'.paths.json')).open('w') as f:
        json.dump({'mesh':mesh_path.stem,'source':args.source,
                   'coordinate_system':'model units; 17 significant digits',
                   'paths':paths},f,indent=2)
        f.write('\n')
    (out/(stem+'_stats.json')).write_text(json.dumps(stats,indent=2)+'\n')
    print('Saved',out/(stem+'.paths.json'));print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
