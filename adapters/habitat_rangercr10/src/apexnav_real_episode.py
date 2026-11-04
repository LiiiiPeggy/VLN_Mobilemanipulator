"""Real ApexNav planner-driven ObjectNav attempt with Ranger+CR10 in Habitat.

Control mode: kinematic_state_set (constrained). Does NOT fall back to scripted_policy.
Does NOT modify baselines/ApexNav defaults.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

# ROS / ApexNav imports expected after sourcing noetic + ApexNav devel
import rospy
from geometry_msgs.msg import PoseStamped
from plan_env.msg import MultipleMasksWithConfidence
from std_msgs.msg import Float64, Int32, Int32MultiArray

from .constants import (
    ARM_APEXNAV_INIT,
    ARM_DEFAULT,
    DEFAULT_OUT_DIR,
    DEFAULT_SCENE,
    LOCOMANIP_COMMIT,
    MODE_KINEMATIC,
    URDF_HABITAT,
)
from .coord_habitat_ros import hab_pos_to_ros
from .demo_compose import compose_frame
from .initial_camera_pose import apply_and_record_initial_camera
from .kinematic_demo import DEFAULT_BASE_Y, RangerCr10KinematicEnv
from .map_listener import ApexNavMapListener
from .pointcloud_dynamic import object_clouds_from_masks
from .ros_dynamic_publisher import DynamicROSPublisher
from .spawn_utils import find_adapted_start
from .traj_utils import save_depth_mm

# ApexNav exploration_fsm.cpp: 1 TURN_DOWN + 12 TURN_LEFT + 1 TURN_UP + 12 TURN_LEFT
APEXNAV_INIT_LOOKAROUND_ACTIONS = 26

# Mirror params.py without importing habitat_evaluation side effects
class HABITAT_STATE:
    READY = 0
    ACTION_EXEC = 1
    ACTION_FINISH = 2
    EPISODE_FINISH = 3


class ROS_STATE:
    INIT = 0
    WAIT_TRIGGER = 1
    PLAN_ACTION = 2
    WAIT_ACTION_FINISH = 3
    PUB_ACTION = 4
    FINISH = 5


class ACTION:
    STOP = 0
    MOVE_FORWARD = 1
    TURN_LEFT = 2
    TURN_RIGHT = 3
    TURN_DOWN = 4
    TURN_UP = 5


ACTION_NAME = {
    0: "STOP",
    1: "MOVE_FORWARD",
    2: "TURN_LEFT",
    3: "TURN_RIGHT",
    4: "TURN_DOWN",
    5: "TURN_UP",
}

FORWARD_M = 0.25
TURN_RAD = math.radians(30)
LOOK_PITCH_RAD = math.pi / 6.0  # original ApexNav ±30°
DEPTH_MIN, DEPTH_MAX = 0.0, 5.0


def _pub_int(pub, v: int) -> None:
    m = Int32()
    m.data = int(v)
    pub.publish(m)


def _pub_f64(pub, v: float) -> None:
    m = Float64()
    m.data = float(v)
    pub.publish(m)


def _goals_for_episode(data: dict, ep: dict, same_floor_tol: float = 1.2) -> List[dict]:
    """HM3D-v2 stores goals in goals_by_category, not episode.goals.

    Prefer same-floor goals vs start_position[1] (ApexNav skips cross-floor).
    """
    goals = list(ep.get("goals") or [])
    if not goals:
        gbc = data.get("goals_by_category") or {}
        scene_id = Path(ep.get("scene_id", "")).name  # TEEsavR23oF.basis.glb
        cat = ep.get("object_category", "")
        key = f"{scene_id}_{cat}"
        goals = list(gbc.get(key) or [])
        if not goals:
            stem = scene_id.replace(".basis.glb", "").replace(".glb", "")
            for k, v in gbc.items():
                if stem in k and k.endswith(f"_{cat}") and v:
                    goals = list(v)
                    break
    sy = float(ep.get("start_position", [0, 0, 0])[1])
    same = [g for g in goals if abs(float(g.get("position", [0, 0, 0])[1]) - sy) <= same_floor_tol]
    return same if same else goals


def load_episode(
    dataset_root: Path,
    scene_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> dict:
    """Load one ObjectNav-HM3D-v2 val episode (content json)."""
    content = dataset_root / "val" / "content"
    files = sorted(content.glob("*.json.gz"))
    if not files:
        raise FileNotFoundError(f"no episodes under {content}")
    for fp in files:
        with gzip.open(fp, "rt") as f:
            data = json.load(f)
        eps = data.get("episodes", [])
        if not eps:
            continue
        for ep in eps:
            sid = ep.get("scene_id", "")
            if scene_filter and scene_filter not in sid:
                continue
            if category_filter and ep.get("object_category") != category_filter:
                continue
            # ################################
            # Optional explicit episode_id (string compare) for open-floor starts.
            # ################################
            if episode_id is not None and str(ep.get("episode_id")) != str(episode_id):
                continue
            goals = _goals_for_episode(data, ep)
            if not goals:
                continue
            return {
                "file": str(fp),
                "episode_id": ep.get("episode_id"),
                "scene_id": sid,
                "object_category": ep.get("object_category"),
                "start_position": ep.get("start_position"),
                "start_rotation": ep.get("start_rotation"),
                "goals": goals,
            }
    raise FileNotFoundError(
        f"no episode matched scene_filter={scene_filter!r} "
        f"category={category_filter!r} episode_id={episode_id!r}"
    )


def scene_glb_from_episode(scene_id: str, hm3d_root: Path) -> str:
    """Resolve ObjectNav scene_id to an absolute .basis.glb under shared HM3D."""
    sid = Path(scene_id)
    candidates = [
        hm3d_root / sid.name,
        hm3d_root / sid.parent.name / sid.name if sid.parent != Path(".") else None,
        Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets") / scene_id,
        Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d")
        / scene_id.replace("hm3d_v0.2/", ""),
    ]
    stem = sid.name.replace(".basis.glb", "").replace(".glb", "")
    matches = list(Path(hm3d_root).glob(f"**/{stem}.basis.glb"))
    candidates.extend(matches)
    for c in candidates:
        if c is not None and Path(c).is_file():
            return str(c)
    raise FileNotFoundError(f"cannot resolve scene glb for {scene_id}")


def load_detector_cfg():
    """Reuse ApexNav hydra detector config without changing baseline defaults on disk."""
    try:
        from hydra import compose, initialize_config_dir
        from hydra.core.global_hydra import GlobalHydra

        cfg_dir = "/workspace/VLN_Mobilemanipulator/baselines/ApexNav/config"
        if not Path(cfg_dir).is_dir():
            cfg_dir = str(
                Path(__file__).resolve().parents[3] / "baselines/ApexNav/config"
            )
        GlobalHydra.instance().clear()
        with initialize_config_dir(config_dir=cfg_dir, version_base=None):
            cfg = compose(config_name="habitat_eval_hm3dv2")
        return cfg.detector
    except Exception as e:
        # Minimal structural fallback matching get_object attribute access
        class _Y:
            agnostic_nms = True
            confidence_threshold_yolo = 0.4
            iou_threshold_yolo = 0.5

        class _G:
            confidence_threshold_dino = 0.35
            text_threshold = 0.25

        class _D:
            yolo = _Y()
            groundingDINO = _G()

        _D._load_error = str(e)  # type: ignore
        return _D()


def hab_quat_yaw(rotation_xyzw_or_wxyz) -> float:
    """Episode start_rotation is typically habitat quaternion [x,y,z,w] or list."""
    q = np.asarray(rotation_xyzw_or_wxyz, dtype=np.float64).reshape(-1)
    if q.shape[0] != 4:
        return 0.0
    # Habitat uses xyzw in many datasets
    x, y, z, w = q
    # yaw about Y
    return float(math.atan2(2 * (w * y + x * z), 1 - 2 * (y * y + z * z)))


def goal_distance(base_xyz: np.ndarray, goals: List[dict]) -> float:
    best = 1e9
    for g in goals:
        p = g.get("position")
        if p is None:
            continue
        # habitat y-up: horizontal xz distance
        d = math.hypot(base_xyz[0] - p[0], base_xyz[2] - p[2])
        best = min(best, d)
    return best


class ApexNavRangerBridge:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
        self.out = Path(args.out_dir) / self.run_id
        self.out.mkdir(parents=True, exist_ok=True)
        for sub in ("rgb_ee", "depth_ee", "third", "detections", "maps", "demo"):
            (self.out / sub).mkdir(exist_ok=True)

        self.global_action: Optional[int] = None
        self.ros_state = ROS_STATE.INIT
        self.final_state = None
        self.expl_result = None
        self.last_action_stamp = 0.0
        self.seen_action_ids = 0

        self.env: Optional[RangerCr10KinematicEnv] = None
        self.ros_pub: Optional[DynamicROSPublisher] = None
        self.map_listener: Optional[ApexNavMapListener] = None
        self.traj_ros: List[Tuple[float, float]] = []
        self.n_init_actions = 0
        self.n_explore_actions = 0
        self.spawn_info: Optional[dict] = None
        self.log: List[dict] = []
        self.termination = "not_finished"
        self.planner_alive = False

    def _callbacks(self):
        def on_action(msg):
            self.global_action = int(msg.data)
            self.last_action_stamp = time.time()
            self.seen_action_ids += 1

        def on_state(msg):
            self.ros_state = int(msg.data)

        def on_final(msg):
            self.final_state = int(msg.data)

        def on_expl(msg):
            self.expl_result = int(msg.data)

        rospy.Subscriber("/habitat/plan_action", Int32, on_action, queue_size=1, buff_size=2**20)
        rospy.Subscriber("/ros/state", Int32, on_state, queue_size=10)
        rospy.Subscriber("/ros/expl_state", Int32, on_final, queue_size=10)
        rospy.Subscriber("/ros/expl_result", Int32, on_expl, queue_size=10)

    def _require_planner(self) -> None:
        import subprocess

        master = rospy.get_master()
        try:
            # XML-RPC getSystemState: [pubs, subs, services]
            _code, _msg, state = master.getSystemState()
            nodes = set()
            for group in state:
                for _topic, node_list in group:
                    nodes.update(node_list)
        except Exception:
            nodes = set()
        r = subprocess.run(
            [
                "bash",
                "-lc",
                "source /opt/ros/noetic/setup.bash; "
                "export ROS_MASTER_URI=${ROS_MASTER_URI:-http://127.0.0.1:11312}; "
                "rosnode list",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "ROS_MASTER_URI": os.environ.get("ROS_MASTER_URI", "http://127.0.0.1:11312")},
        )
        nodes.update(x for x in r.stdout.split() if x.startswith("/"))
        if "/exploration_node" not in nodes:
            raise RuntimeError(
                "REAL_PLANNER_MISSING: /exploration_node not in rosnode list "
                f"(have={sorted(nodes)[:20]}). "
                "Start ApexNav exploration.launch before this episode. "
                "Will NOT fall back to scripted_policy."
            )
        self.planner_alive = True

    def _publish_obs_bundle(self, rgb, depth, step_i: int) -> dict:
        assert self.env and self.ros_pub
        cam_T = self.env.camera_world_matrix()
        # EE camera after optical fix for ROS projection
        import magnum as mn

        fix = mn.Matrix4.rotation_x(mn.Rad(math.pi))
        ee_T = cam_T @ fix
        meta = self.ros_pub.publish(
            rgb=rgb[..., :3],
            depth_m=depth,
            base_pos_hab=self.env.base_xyz,
            base_yaw_hab=self.env.base_yaw,
            camera_T_hab=ee_T,
        )
        # save artifacts
        Image.fromarray(rgb[..., :3]).save(self.out / "rgb_ee" / f"frame_{step_i:04d}.png")
        save_depth_mm(self.out / "depth_ee" / f"frame_{step_i:04d}.png", depth)
        return meta

    def _execute_action(self, action: int) -> dict:
        """Kinematic execution with collision diagnostics and LOOK pitch verify."""
        assert self.env
        before = {
            "base": self.env.base_xyz.copy(),
            "yaw": float(self.env.base_yaw),
            "arm": self.env.arm_q.copy(),
            "contacts": self.env.contact_count(),
            "forward": self.env.camera_forward_hab(),
        }
        info: Dict[str, Any] = {
            "raw_action": int(action),
            "action_name": ACTION_NAME.get(int(action), str(action)),
            "look_equivalence": "native_pitch_approx"
            if action in (ACTION.TURN_UP, ACTION.TURN_DOWN)
            else "base_discrete",
            "executed": False,
            "blocked": False,
            "pitch_delta_rad": None,
        }
        x, y, z = self.env.base_xyz
        yaw = self.env.base_yaw
        floor_y = float(getattr(self.env, "floor_y", y - DEFAULT_BASE_Y))

        def _place(nx, nz, nyaw):
            self.env.set_base_pose(
                float(nx), float(nz), float(nyaw), y=float(y), floor_y=floor_y
            )

        if action == ACTION.STOP:
            info["executed"] = True
            return info
        if action == ACTION.MOVE_FORWARD:
            # intermediate check: half step then full
            nx = x + 0.5 * FORWARD_M * math.sin(yaw)
            nz = z + 0.5 * FORWARD_M * math.cos(yaw)
            _place(nx, nz, yaw)
            mid_c = self.env.contact_count()
            nx2 = x + FORWARD_M * math.sin(yaw)
            nz2 = z + FORWARD_M * math.cos(yaw)
            _place(nx2, nz2, yaw)
            after_c = self.env.contact_count()
            # heuristic: large contact jump + tiny motion → blocked (diagnostic)
            moved = math.hypot(self.env.base_xyz[0] - x, self.env.base_xyz[2] - z)
            if after_c > before["contacts"] + 15 and moved < 0.05:
                # revert
                _place(x, z, yaw)
                info["blocked"] = True
                info["block_reason"] = "contact_spike_little_motion"
            else:
                info["executed"] = True
            info["mid_contacts"] = mid_c
            info["moved_m"] = moved
            info["upright"] = self.env.upright_diagnostics()
        elif action == ACTION.TURN_LEFT:
            _place(x, z, yaw + TURN_RAD)
            info["executed"] = True
            info["upright"] = self.env.upright_diagnostics()
        elif action == ACTION.TURN_RIGHT:
            _place(x, z, yaw - TURN_RAD)
            info["executed"] = True
            info["upright"] = self.env.upright_diagnostics()
        elif action in (ACTION.TURN_UP, ACTION.TURN_DOWN):
            # ################################
            # LOOK pitch via joint3 (not joint5): at LocoManip 4.10 default FK,
            # joint5 optical-pitch gain ≈ 0; joint3 ≈ 50 deg/rad. ±0.6 rad ≈ ±30°.
            # Still arm-adapted — NOT Habitat agent look_up/down.
            # ################################
            q = self.env.arm_q.copy()
            # Empirical @ L410: joint3 +δ → optical pitch up (Habitat fwd.y>0)
            delta = 0.60 if action == ACTION.TURN_UP else -0.60
            q[2] = float(np.clip(q[2] + delta, -2.86, 2.86))
            self.env.set_arm_joints(q)
            after_f = self.env.camera_forward_hab()
            # pitch change approx: angle between forward vectors projected
            cosang = float(np.clip(np.dot(before["forward"], after_f), -1, 1))
            info["pitch_delta_rad"] = float(math.acos(cosang))
            info["look_equivalence"] = "arm_joint3_adapted_not_habitat_look"
            info["look_joint"] = "cr10_joint3"
            info["executed"] = True
            if info["pitch_delta_rad"] < math.radians(5):
                info["pitch_verify"] = "weak_change"
            else:
                info["pitch_verify"] = "ok"
        else:
            info["blocked"] = True
            info["block_reason"] = f"unknown_action_{action}"
        info["contacts_after"] = self.env.contact_count()
        info["joint_limits"] = self.env.joint_limits_report()
        return info

    def run(self) -> dict:
        args = self.args
        t0 = time.time()
        error = None
        status = "ok"
        try:
            rospy.init_node("apexnav_ranger_bridge", anonymous=True)
            self._callbacks()
            self.map_listener = ApexNavMapListener()
            self._require_planner()

            ep = load_episode(
                Path(args.objectnav_root),
                scene_filter=args.scene_filter or None,
                category_filter=args.category_filter or None,
                episode_id=args.episode_id or None,
            )
            scene = scene_glb_from_episode(ep["scene_id"], Path(args.hm3d_root))
            (self.out / "episode.json").write_text(json.dumps(ep, indent=2))

            self.env = RangerCr10KinematicEnv(scene=scene, urdf=args.urdf, gpu_device_id=args.gpu)
            # place at episode start (habitat y-up)
            sp = ep["start_position"]
            yaw = hab_quat_yaw(ep["start_rotation"])
            # Habitat ObjectNav start_position y ≈ navmesh floor
            floor_y = float(sp[1])
            spawn = find_adapted_start(
                self.env, (float(sp[0]), float(sp[2])), yaw, floor_y=floor_y
            )
            self.spawn_info = spawn
            (self.out / "start_pose.json").write_text(
                json.dumps(
                    {
                        "episode_start_position": sp,
                        "episode_start_rotation": ep["start_rotation"],
                        "spawn": spawn,
                        "urdf_to_habitat": "Ry(-90)*Rx(-90) Z-up→Y-up",
                        "note": "adapted_episode if start offset >5cm; not raw benchmark",
                    },
                    indent=2,
                )
            )
            # seed trajectory for map panel
            br0 = hab_pos_to_ros(self.env.base_xyz)
            self.traj_ros = [(float(br0[0]), float(br0[1]))]
            # diagnostic views (top/side/third) after upright place
            diag = self.out / "pose_diag"
            diag.mkdir(exist_ok=True)
            try:
                import magnum as mn

                Image.fromarray(self.env.observe_third_only()[..., :3]).save(
                    diag / "third.png"
                )
                b = self.env.base_xyz
                eye = mn.Vector3(b[0] + 3.2, b[1] + 1.3, b[2])
                tgt = mn.Vector3(b[0], b[1] + 0.5, b[2])
                self.env._set_agent_pose(
                    mn.Matrix4.look_at(eye, tgt, mn.Vector3(0, 1, 0))
                )
                Image.fromarray(
                    self.env.sim.get_sensor_observations()["third_rgb"][..., :3]
                ).save(diag / "side.png")
                eye = mn.Vector3(b[0], b[1] + 4.8, b[2] + 0.05)
                tgt = mn.Vector3(b[0], b[1], b[2])
                self.env._set_agent_pose(
                    mn.Matrix4.look_at(eye, tgt, mn.Vector3(0, 0, -1))
                )
                Image.fromarray(
                    self.env.sim.get_sensor_observations()["third_rgb"][..., :3]
                ).save(diag / "top.png")
                (diag / "upright.json").write_text(
                    json.dumps(self.env.upright_diagnostics(), indent=2)
                )
            except Exception as e:
                (diag / "diag_error.txt").write_text(str(e))
            # ################################
            # ApexNav-like init camera via URDF FK (not ARM_DEFAULT / not forged agent pose)
            # ################################
            cam_init = apply_and_record_initial_camera(self.env, self.out / "camera_init")
            (self.out / "camera_init_summary.json").write_text(
                json.dumps(
                    {
                        "selected": cam_init.get("selected"),
                        "final": cam_init.get("final"),
                        "ARM_DEFAULT_ok": cam_init.get("ARM_DEFAULT", {})
                        .get("tolerances", {})
                        .get("all_ok"),
                        "note": "ARM_DEFAULT kept for teleop; episode uses ARM_APEXNAV_INIT FK",
                        "arm_default": list(ARM_DEFAULT),
                        "arm_apexnav_init": list(ARM_APEXNAV_INIT),
                    },
                    indent=2,
                )
            )
            if not cam_init.get("final", {}).get("tolerances", {}).get("all_ok", False):
                # Still proceed with best FK; mark for evaluation honesty
                (self.out / "camera_init_OUT_OF_TOL.txt").write_text(
                    cam_init.get("warning", "out of tolerance")
                )

            self.ros_pub = DynamicROSPublisher(DEPTH_MIN, DEPTH_MAX)
            state_pub = rospy.Publisher("/habitat/state", Int32, queue_size=10)
            trigger_pub = rospy.Publisher("/move_base_simple/goal", PoseStamped, queue_size=10)
            itm_score_pub = rospy.Publisher("/blip2/cosine_score", Float64, queue_size=10)
            confidence_threshold_pub = rospy.Publisher(
                "/detector/confidence_threshold", Float64, queue_size=10
            )
            cld_pub = rospy.Publisher(
                "/detector/clouds_with_scores", MultipleMasksWithConfidence, queue_size=10
            )
            progress_pub = rospy.Publisher("/habitat/progress", Int32MultiArray, queue_size=10)
            rospy.sleep(1.0)

            label = ep["object_category"]
            # Map HM3D category via ApexNav helpers if available
            try:
                from vlm.Labels import category_to_coco, id_to_name  # type: ignore

                if label in category_to_coco:
                    label = id_to_name.get(category_to_coco[label], label)
            except Exception:
                pass

            fusion_threshold = 0.35
            # LLM answer optional
            llm_answer, room = None, ""
            try:
                from llm.answer_reader.answer_reader import read_answer  # type: ignore

                llm_answer, room, fusion_threshold = read_answer(
                    args.llm_answer_path, args.llm_response_path, label, None
                )
            except Exception as e:
                (self.out / "llm_warn.txt").write_text(str(e))
                llm_answer = [label] if not isinstance(label, list) else label
            if isinstance(llm_answer, str):
                llm_answer = [llm_answer]

            detector_cfg = load_detector_cfg()
            (self.out / "target_label.json").write_text(
                json.dumps(
                    {
                        "object_category": ep["object_category"],
                        "label": label,
                        "room": room,
                        "llm_answer": llm_answer,
                        "fusion_threshold": fusion_threshold,
                    },
                    indent=2,
                )
            )

            # Initial observation + wait for planner handshake
            ee = self.env.observe_ee_only()
            meta = self._publish_obs_bundle(ee["ee_rgb"], ee["ee_depth"], 0)
            (self.out / "pre_plan_obs_meta.json").write_text(json.dumps(meta, indent=2))
            _pub_f64(confidence_threshold_pub, fusion_threshold)
            trigger_pub.publish(PoseStamped())
            _pub_int(state_pub, HABITAT_STATE.READY)

            # Cache EE obs; republish at ~4 Hz like habitat_evaluation timer (avoid GPU thrash)
            cached_ee = ee
            rate = rospy.Rate(4)
            wait_t0 = time.time()
            last_reobs = time.time()
            while self.ros_state in (ROS_STATE.INIT, ROS_STATE.WAIT_TRIGGER):
                if time.time() - last_reobs > 1.0:
                    cached_ee = self.env.observe_ee_only()
                    last_reobs = time.time()
                self._publish_obs_bundle(cached_ee["ee_rgb"], cached_ee["ee_depth"], 0)
                trigger_pub.publish(PoseStamped())
                _pub_f64(confidence_threshold_pub, fusion_threshold)
                if time.time() - wait_t0 > args.handshake_timeout_s:
                    raise RuntimeError(
                        f"PLANNER_HANDSHAKE_TIMEOUT: ros_state stuck at {self.ros_state} "
                        f"for {args.handshake_timeout_s}s"
                    )
                rate.sleep()

            # If planner already advanced to WAIT_ACTION_FINISH (missed first action),
            # ACK finish once so FSM can publish the next plan_action.
            if (
                self.ros_state == ROS_STATE.WAIT_ACTION_FINISH
                and self.global_action is None
            ):
                _pub_int(state_pub, HABITAT_STATE.ACTION_FINISH)
                rospy.sleep(0.3)

            step = 0
            success_distance = args.success_distance
            while step < args.max_steps and not rospy.is_shutdown():
                # wait for action from real planner
                wait_a0 = time.time()
                while self.global_action is None:
                    if time.time() - wait_a0 > args.action_timeout_s:
                        self.termination = "planner_action_timeout"
                        raise RuntimeError(
                            f"PLANNER_ACTION_TIMEOUT at step {step}: no /habitat/plan_action "
                            f"within {args.action_timeout_s}s (ros_state={self.ros_state})"
                        )
                    # Unstick planner waiting on our ACTION_FINISH
                    if self.ros_state == ROS_STATE.WAIT_ACTION_FINISH:
                        _pub_int(state_pub, HABITAT_STATE.ACTION_FINISH)
                    if time.time() - last_reobs > 1.0:
                        cached_ee = self.env.observe_ee_only()
                        last_reobs = time.time()
                    self._publish_obs_bundle(
                        cached_ee["ee_rgb"], cached_ee["ee_depth"], step
                    )
                    _pub_f64(confidence_threshold_pub, fusion_threshold)
                    rate.sleep()

                action = int(self.global_action)
                self.global_action = None
                # ################################
                # ApexNav exploration_fsm: first 26 plan actions = init lookaround;
                # subsequent actions come from callActionPlanner() (real explore).
                # ################################
                phase = (
                    "init_lookaround"
                    if step < APEXNAV_INIT_LOOKAROUND_ACTIONS
                    else "explore_planner"
                )
                if phase == "init_lookaround":
                    self.n_init_actions += 1
                else:
                    self.n_explore_actions += 1
                (self.out / "actions.jsonl").open("a").write(
                    json.dumps(
                        {
                            "step": step,
                            "action": action,
                            "name": ACTION_NAME.get(action, str(action)),
                            "phase": phase,
                            "ros_state": self.ros_state,
                            "t": time.time(),
                        }
                    )
                    + "\n"
                )

                _pub_int(state_pub, HABITAT_STATE.ACTION_EXEC)
                exec_info = self._execute_action(action)

                # new observation after motion
                ee = self.env.observe_ee_only()
                rgb, depth = ee["ee_rgb"], ee["ee_depth"]
                meta = self._publish_obs_bundle(rgb, depth, step)
                br = hab_pos_to_ros(self.env.base_xyz)
                self.traj_ros.append((float(br[0]), float(br[1])))

                # ITM + detection (real VLM servers)
                cosine = -1.0
                score_list, masks, label_list = [], [], []
                rgb_vis = rgb[..., :3].copy()
                try:
                    from vlm.utils.get_itm_message import get_itm_message_cosine  # type: ignore
                    from vlm.utils.get_object_utils import get_object  # type: ignore

                    cosine = float(get_itm_message_cosine(rgb[..., :3], label, room))
                    _pub_f64(itm_score_pub, cosine)
                    rgb_vis, score_list, masks, label_list = get_object(
                        label, rgb[..., :3].copy(), detector_cfg, llm_answer
                    )
                    Image.fromarray(rgb_vis).save(
                        self.out / "detections" / f"frame_{step:04d}.png"
                    )
                except Exception as e:
                    (self.out / f"vlm_step_{step}_error.txt").write_text(traceback.format_exc())
                    # Perception failure is a real failure mode for this episode goal
                    self.termination = "perception_error"
                    raise RuntimeError(f"VLM/perception failed at step {step}: {e}") from e

                clouds = object_clouds_from_masks(
                    depth, masks, ee["ee_T"], hfov_deg=79.0, min_depth=DEPTH_MIN, max_depth=DEPTH_MAX
                )
                msg = MultipleMasksWithConfidence()
                msg.point_clouds = clouds
                msg.confidence_scores = [float(s) for s in score_list]
                msg.label_indices = [int(x) for x in label_list]
                cld_pub.publish(msg)

                # third-person AFTER publish (must not affect planner stream)
                third = None
                try:
                    third = self.env.observe_third_only()
                    Image.fromarray(third[..., :3]).save(
                        self.out / "third" / f"frame_{step:04d}.png"
                    )
                except Exception:
                    third = np.zeros((720, 1280, 3), dtype=np.uint8)

                # ################################
                # Online ApexNav /grid_map panel + 16:9 paper-style compose
                # ################################
                map_stats = {}
                try:
                    assert self.map_listener is not None
                    map_rgb = self.map_listener.render_panel(
                        size=(320, 240),
                        robot_xy=(float(br[0]), float(br[1])),
                        robot_yaw=float(self.env.base_yaw),
                        traj_xy=list(self.traj_ros),
                    )
                    map_stats = self.map_listener.stats()
                    Image.fromarray(map_rgb).save(
                        self.out / "maps" / f"frame_{step:04d}.png"
                    )
                    (self.out / "maps" / "latest_stats.json").write_text(
                        json.dumps(
                            {
                                "step": step,
                                "phase": phase,
                                "has_map": self.map_listener.has_map(),
                                "stats": map_stats,
                            },
                            indent=2,
                        )
                    )
                except Exception:
                    map_rgb = np.full((240, 320, 3), 40, dtype=np.uint8)
                    (self.out / f"map_step_{step}_error.txt").write_text(
                        traceback.format_exc()
                    )

                try:
                    demo = compose_frame(
                        third[..., :3] if third is not None else np.zeros((720, 1280, 3), dtype=np.uint8),
                        np.asarray(rgb_vis)[..., :3],
                        map_rgb,
                        goal=str(ep.get("object_category", label)),
                        step=step,
                        action=ACTION_NAME.get(action, str(action)),
                        phase=phase,
                        control_mode=MODE_KINEMATIC,
                        status=self.termination if self.termination != "not_finished" else "running",
                    )
                    Image.fromarray(demo).save(
                        self.out / "demo" / f"frame_{step:04d}.png"
                    )
                except Exception:
                    (self.out / f"demo_step_{step}_error.txt").write_text(
                        traceback.format_exc()
                    )

                dtg = goal_distance(self.env.base_xyz, ep["goals"])
                rec = {
                    "step": step,
                    "planner_action": action,
                    "planner_action_name": ACTION_NAME.get(action, str(action)),
                    "phase": phase,
                    "action_source": "apexnav_/habitat/plan_action",
                    "ros_state": self.ros_state,
                    "final_state": self.final_state,
                    "expl_result": self.expl_result,
                    "exec": exec_info,
                    "publish_meta": meta,
                    "itm_cosine": cosine,
                    "n_detections": len(score_list),
                    "distance_to_goal_eval_only": dtg,
                    "map_stats": map_stats,
                    "base": {
                        "x": float(self.env.base_xyz[0]),
                        "y": float(self.env.base_xyz[1]),
                        "z": float(self.env.base_xyz[2]),
                        "yaw": float(self.env.base_yaw),
                    },
                    "arm": self.env.arm_q.tolist(),
                    "control_mode": MODE_KINEMATIC,
                }
                self.log.append(rec)
                (self.out / "steps.jsonl").write_text(
                    "\n".join(json.dumps(x) for x in self.log) + "\n"
                )

                _pub_int(state_pub, HABITAT_STATE.ACTION_FINISH)

                if exec_info.get("blocked"):
                    self.termination = "execution_blocked"
                    break
                if action == ACTION.STOP:
                    self.termination = "planner_stop"
                    break
                if dtg <= success_distance and len(score_list) > 0:
                    # visual confirm candidate — still only STOP from planner counts as nav stop
                    rec["near_goal_and_detection"] = True
                step += 1
                if step >= args.max_steps:
                    self.termination = "step_budget_exhausted"
                    break
                rate.sleep()

            _pub_int(state_pub, HABITAT_STATE.EPISODE_FINISH)
            if self.termination == "not_finished":
                self.termination = "completed_without_stop"

        except Exception as e:
            status = "failed"
            error = f"{type(e).__name__}: {e}"
            (self.out / "error.log").write_text(traceback.format_exc())
            if self.termination == "not_finished":
                self.termination = "exception"
        finally:
            if self.env is not None:
                try:
                    self.env.close()
                except Exception:
                    pass

        elapsed = time.time() - t0
        # Evaluate (GT only for metrics)
        final_dtg = None
        if self.log:
            final_dtg = self.log[-1].get("distance_to_goal_eval_only")
        map_ok = False
        map_final = {}
        if self.map_listener is not None:
            map_ok = bool(self.map_listener.has_map())
            map_final = self.map_listener.stats()
        entered_explore = self.n_explore_actions > 0
        summary = {
            "status": status,
            "run_id": self.run_id,
            "control_mode": MODE_KINEMATIC,
            "apexnav_planner": "exploration_node_real",
            "scripted_policy_used": False,
            "termination": self.termination,
            "error": error,
            "elapsed_sec": elapsed,
            "n_steps": len(self.log),
            "seen_plan_actions": self.seen_action_ids,
            "n_init_lookaround_actions": self.n_init_actions,
            "n_explore_planner_actions": self.n_explore_actions,
            "entered_callActionPlanner": entered_explore,
            "apexnav_init_lookaround_budget": APEXNAV_INIT_LOOKAROUND_ACTIONS,
            "spawn": self.spawn_info,
            "adapted_episode": bool(
                self.spawn_info.get("adapted_episode") if self.spawn_info else False
            ),
            "online_grid_map": {"has_data": map_ok, "stats": map_final},
            "final_distance_to_goal_eval_only": final_dtg,
            "success_claimed": False,  # never claim ObjectNav success without official evaluator
            "near_goal": bool(final_dtg is not None and final_dtg <= args.success_distance),
            "locomanip_commit": LOCOMANIP_COMMIT,
            "out_dir": str(self.out),
            "notes": [
                "LOOK_UP/DOWN are arm-joint adapted (±pitch via FK), not Habitat agent look.",
                "Initial EE uses ARM_APEXNAV_INIT FK (~0.88m horizontal); runtime sensor_pose is full SE3.",
                "Goal distance is eval-only and not fed to planner.",
                "URDF Z-up→Habitat Y-up via Ry(-90)*Rx(-90); wheels snapped to floor_y.",
                "Init lookaround ≠ adaptive explore; explore starts after 26 FSM init actions.",
                "Demo map panel uses ApexNav /grid_map/* (not Habitat GT).",
            ],
            "initial_camera": {
                "config": "ARM_APEXNAV_INIT",
                "record_dir": str(self.out / "camera_init"),
            },
            "demo": {
                "layout": "16:9 third + EE semantic + /grid_map",
                "frames_dir": str(self.out / "demo"),
            },
        }
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2))
        # also write process exit hint separately
        (self.out / "process_meta.json").write_text(
            json.dumps(
                {
                    "expected_cleanup_abort": "habitat Simulator.close may SIGABRT/134",
                    "task_status_file": "summary.json",
                },
                indent=2,
            )
        )
        return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "apexnav_real"))
    p.add_argument("--run_id", default="")
    p.add_argument("--urdf", default=URDF_HABITAT)
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument("--max_steps", type=int, default=40)
    p.add_argument("--success_distance", type=float, default=1.0)
    p.add_argument("--handshake_timeout_s", type=float, default=120.0)
    p.add_argument("--action_timeout_s", type=float, default=90.0)
    p.add_argument(
        "--objectnav_root",
        default="/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2",
    )
    p.add_argument(
        "--hm3d_root",
        default="/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val",
    )
    p.add_argument("--scene_filter", default="TEEsavR23oF")
    p.add_argument("--category_filter", default="chair")
    # ################################
    # Default eid 4: more open TEEsav floor start vs eid 3 bedroom (prior free≈6).
    # ################################
    p.add_argument("--episode_id", default="4")
    p.add_argument("--detector_cfg", default="yolo")
    p.add_argument(
        "--llm_answer_path",
        default="/workspace/VLN_Mobilemanipulator/baselines/ApexNav/llm/answers/llm_answer_hm3d.txt",
    )
    p.add_argument(
        "--llm_response_path",
        default="/workspace/VLN_Mobilemanipulator/baselines/ApexNav/llm/answers/llm_response_list.txt",
    )
    args = p.parse_args(argv)
    # Ensure ApexNav python modules importable (prefer catkin build path symlink)
    for apex in (
        "/workspace/ApexNav",
        "/workspace/VLN_Mobilemanipulator/baselines/ApexNav",
    ):
        if Path(apex).is_dir() and apex not in sys.path:
            sys.path.insert(0, apex)
            break
    try:
        summary = ApexNavRangerBridge(args).run()
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("status") == "ok" else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
