"""Kinematic Ranger+CR10 demo in Habitat HM3D (independent of VLN baselines).

Control mode: **kinematic_state_set** — base SE(2) and arm joints are written directly;
this is NOT whole-body dynamics / swerve physics. Collision contacts are queried when
Bullet is available, but contacts under kinematic teleport are diagnostic only.

Outputs (to --out_dir):
  - rgb_ee/ frame_XXXX.png
  - depth_ee/ frame_XXXX.png (uint16 mm)
  - third/ frame_XXXX.png
  - traj.jsonl (pose, joints, camera T, contact count)
  - summary.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import magnum as mn
import numpy as np
from PIL import Image

import habitat_sim

from .constants import (
    ARM_DEFAULT,
    ARM_JOINT_NAMES,
    CAMERA_LINK,
    DEFAULT_OUT_DIR,
    DEFAULT_SCENE,
    EE_RGB_HFOV_DEG,
    EE_RGB_RES,
    LOCOMANIP_COMMIT,
    MODE_COLLISION_QUERY,
    MODE_KINEMATIC,
    THIRD_RGB_RES,
    URDF_HABITAT,
)
from .traj_utils import preset_trajectory, save_depth_mm

# MuJoCo home base height (wheel contact); Habitat y-up uses same magnitude for base_link.
DEFAULT_BASE_Y = 0.4071


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _mat4_to_list(m: mn.Matrix4) -> List[float]:
    out = []
    for c in range(4):
        for r in range(4):
            out.append(float(m[c][r]))
    return out


def _mn_quat_to_xyzw(q: mn.Quaternion) -> np.ndarray:
    # magnum: Quaternion(vector, scalar)
    return np.array([q.vector.x, q.vector.y, q.vector.z, q.scalar], dtype=np.float32)


class RangerCr10KinematicEnv:
    """Load HM3D + URDF; drive by kinematic state sets; RGB-D from EE optical frame."""

    def __init__(
        self,
        scene: str = DEFAULT_SCENE,
        urdf: str = URDF_HABITAT,
        enable_physics: bool = True,
        gpu_device_id: int = 0,
    ):
        if not habitat_sim.built_with_bullet and enable_physics:
            raise RuntimeError(
                "habitat-sim built_with_bullet=False; need vln-rangercr10:bullet "
                "(and restored /usr/share/glvnd/egl_vendor.d/10_nvidia.json)."
            )
        self.scene = scene
        self.urdf = urdf
        self.mode = MODE_KINEMATIC
        self.collision_mode = MODE_COLLISION_QUERY

        backend = habitat_sim.SimulatorConfiguration()
        backend.scene_id = scene
        backend.enable_physics = bool(enable_physics)
        backend.gpu_device_id = gpu_device_id
        backend.allow_sliding = True

        def make_cam(uuid: str, depth: bool = False, res=EE_RGB_RES, hfov=EE_RGB_HFOV_DEG):
            s = habitat_sim.CameraSensorSpec()
            s.uuid = uuid
            s.sensor_type = (
                habitat_sim.SensorType.DEPTH if depth else habitat_sim.SensorType.COLOR
            )
            s.resolution = list(res)
            s.hfov = float(hfov)
            s.position = [0.0, 0.0, 0.0]
            s.orientation = [0.0, 0.0, 0.0]
            return s

        agent_cfg = habitat_sim.agent.AgentConfiguration()
        agent_cfg.sensor_specifications = [
            make_cam("ee_rgb"),
            make_cam("ee_depth", depth=True),
            make_cam("third_rgb", res=THIRD_RGB_RES, hfov=90.0),
        ]
        agent_cfg.height = 0.01
        agent_cfg.radius = 0.01

        self.sim = habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent_cfg]))
        self.agent = self.sim.get_agent(0)

        aom = self.sim.get_articulated_object_manager()
        self.ao = aom.add_articulated_object_from_urdf(
            urdf, fixed_base=False, maintain_link_order=True
        )
        self.ao.motion_type = habitat_sim.physics.MotionType.KINEMATIC

        self.link_ids: Dict[str, int] = {}
        for lid in self.ao.get_link_ids():
            self.link_ids[self.ao.get_link_name(lid)] = int(lid)
        self.link_ids[self.ao.get_link_name(-1)] = -1
        if CAMERA_LINK not in self.link_ids:
            raise RuntimeError(
                f"Camera link {CAMERA_LINK} missing; have={sorted(self.link_ids)[:25]}"
            )

        self.joint_pos_index: Dict[str, int] = {}
        for lid in self.ao.get_link_ids():
            jn = self.ao.get_link_joint_name(lid)
            npos = self.ao.get_link_num_joint_pos(lid)
            if jn and npos > 0:
                self.joint_pos_index[jn] = int(self.ao.get_link_joint_pos_offset(lid))
        for jn in ARM_JOINT_NAMES:
            if jn not in self.joint_pos_index:
                raise RuntimeError(f"missing arm joint mapping for {jn}")

        self.arm_q = np.array(ARM_DEFAULT, dtype=np.float64)
        self.base_xyz = np.array([1.0, DEFAULT_BASE_Y, 1.0], dtype=np.float64)
        self.base_yaw = 0.0
        self._apply_state()

    def _base_matrix(self) -> mn.Matrix4:
        rot = mn.Quaternion.rotation(mn.Rad(self.base_yaw), mn.Vector3(0.0, 1.0, 0.0))
        return mn.Matrix4.from_(rot.to_matrix(), mn.Vector3(*self.base_xyz))

    def _apply_state(self) -> None:
        jp = np.array(self.ao.joint_positions, dtype=np.float64)
        for i, jn in enumerate(ARM_JOINT_NAMES):
            jp[self.joint_pos_index[jn]] = float(self.arm_q[i])
        self.ao.joint_positions = jp.tolist()
        self.ao.transformation = self._base_matrix()
        # kinematic write does not auto-step; nudge collision world
        self.sim.perform_discrete_collision_detection()

    def set_base_pose(self, x: float, z: float, yaw: float, y: float = DEFAULT_BASE_Y) -> None:
        self.base_xyz[:] = (x, y, z)
        self.base_yaw = float(yaw)
        self._apply_state()

    def set_arm_joints(self, q: Sequence[float]) -> None:
        q = np.asarray(q, dtype=np.float64)
        assert q.shape == (6,)
        lows, highs = self.ao.joint_position_limits
        for i, jn in enumerate(ARM_JOINT_NAMES):
            idx = self.joint_pos_index[jn]
            lo, hi = float(lows[idx]), float(highs[idx])
            if np.isfinite(lo) and np.isfinite(hi):
                q[i] = float(np.clip(q[i], lo, hi))
        self.arm_q = q.copy()
        self._apply_state()

    def camera_world_matrix(self) -> mn.Matrix4:
        lid = self.link_ids[CAMERA_LINK]
        return mn.Matrix4(self.ao.get_link_scene_node(lid).absolute_transformation())

    def _set_agent_pose(self, T: mn.Matrix4) -> None:
        st = habitat_sim.AgentState()
        st.position = np.array(
            [T.translation.x, T.translation.y, T.translation.z], dtype=np.float32
        )
        st.rotation = _mn_quat_to_xyzw(mn.Quaternion.from_matrix(mn.Matrix3x3(T.rotation())))
        self.agent.set_state(st, infer_sensor_states=True)

    def sync_agent_sensors(self) -> None:
        """Place EE sensors at optical frame; third cam elevated behind base."""
        cam_T = self.camera_world_matrix()
        # OpenCV optical (+Z fwd, Y down) -> Habitat camera (-Z fwd, Y up): 180° about X
        fix = mn.Matrix4.rotation_x(mn.Rad(math.pi))
        self._ee_T = cam_T @ fix

        fwd = mn.Vector3(math.sin(self.base_yaw), 0.0, math.cos(self.base_yaw))
        base = mn.Vector3(*self.base_xyz)
        eye = base - fwd * 2.8 + mn.Vector3(0.0, 1.6, 0.0)
        target = base + mn.Vector3(0.0, 0.6, 0.0)
        self._third_T = mn.Matrix4.look_at(eye, target, mn.Vector3(0.0, 1.0, 0.0))

    def observe(self) -> Dict[str, np.ndarray]:
        self.sync_agent_sensors()
        # Capture EE first
        self._set_agent_pose(self._ee_T)
        obs_ee = self.sim.get_sensor_observations()
        rgb = obs_ee["ee_rgb"]
        depth = obs_ee["ee_depth"]
        # Then third (same agent sensors; we only keep third_rgb channel after reposition)
        self._set_agent_pose(self._third_T)
        obs_third = self.sim.get_sensor_observations()
        return {
            "ee_rgb": rgb,
            "ee_depth": depth,
            "third_rgb": obs_third["third_rgb"],
        }

    def contact_count(self) -> int:
        return len(self.sim.get_physics_contact_points())

    def joint_limits_report(self) -> Dict[str, dict]:
        out = {}
        lows, highs = self.ao.joint_position_limits
        jp = self.ao.joint_positions
        for jn in ARM_JOINT_NAMES:
            i = self.joint_pos_index[jn]
            q = float(jp[i])
            lo, hi = float(lows[i]), float(highs[i])
            within = True
            if np.isfinite(lo) and np.isfinite(hi):
                within = bool(lo - 1e-5 <= q <= hi + 1e-5)
            out[jn] = {"q": q, "lower": lo, "upper": hi, "within": within}
        return out

    def close(self) -> None:
        try:
            self.sim.close()
        except Exception:
            # habitat-sim 0.3.1 often SIGABRT/heap noise on close; ignore after work done
            pass


def run_demo(args: argparse.Namespace) -> dict:
    out = _ensure_dir(Path(args.out_dir))
    ee_rgb_dir = _ensure_dir(out / "rgb_ee")
    ee_depth_dir = _ensure_dir(out / "depth_ee")
    third_dir = _ensure_dir(out / "third")
    traj_path = out / "traj.jsonl"
    err_path = out / "error.log"

    t0 = time.time()
    env = None
    records = []
    status = "ok"
    error = None
    try:
        env = RangerCr10KinematicEnv(scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu)
        frames = preset_trajectory(args.num_frames)
        with traj_path.open("w") as f:
            for i, fr in enumerate(frames):
                env.set_base_pose(fr["x"], fr["z"], fr["yaw"])
                env.set_arm_joints(fr["arm"])
                obs = env.observe()
                rgb = obs["ee_rgb"][..., :3]
                depth = obs["ee_depth"]
                third = obs["third_rgb"][..., :3]
                Image.fromarray(rgb).save(ee_rgb_dir / f"frame_{i:04d}.png")
                save_depth_mm(ee_depth_dir / f"frame_{i:04d}.png", depth)
                Image.fromarray(third).save(third_dir / f"frame_{i:04d}.png")
                cam_T = env.camera_world_matrix()
                rec = {
                    "i": i,
                    "control_mode": env.mode,
                    "base": {
                        "x": fr["x"],
                        "y": float(env.base_xyz[1]),
                        "z": fr["z"],
                        "yaw": fr["yaw"],
                    },
                    "arm": fr["arm"],
                    "joint_limits": env.joint_limits_report(),
                    "camera_link": CAMERA_LINK,
                    "camera_T_flat16": _mat4_to_list(cam_T),
                    "contact_count": env.contact_count(),
                    "collision_semantics": env.collision_mode,
                    "depth_stats": {
                        "min": float(np.min(depth)),
                        "max": float(np.max(depth)),
                        "mean": float(np.mean(depth)),
                    },
                }
                f.write(json.dumps(rec) + "\n")
                records.append(rec)
    except Exception as e:
        status = "failed"
        error = f"{type(e).__name__}: {e}"
        err_path.write_text(traceback.format_exc())
        raise
    finally:
        if env is not None:
            env.close()

    elapsed = time.time() - t0
    summary = {
        "status": status,
        "control_mode": MODE_KINEMATIC,
        "note": "Native Habitat URDF kinematic state set; NOT whole-body swerve dynamics.",
        "robot_mesh_in_habitat": True,
        "locomanip_commit": LOCOMANIP_COMMIT,
        "habitat_sim": habitat_sim.__version__,
        "built_with_bullet": bool(habitat_sim.built_with_bullet),
        "scene": args.scene,
        "urdf": args.urdf,
        "num_frames": len(records),
        "elapsed_sec": elapsed,
        "out_dir": str(out),
        "n_links": len(env.link_ids) if env is not None else None,
        "final_contacts": records[-1]["contact_count"] if records else None,
        "arm_within_limits_final": all(
            v["within"] for v in records[-1]["joint_limits"].values()
        )
        if records
        else None,
        "error": error,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--urdf", default=URDF_HABITAT)
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "kinematic_demo"))
    p.add_argument("--num_frames", type=int, default=24)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args(argv)
    try:
        summary = run_demo(args)
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("status") == "ok" else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
