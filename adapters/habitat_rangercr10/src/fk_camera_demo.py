"""Fallback EE-camera demo without URDF mesh (no Bullet required).

Uses Habitat HM3D for RGB-D and MuJoCo FK (via LocoManip MJCF) only to obtain
`d455_depth_optical_frame` world pose. Robot mesh is NOT drawn in Habitat.

Control mode remains **kinematic** (preset base+arm). Marked clearly in summary.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import magnum as mn
import numpy as np
from PIL import Image

import habitat_sim

from .constants import (
    ARM_DEFAULT,
    CAMERA_LINK,
    DEFAULT_OUT_DIR,
    DEFAULT_SCENE,
    EE_RGB_HFOV_DEG,
    EE_RGB_RES,
    LOCOMANIP_COMMIT,
    LOCOMANIP_REPO,
    MODE_KINEMATIC,
    THIRD_RGB_RES,
)
from .traj_utils import preset_trajectory, save_depth_mm


def _mujoco_fk_camera(arm_q, base_x, base_z, base_yaw, y=0.0):
    """Return (position xyz y-up, quaternion wxyz) of CAMERA_LINK in Habitat y-up."""
    import mujoco

    xml = Path(LOCOMANIP_REPO) / "mujoco/robots/ranger_cr10/scene.xml"
    m = mujoco.MjModel.from_xml_path(str(xml))
    d = mujoco.MjData(m)
    mujoco.mj_resetData(m, d)
    # free joint: qpos[0:3] pos, qpos[3:7] quat wxyz (MuJoCo)
    d.qpos[0:3] = [base_x, base_z, y]  # MuJoCo scene is z-up: x,y,z with z up
    # convert Habitat yaw about Y to MuJoCo yaw about Z
    cy, sy = math.cos(base_yaw * 0.5), math.sin(base_yaw * 0.5)
    d.qpos[3:7] = [cy, 0.0, 0.0, sy]
    # arm joints
    for i, name in enumerate([f"cr10_joint{j}" for j in range(1, 7)]):
        jid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name)
        qadr = m.jnt_qposadr[jid]
        d.qpos[qadr] = float(arm_q[i])
    mujoco.mj_forward(m, d)
    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, CAMERA_LINK)
    # MuJoCo body xpos (z-up) -> Habitat (y-up): (x, z, y)
    p = d.xpos[bid]
    # body xmat 3x3 row-major
    R = d.xmat[bid].reshape(3, 3)
    # convert pose to habitat y-up
    # M_h = C * M_m * C^{-1} with C: (x,y,z)_m -> (x,z,y)_h
    C = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=np.float64)
    Rh = C @ R @ C.T
    ph = C @ p
    # matrix to quat wxyz
    from scipy.spatial.transform import Rotation

    qwxyz = Rotation.from_matrix(Rh).as_quat()  # xyzw
    wxyz = [float(qwxyz[3]), float(qwxyz[0]), float(qwxyz[1]), float(qwxyz[2])]
    return ph.tolist(), wxyz


def run(args: argparse.Namespace) -> dict:
    out = Path(args.out_dir)
    for sub in ("rgb_ee", "depth_ee", "third"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = args.scene
    backend.enable_physics = False
    backend.gpu_device_id = args.gpu

    def cam(uuid, res, hfov):
        s = habitat_sim.CameraSensorSpec()
        s.uuid = uuid
        s.sensor_type = habitat_sim.SensorType.COLOR if "rgb" in uuid else habitat_sim.SensorType.DEPTH
        if "depth" in uuid:
            s.sensor_type = habitat_sim.SensorType.DEPTH
        s.resolution = list(res)
        s.hfov = float(hfov)
        return s

    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [
        cam("ee_rgb", EE_RGB_RES, EE_RGB_HFOV_DEG),
        cam("ee_depth", EE_RGB_RES, EE_RGB_HFOV_DEG),
        cam("third_rgb", THIRD_RGB_RES, 90.0),
    ]
    sim = habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent_cfg]))
    agent = sim.get_agent(0)

    frames = preset_trajectory(args.num_frames)
    t0 = time.time()
    records = []
    for i, fr in enumerate(frames):
        try:
            pos, wxyz = _mujoco_fk_camera(fr["arm"], fr["x"], fr["z"], fr["yaw"])
        except Exception as e:
            # if mujoco unavailable inside container, use upright base camera proxy
            pos = [fr["x"], 1.2, fr["z"]]
            wxyz = [1.0, 0.0, 0.0, 0.0]
            fk_err = str(e)
        else:
            fk_err = None
        st = habitat_sim.AgentState()
        st.position = mn.Vector3(*pos)
        st.rotation = mn.Quaternion(mn.Vector3(wxyz[1], wxyz[2], wxyz[3]), wxyz[0])
        agent.set_state(st, infer_sensor_states=True)
        obs = sim.get_sensor_observations()
        Image.fromarray(obs["ee_rgb"][..., :3]).save(out / "rgb_ee" / f"frame_{i:04d}.png")
        save_depth_mm(out / "depth_ee" / f"frame_{i:04d}.png", obs["ee_depth"])
        Image.fromarray(obs["third_rgb"][..., :3]).save(out / "third" / f"frame_{i:04d}.png")
        records.append({"i": i, "pos": pos, "wxyz": wxyz, "fk_err": fk_err, "arm": fr["arm"]})

    elapsed = time.time() - t0
    summary = {
        "status": "ok_fallback_fk_camera",
        "control_mode": MODE_KINEMATIC,
        "robot_mesh_in_habitat": False,
        "note": "EE pose from MuJoCo FK; Habitat renders scene only. Not whole-body dynamics.",
        "locomanip_commit": LOCOMANIP_COMMIT,
        "habitat_sim": habitat_sim.__version__,
        "built_with_bullet": bool(habitat_sim.built_with_bullet),
        "num_frames": len(frames),
        "elapsed_sec": elapsed,
        "out_dir": str(out),
        "fk_errors": sum(1 for r in records if r["fk_err"]),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "traj.json").write_text(json.dumps(records, indent=2))
    sim.close()
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "fk_camera_demo"))
    p.add_argument("--num_frames", type=int, default=20)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args()
    # allow mujoco from host env if container lacks it: path injection
    print(json.dumps(run(args), indent=2))


if __name__ == "__main__":
    main()
