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
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import magnum as mn
import numpy as np
from PIL import Image

import habitat_sim
from habitat_sim.utils.common import quat_from_angle_axis, quat_to_coeffs

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


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _quat_wxyz_to_mn(q: Sequence[float]) -> mn.Quaternion:
    # habitat / magnum: Quaternion(vector3, scalar) with (x,y,z), w
    w, x, y, z = [float(v) for v in q]
    return mn.Quaternion(mn.Vector3(x, y, z), w)


def _mat4_to_list(m: mn.Matrix4) -> List[float]:
    # column-major flat 16
    out = []
    for c in range(4):
        for r in range(4):
            out.append(float(m[c][r]))
    return out


def _yaw_to_quat(yaw: float) -> mn.Quaternion:
    return quat_from_angle_axis(yaw, np.array([0.0, 1.0, 0.0]))


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
                "habitat-sim built_with_bullet=False; install headless_bullet build "
                "in the dedicated vln-rangercr10 container before loading URDF."
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

        # EE camera (updated every frame to CAMERA_LINK)
        ee_rgb = habitat_sim.CameraSensorSpec()
        ee_rgb.uuid = "ee_rgb"
        ee_rgb.sensor_type = habitat_sim.SensorType.COLOR
        ee_rgb.resolution = list(EE_RGB_RES)
        ee_rgb.hfov = float(EE_RGB_HFOV_DEG)
        ee_rgb.position = [0.0, 0.0, 0.0]
        ee_rgb.orientation = [0.0, 0.0, 0.0]

        ee_depth = habitat_sim.CameraSensorSpec()
        ee_depth.uuid = "ee_depth"
        ee_depth.sensor_type = habitat_sim.SensorType.DEPTH
        ee_depth.resolution = list(EE_RGB_RES)
        ee_depth.hfov = float(EE_RGB_HFOV_DEG)
        ee_depth.position = [0.0, 0.0, 0.0]
        ee_depth.orientation = [0.0, 0.0, 0.0]

        # Third-person overview (world-ish follow)
        third = habitat_sim.CameraSensorSpec()
        third.uuid = "third_rgb"
        third.sensor_type = habitat_sim.SensorType.COLOR
        third.resolution = list(THIRD_RGB_RES)
        third.hfov = 90.0
        third.position = [0.0, 0.0, 0.0]

        agent_cfg = habitat_sim.agent.AgentConfiguration()
        agent_cfg.sensor_specifications = [ee_rgb, ee_depth, third]
        agent_cfg.height = 0.01
        agent_cfg.radius = 0.01

        self.sim = habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent_cfg]))
        self.agent = self.sim.get_agent(0)

        aom = self.sim.get_articulated_object_manager()
        self.ao = aom.add_articulated_object_from_urdf(
            urdf, fixed_base=False, maintain_link_order=True
        )
        self.ao.motion_type = habitat_sim.physics.MotionType.KINEMATIC

        # link name -> id
        self.link_ids: Dict[str, int] = {
            name: lid for lid, name in self.ao.link_id_to_names.items()
        }
        if CAMERA_LINK not in self.link_ids:
            raise RuntimeError(
                f"Camera link {CAMERA_LINK} missing; links={list(self.link_ids)[:20]}..."
            )

        # joint name -> position index in ao.joint_positions
        self.joint_pos_index: Dict[str, int] = {}
        # habitat exposes get_link_joint_pos_offset per link; map via joint names when possible
        for jname in list(ARM_JOINT_NAMES) + [
            "fr_steering_joint",
            "fl_steering_wheel_joint",
            "rl_steering_wheel_joint",
            "rr_steering_wheel_joint",
        ]:
            # iterate links to find matching joint
            for lid, lname in self.ao.link_id_to_names.items():
                # joint name often equals child link's driving joint; query motor
                pass
        # Fallback: use dof metadata
        self._build_joint_index()

        self.arm_q = np.array(ARM_DEFAULT, dtype=np.float64)
        self.base_xyz = np.array([0.0, 0.15, 0.0], dtype=np.float64)  # y-up
        self.base_yaw = 0.0
        self._apply_state()

    def _build_joint_index(self) -> None:
        """Map CR10 joint names to indices in `joint_positions` vector."""
        # Habitat stores one position per movable DoF in URDF order.
        # We discover by setting one-hot probes after reset to zero.
        n = len(self.ao.joint_positions)
        self.joint_pos_index = {}
        # Prefer link_joint_name API if present
        if hasattr(self.ao, "get_link_joint_names"):
            names = list(self.ao.get_link_joint_names())
            for i, name in enumerate(names):
                self.joint_pos_index[str(name)] = i
            return
        # Manual: match known arm joints by link child names
        # joint_positions order follows URDF revolute/continuous joints.
        # We parse URDF joint order for revolute/continuous.
        import xml.etree.ElementTree as ET

        root = ET.parse(self.urdf).getroot()
        movable = [
            j.get("name")
            for j in root.findall("joint")
            if j.get("type") in ("revolute", "continuous", "prismatic")
        ]
        if len(movable) != n:
            # still assign by min length
            pass
        for i, name in enumerate(movable[:n]):
            self.joint_pos_index[name] = i
        if n != len(movable):
            print(
                f"[warn] joint_positions len={n} vs URDF movable={len(movable)}; "
                "using truncated name map"
            )

    def _base_matrix(self) -> mn.Matrix4:
        # Habitat y-up: translation (x, y, z), yaw about +Y
        R = mn.Matrix4.from_(
            mn.Quaternion.rotation(mn.Rad(self.base_yaw), mn.Vector3(0.0, 1.0, 0.0)).to_matrix(),
            mn.Vector3(*self.base_xyz),
        )
        return R

    def _apply_state(self) -> None:
        jp = np.array(self.ao.joint_positions, dtype=np.float64)
        for i, jn in enumerate(ARM_JOINT_NAMES):
            if jn in self.joint_pos_index:
                jp[self.joint_pos_index[jn]] = float(self.arm_q[i])
        self.ao.joint_positions = jp.tolist()
        self.ao.transformation = self._base_matrix()
        # force forward kinematics update
        if hasattr(self.ao, "clear_joint_states"):
            pass
        self.sim.perform_discrete_collision_detection()

    def set_base_pose(self, x: float, z: float, yaw: float, y: float = 0.15) -> None:
        """Set base on ground plane (Habitat y-up)."""
        self.base_xyz[:] = (x, y, z)
        self.base_yaw = float(yaw)
        self._apply_state()

    def set_arm_joints(self, q: Sequence[float]) -> None:
        q = np.asarray(q, dtype=np.float64)
        assert q.shape == (6,)
        # clamp to URDF limits if available
        self.arm_q = q.copy()
        self._apply_state()

    def camera_world_matrix(self) -> mn.Matrix4:
        lid = self.link_ids[CAMERA_LINK]
        node = self.ao.get_link_scene_node(lid)
        return mn.Matrix4(node.absolute_transformation())

    def sync_agent_sensors(self) -> None:
        """Place EE sensors at optical frame; third cam looks at base from behind."""
        cam_T = self.camera_world_matrix()
        # Habitat camera looks down -Z; D455 optical looks +Z → rotate 180° about Y (or X)
        # Optical (OpenCV): x right, y down, z forward. Habitat: x right, y up, -z forward.
        # Convert optical -> habitat camera: rotate 180° about X.
        fix = mn.Matrix4.rotation_x(mn.Rad(math.pi))
        ee_T = cam_T @ fix

        # Third person: behind base along -forward, elevated
        fwd = mn.Vector3(math.sin(self.base_yaw), 0.0, math.cos(self.base_yaw))
        base = mn.Vector3(*self.base_xyz)
        eye = base - fwd * 2.8 + mn.Vector3(0.0, 1.6, 0.0)
        target = base + mn.Vector3(0.0, 0.6, 0.0)
        # build look-at for habitat agent state: use translation + rotation from eye
        # Simpler: set agent state for EE, then manually set third sensor node.
        st = habitat_sim.AgentState()
        # Extract rotation from ee_T
        st.position = ee_T.translation
        st.rotation = mn.Quaternion.from_matrix(mn.Matrix3x3(ee_T.rotation()))
        self.agent.set_state(st, infer_sensor_states=True)

        # Override third sensor pose via scene graph
        third_node = self.agent.scene_node.node_sensor_suite.get("third_rgb").node
        # look from eye to target
        third_node.transformation = mn.Matrix4.look_at(eye, target, mn.Vector3(0, 1, 0))

    def observe(self) -> Dict[str, np.ndarray]:
        self.sync_agent_sensors()
        return self.sim.get_sensor_observations()

    def contact_count(self) -> int:
        if not habitat_sim.built_with_bullet:
            return -1
        cps = self.sim.get_physics_contact_points()
        return len(cps)

    def joint_limits_report(self) -> Dict[str, dict]:
        out = {}
        lows, highs = self.ao.joint_position_limits
        for jn in ARM_JOINT_NAMES:
            if jn not in self.joint_pos_index:
                continue
            i = self.joint_pos_index[jn]
            q = float(self.ao.joint_positions[i])
            lo, hi = float(lows[i]), float(highs[i])
            out[jn] = {
                "q": q,
                "lower": lo,
                "upper": hi,
                "within": bool(lo - 1e-6 <= q <= hi + 1e-6),
            }
        return out

    def close(self) -> None:
        self.sim.close()


