"""Hybrid kinematic demo (ApexNav Habitat GPU + host MuJoCo FK/robot viz).

Why hybrid: dedicated `vln-rangercr10:bullet` currently fails Windowless EGL
(`unable to find CUDA device 0 among 1 EGL devices`) after swapping to
`headless_bullet`. Baseline `vln-apexnav` (nobullet) still renders HM3D correctly.
URDF articulated mesh therefore cannot be shown *inside* Habitat this round;
robot mesh frames come from MuJoCo offscreen render. EE RGB-D still comes from
Habitat with camera pose driven by MuJoCo FK of `d455_depth_optical_frame`.

Control mode: **kinematic_state_set** (explicit). Not swerve whole-body dynamics.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .constants import (
    ARM_DEFAULT,
    ARM_JOINT_NAMES,
    CAMERA_LINK,
    DEFAULT_OUT_DIR,
    DEFAULT_SCENE,
    LOCOMANIP_COMMIT,
    LOCOMANIP_REPO,
    MODE_KINEMATIC,
    TCP_BODY,
)
from .traj_utils import preset_trajectory, save_depth_mm

# MuJoCo is z-up; Habitat is y-up
C_M2H = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=np.float64)


def _mat_to_wxyz(R: np.ndarray) -> List[float]:
    # robust quat from rotation matrix
    tr = float(np.trace(R))
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    else:
        if R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
    q = np.array([w, x, y, z], dtype=np.float64)
    q /= np.linalg.norm(q) + 1e-12
    return q.tolist()


class MujocoRangerFK:
    def __init__(self, xml: Path):
        import mujoco

        self.mj = mujoco
        self.m = mujoco.MjModel.from_xml_path(str(xml))
        self.d = mujoco.MjData(self.m)
        self.cam_id = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, CAMERA_LINK)
        self.tcp_id = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, TCP_BODY)
        self.arm_qadr = []
        for name in ARM_JOINT_NAMES:
            jid = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_JOINT, name)
            self.arm_qadr.append(int(self.m.jnt_qposadr[jid]))
        # offscreen renderer
        self.renderer = mujoco.Renderer(self.m, height=480, width=640)

    def set_state(
        self,
        x: float,
        y_plane: float,
        yaw: float,
        arm_q: List[float],
        z_up: float = 0.4071,
    ):
        """x,y_plane are ground-plane coords matching Habitat x,z; yaw about vertical.

        Default ``z_up=0.4071`` matches MuJoCo ``home`` keyframe base height (wheel contact).
        """
        self.mj.mj_resetData(self.m, self.d)
        # MuJoCo freejoint: pos xyz (z-up), quat wxyz
        self.d.qpos[0:3] = [x, y_plane, z_up]
        cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
        self.d.qpos[3:7] = [cy, 0.0, 0.0, sy]
        for adr, q in zip(self.arm_qadr, arm_q):
            self.d.qpos[adr] = float(q)
        self.mj.mj_forward(self.m, self.d)

    def camera_habitat(self):
        p = self.d.xpos[self.cam_id].copy()
        R = self.d.xmat[self.cam_id].reshape(3, 3).copy()
        ph = C_M2H @ p
        Rh = C_M2H @ R @ C_M2H.T
        # Habitat camera looks along -Z; optical +Z → rotate 180° about X in camera frame
        Rx = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)
        Rh_cam = Rh @ Rx
        return ph.tolist(), _mat_to_wxyz(Rh_cam)

    def tcp_habitat(self):
        p = C_M2H @ self.d.xpos[self.tcp_id]
        return p.tolist()

    def render_robot(self) -> np.ndarray:
        # follow camera looking at base
        self.renderer.update_scene(self.d, camera=-1)
        # set free camera
        scn = self.renderer.scene
        # simpler: use built-in track
        self.mj.mj_forward(self.m, self.d)
        # look at robot from side
        cam = self.mj.MjvCamera()
        cam.type = self.mj.mjtCamera.mjCAMERA_FREE
        cam.lookat[:] = self.d.xpos[1] if False else [self.d.qpos[0], self.d.qpos[1], 0.6]
        cam.distance = 3.2
        cam.azimuth = 140
        cam.elevation = -20
        self.renderer.update_scene(self.d, camera=cam)
        return self.renderer.render()


def run_mujoco_pass(out: Path, frames) -> List[dict]:
    xml = Path(LOCOMANIP_REPO) / "mujoco/robots/ranger_cr10/scene.xml"
    fk = MujocoRangerFK(xml)
    robot_dir = out / "robot_mujoco"
    robot_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for i, fr in enumerate(frames):
        fk.set_state(fr["x"], fr["z"], fr["yaw"], fr["arm"])
        pos, wxyz = fk.camera_habitat()
        tcp = fk.tcp_habitat()
        img = fk.render_robot()
        Image.fromarray(img).save(robot_dir / f"frame_{i:04d}.png")
        records.append(
            {
                "i": i,
                "base": fr,
                "camera_pos_habitat": pos,
                "camera_wxyz_habitat": wxyz,
                "tcp_pos_habitat": tcp,
                "arm": fr["arm"],
            }
        )
    (out / "fk_poses.json").write_text(json.dumps(records, indent=2))
    return records


def run_habitat_pass(out: Path, records: List[dict], scene: str, gpu: int) -> dict:
    import magnum as mn
    import habitat_sim

    ee_dir = out / "rgb_ee"
    depth_dir = out / "depth_ee"
    third_dir = out / "third_habitat"
    for d in (ee_dir, depth_dir, third_dir):
        d.mkdir(parents=True, exist_ok=True)

    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = scene
    backend.enable_physics = False
    backend.gpu_device_id = gpu

    def make(uuid, depth=False, res=(480, 640), hfov=79.0):
        s = habitat_sim.CameraSensorSpec()
        s.uuid = uuid
        s.sensor_type = habitat_sim.SensorType.DEPTH if depth else habitat_sim.SensorType.COLOR
        s.resolution = list(res)
        s.hfov = float(hfov)
        return s

    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [
        make("ee_rgb"),
        make("ee_depth", depth=True),
        make("third_rgb", res=(480, 640), hfov=90.0),
    ]
    sim = habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent_cfg]))
    agent = sim.get_agent(0)

    for rec in records:
        st = habitat_sim.AgentState()
        st.position = mn.Vector3(*rec["camera_pos_habitat"])
        w, x, y, z = rec["camera_wxyz_habitat"]
        st.rotation = mn.Quaternion(mn.Vector3(x, y, z), w)
        agent.set_state(st, infer_sensor_states=True)
        # crude third: elevate behind
        # (agent sensors share root; third will be near EE — acceptable for stub)
        obs = sim.get_sensor_observations()
        i = rec["i"]
        Image.fromarray(obs["ee_rgb"][..., :3]).save(ee_dir / f"frame_{i:04d}.png")
        save_depth_mm(depth_dir / f"frame_{i:04d}.png", obs["ee_depth"])
        Image.fromarray(obs["third_rgb"][..., :3]).save(third_dir / f"frame_{i:04d}.png")
        d = obs["ee_depth"]
        rec["depth_stats"] = {
            "min": float(np.min(d)),
            "max": float(np.max(d)),
            "mean": float(np.mean(d)),
        }

    meta = {
        "habitat_sim": habitat_sim.__version__,
        "built_with_bullet": bool(habitat_sim.built_with_bullet),
        "scene": scene,
    }
    sim.close()
    return meta


def make_collage(out: Path, n: int) -> None:
    coll = out / "collage"
    coll.mkdir(exist_ok=True)
    for i in range(n):
        panels = []
        for name in ("rgb_ee", "depth_ee", "robot_mujoco"):
            p = out / name / f"frame_{i:04d}.png"
            if not p.exists():
                continue
            im = Image.open(p).convert("RGB").resize((320, 240))
            if name == "depth_ee":
                # visualize uint16 depth roughly
                arr = np.array(Image.open(p))
                if arr.dtype == np.uint16:
                    vis = (np.clip(arr.astype(np.float32) / 5000.0, 0, 1) * 255).astype(np.uint8)
                    im = Image.fromarray(vis).convert("RGB").resize((320, 240))
            panels.append(im)
        if not panels:
            continue
        w = sum(p.width for p in panels)
        canvas = Image.new("RGB", (w, panels[0].height + 24), (20, 20, 20))
        x = 0
        for p in panels:
            canvas.paste(p, (x, 24))
            x += p.width
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 4), f"frame {i} | kinematic | Habitat EE + MuJoCo robot", fill=(240, 240, 240))
        canvas.save(coll / f"frame_{i:04d}.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "hybrid_kinematic_demo"))
    ap.add_argument("--scene", default=DEFAULT_SCENE)
    ap.add_argument("--num_frames", type=int, default=24)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--habitat_only_poses", default="", help="if set, only Habitat pass using poses json")
    ap.add_argument("--mujoco_only", action="store_true")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if args.habitat_only_poses:
        records = json.loads(Path(args.habitat_only_poses).read_text())
        hab = run_habitat_pass(out, records, args.scene, args.gpu)
        (out / "fk_poses.json").write_text(json.dumps(records, indent=2))
        summary = {
            "status": "ok_habitat_pass",
            "control_mode": MODE_KINEMATIC,
            "habitat": hab,
            "elapsed_sec": time.time() - t0,
            "out_dir": str(out),
        }
        (out / "summary_habitat.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return

    frames = preset_trajectory(args.num_frames)
    records = run_mujoco_pass(out, frames)
    if args.mujoco_only:
        summary = {
            "status": "ok_mujoco_pass",
            "control_mode": MODE_KINEMATIC,
            "locomanip_commit": LOCOMANIP_COMMIT,
            "n": len(records),
            "elapsed_sec": time.time() - t0,
            "out_dir": str(out),
            "poses": str(out / "fk_poses.json"),
        }
        (out / "summary_mujoco.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return

    # full path assumes habitat_sim importable in this process
    hab = run_habitat_pass(out, records, args.scene, args.gpu)
    make_collage(out, len(records))
    summary = {
        "status": "ok",
        "control_mode": MODE_KINEMATIC,
        "note": (
            "Robot mesh from MuJoCo; EE RGB-D from Habitat HM3D with MuJoCo FK camera. "
            "NOT whole-body dynamics. Bullet EGL path deferred."
        ),
        "robot_mesh_in_habitat": False,
        "locomanip_commit": LOCOMANIP_COMMIT,
        "habitat": hab,
        "num_frames": len(records),
        "elapsed_sec": time.time() - t0,
        "out_dir": str(out),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