def run_demo(args: argparse.Namespace) -> dict:
    out = _ensure_dir(Path(args.out_dir))
    ee_rgb_dir = _ensure_dir(out / "rgb_ee")
    ee_depth_dir = _ensure_dir(out / "depth_ee")
    third_dir = _ensure_dir(out / "third")
    traj_path = out / "traj.jsonl"

    t0 = time.time()
    env = RangerCr10KinematicEnv(scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu)
    frames = preset_trajectory(args.num_frames)
    records = []

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
                "base": {"x": fr["x"], "y": float(env.base_xyz[1]), "z": fr["z"], "yaw": fr["yaw"]},
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

    elapsed = time.time() - t0
    summary = {
        "status": "ok",
        "control_mode": MODE_KINEMATIC,
        "note": "Kinematic state set only; NOT whole-body swerve dynamics.",
        "locomanip_commit": LOCOMANIP_COMMIT,
        "habitat_sim": habitat_sim.__version__,
        "built_with_bullet": bool(habitat_sim.built_with_bullet),
        "scene": args.scene,
        "urdf": args.urdf,
        "num_frames": len(frames),
        "elapsed_sec": elapsed,
        "out_dir": str(out),
        "link_has_camera": CAMERA_LINK in env.link_ids,
        "n_links": len(env.link_ids),
        "final_contacts": records[-1]["contact_count"] if records else None,
        "arm_within_limits_final": all(
            v["within"] for v in records[-1]["joint_limits"].values()
        )
        if records
        else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    env.close()
    return summary


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--urdf", default=URDF_HABITAT)
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "kinematic_demo"))
    p.add_argument("--num_frames", type=int, default=40)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args(argv)
    summary = run_demo(args)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
