"""MuJoCo-native teleop PPO arm raise, then joint sync for Habitat (adapter-only).

################################
Contract (unchanged vs stage 4.10d / published model_9999):
  obs=117 hist=3 @10Hz; act=8 = [vx,wz, j1..j6 raw];
  arm targets = ARM_DEFAULT + ACTION_SCALE * raw[2:];
  teleop commands: vel_cmd=(vx,wz), ee_cmd=ee_command_from_offset(dpos, drpy).

Default --policy is constants.DEFAULT_TELEOP_CKPT
(= models/ranger_cr10/model_9999.pt under --loco_root).
Loader: LocoManip deploy_mujoco.ranger_cr10.ranger_policy.load_actor
(hardcoded 117→512-256-128→8; does not read params/agent.yaml).

Raise uses vx=wz=0 and +Z EE offset (keyboard box). No IK joint targets.
LOOK_UP/DOWN uses same policy with ee_offset_rpy (pitch ±π/6) while holding
the raised Z offset so height stays ~ApexNav 0.88 m — not gimbal-only pitch.
MuJoCo stays 1.0× (training geometry). Habitat 0.7× consumes final arm joints only.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .constants import (
    ARM_DEFAULT,
    ARM_JOINT_NAMES,
    DEFAULT_TELEOP_CKPT,
    LOCOMANIP_REPO,
    POLICY_HZ,
)

# TCP offset from ranger_policy (Link6 → TCP); used for Habitat FK reporting only.
TCP_OFFSET_POS = np.array([0.0, 0.00003, 0.14389], dtype=np.float64)
TCP_BODY = "cr10_Link6"

# Stage 4.10 keyboard Z+ ceiling (workspace_limits.KEYBOARD_BOX_410)
Z_OFFSET_MAX = 0.40
EE_TARGET_AGL_M = 0.88
EE_TARGET_TOL_M = 0.02
# ################################
# ApexNav LOOK step (±30°) as EE pitch about training TCP frame.
# ################################
LOOK_PITCH_STEP_RAD = math.pi / 6.0
# ################################
# ApexNav discrete step targets for PPO chassis unit segments.
# ################################
CHASSIS_FORWARD_M = 0.25
CHASSIS_TURN_RAD = math.pi / 6.0
CHASSIS_VX_CMD = 0.25
CHASSIS_WZ_CMD = 0.50


def _official_base_filter():
    """Match deploy config.yaml: deadband 0.02 + lock_output=True, hysteresis=0."""
    from base_command_filter import BaseCommandFilter

    # ################################
    # Args: (vx_deadband, wz_deadband, lock_output, hysteresis)
    # ################################
    return BaseCommandFilter(0.02, 0.02, True, 0.0)


def _ensure_loco_paths(loco_root: Path) -> None:
    for p in (
        loco_root / "mujoco" / "deploy",
        loco_root / "mujoco" / "deploy" / "deploy_mujoco",
        loco_root / "scripts" / "ranger_cr10",
    ):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def run_mujoco_raise(
    *,
    policy: str,
    loco_root: str = LOCOMANIP_REPO,
    z_offset: float = Z_OFFSET_MAX,
    hold_steps: int = 40,
    ramp_steps: int = 20,
    settle_steps: int = 30,
    device: str = "cpu",
) -> Dict[str, Any]:
    """Drive teleop PPO in MuJoCo with +Z EE command; return final arm joints + log."""
    loco = Path(loco_root)
    _ensure_loco_paths(loco)
    import mujoco
    from base_command_filter import BaseCommandFilter
    from deploy_mujoco.ranger_cr10.ranger_policy import (  # type: ignore
        ACTION_SCALE,
        ARM_DEFAULT as MJ_ARM_DEFAULT,
        ARM_JOINT_NAMES as MJ_ARM_NAMES,
        STEERING_JOINT_NAMES,
        WHEEL_JOINT_NAMES,
        ChassisAction,
        EndEffector,
        RangerPolicyObs,
        act,
        ee_command_from_offset,
        load_actor,
    )
    from deploy_mujoco.ranger_cr10.teleop_eval import Sim, np_to_t  # type: ignore

    ckpt = Path(policy)
    if not ckpt.is_file():
        ckpt = loco / policy
    if not ckpt.is_file():
        raise FileNotFoundError(f"policy missing: {policy}")

    # ################################
    # Official Sim loop (filter on, same as teleop_eval): chassis held, EE +Z.
    # ################################
    filt = _official_base_filter()
    sim = Sim(str(ckpt), filt)
    sim.reset()
    z_cmd = float(np.clip(z_offset, 0.0, Z_OFFSET_MAX))
    log: List[dict] = []
    t0 = time.time()

    def _arm_q() -> List[float]:
        q = []
        for name in MJ_ARM_NAMES:
            jid = mujoco.mj_name2id(sim.m, mujoco.mjtObj.mjOBJ_JOINT, name)
            q.append(float(sim.d.qpos[sim.m.jnt_qposadr[jid]]))
        return q

    def _metrics() -> Dict[str, Any]:
        pos_b, quat_b = sim.ee.tcp_pose_b()
        # world Z of TCP (MuJoCo Z-up)
        import mujoco as mj

        mj.mj_forward(sim.m, sim.d)
        base_id = sim.base_id
        Rb = sim.d.xmat[base_id].reshape(3, 3)
        tcp_w = sim.d.xpos[base_id] + Rb @ pos_b
        # floor ~0 at home keyframe
        floor_z = 0.0
        try:
            # contact/floor geom; fallback 0
            floor_z = float(sim.d.xpos[0][2]) * 0.0
        except Exception:
            floor_z = 0.0
        # wheel mean as floor proxy
        wh = []
        for wn in ("fr_wheel_link", "fl_wheel_link", "rl_wheel_link", "rr_wheel_link"):
            bid = mj.mj_name2id(sim.m, mj.mjtObj.mjOBJ_BODY, wn)
            if bid >= 0:
                wh.append(float(sim.d.xpos[bid][2]))
        floor_z = float(np.mean(wh) - 0.1531) if wh else 0.0
        tcp_agl = float(tcp_w[2] - floor_z)
        base_xy = (float(sim.d.qpos[0]), float(sim.d.qpos[1]))
        return {
            "t": float(sim.t),
            "tcp_pos_b": pos_b.astype(float).tolist(),
            "tcp_quat_b": quat_b.astype(float).tolist(),
            "tcp_agl_mujoco_m": tcp_agl,
            "base_xy": list(base_xy),
            "arm_q": _arm_q(),
            "ee_pos_err": float(sim.ee.errors(sim.ee_cmd)[0]),
            "ee_ori_err_rad": float(sim.ee.errors(sim.ee_cmd)[1]),
            "path_m": float(sim.path),
        }

    # Ramp Z command (teleop-conditioned), hold chassis at 0.
    for i in range(int(ramp_steps)):
        u = (i + 1) / float(ramp_steps)
        dz = z_cmd * u
        sim.set_commands(0.0, 0.0, ee_command_from_offset((0.0, 0.0, dz), (0.0, 0.0, 0.0)))
        row = sim.step()
        m = _metrics()
        m["phase"] = "ramp"
        m["z_offset_cmd"] = dz
        m["vx_cmd"] = 0.0
        m["wz_cmd"] = 0.0
        log.append(m)

    sim.set_commands(0.0, 0.0, ee_command_from_offset((0.0, 0.0, z_cmd), (0.0, 0.0, 0.0)))
    for i in range(int(hold_steps)):
        sim.step()
        m = _metrics()
        m["phase"] = "hold"
        m["z_offset_cmd"] = z_cmd
        log.append(m)

    for i in range(int(settle_steps)):
        # keep command; allow tracking to settle
        sim.step()
        m = _metrics()
        m["phase"] = "settle"
        m["z_offset_cmd"] = z_cmd
        log.append(m)

    final = log[-1]
    base0 = log[0]["base_xy"]
    base1 = final["base_xy"]
    drift = float(math.hypot(base1[0] - base0[0], base1[1] - base0[1]))
    rep = {
        "status": "ok",
        "policy": str(ckpt),
        "policy_hz": POLICY_HZ,
        "num_obs": 117,
        "num_actions": 8,
        "obs_history": 3,
        "action_scale": float(ACTION_SCALE),
        "control": {
            "type": "teleop_conditioned_ee_pose",
            "vel_cmd": [0.0, 0.0],
            "ee_offset_pos": [0.0, 0.0, z_cmd],
            "ee_offset_rpy": [0.0, 0.0, 0.0],
            "note": "Native ee_command_from_offset; not IK joint targets",
        },
        "arm_default": [float(x) for x in MJ_ARM_DEFAULT],
        "arm_q_final": final["arm_q"],
        "tcp_agl_mujoco_m": final["tcp_agl_mujoco_m"],
        "tcp_pos_b_final": final["tcp_pos_b"],
        "ee_pos_err_final": final["ee_pos_err"],
        "ee_ori_err_deg_final": math.degrees(final["ee_ori_err_rad"]),
        "base_drift_m": drift,
        "path_m": final["path_m"],
        "elapsed_wall_s": time.time() - t0,
        "n_policy_steps": len(log),
        "log_tail": log[-5:],
        "log": log,
        "mujoco_scale": 1.0,
        "habitat_sync": "arm_joints_only",
        "tag": "scaled_robot_proxy_070_handover",
    }
    # quick limit proximity
    limits = np.array(
        [[-3.92, 0.94], [-1.570, 1.570], [-2.860, 2.860], [-3.140, 3.140], [-3.140, 3.140], [-3.140, 3.140]]
    )
    q = np.array(final["arm_q"], dtype=np.float64)
    near = np.any(np.abs(q - limits[:, 0]) < 0.03) or np.any(np.abs(q - limits[:, 1]) < 0.03)
    rep["near_joint_limit"] = bool(near)
    return rep


def run_mujoco_ee_orient(
    *,
    policy: str,
    loco_root: str = LOCOMANIP_REPO,
    offset_rpy: Sequence[float] = (0.0, 0.0, 0.0),
    offset_pos: Optional[Sequence[float]] = None,
    z_hold: float = Z_OFFSET_MAX,
    hold_steps: int = 40,
    ramp_steps: int = 15,
    settle_steps: int = 30,
    device: str = "cpu",
    tag: str = "ppo_ee_orient",
) -> Dict[str, Any]:
    """Drive teleop PPO with EE pose offset (typically pitch LOOK while holding Z).

    ################################
    ApexNav LOOK_UP/DOWN mapping: dpos=(0,0,z_hold), drpy=(0, ±π/6, 0).
    Position hold keeps the post-raise height; orientation comes from trained
    weights via ee_command_from_offset — not simulated gimbal / joint3 hack.
    ################################
    """
    loco = Path(loco_root)
    _ensure_loco_paths(loco)
    import mujoco
    from base_command_filter import BaseCommandFilter
    from deploy_mujoco.ranger_cr10.ranger_policy import (  # type: ignore
        ACTION_SCALE,
        ARM_DEFAULT as MJ_ARM_DEFAULT,
        ARM_JOINT_NAMES as MJ_ARM_NAMES,
        ee_command_from_offset,
    )
    from deploy_mujoco.ranger_cr10.teleop_eval import Sim  # type: ignore

    ckpt = Path(policy)
    if not ckpt.is_file():
        ckpt = loco / policy
    if not ckpt.is_file():
        raise FileNotFoundError(f"policy missing: {policy}")

    rpy = [float(x) for x in offset_rpy]
    if len(rpy) != 3:
        raise ValueError(f"offset_rpy must be length 3, got {offset_rpy}")
    if offset_pos is None:
        dpos = [0.0, 0.0, float(np.clip(z_hold, 0.0, Z_OFFSET_MAX))]
    else:
        dpos = [float(x) for x in offset_pos]
        if len(dpos) != 3:
            raise ValueError(f"offset_pos must be length 3, got {offset_pos}")

    filt = _official_base_filter()
    sim = Sim(str(ckpt), filt)
    sim.reset()
    log: List[dict] = []
    t0 = time.time()

    def _arm_q() -> List[float]:
        q = []
        for name in MJ_ARM_NAMES:
            jid = mujoco.mj_name2id(sim.m, mujoco.mjtObj.mjOBJ_JOINT, name)
            q.append(float(sim.d.qpos[sim.m.jnt_qposadr[jid]]))
        return q

    def _metrics() -> Dict[str, Any]:
        pos_b, quat_b = sim.ee.tcp_pose_b()
        import mujoco as mj

        mj.mj_forward(sim.m, sim.d)
        base_id = sim.base_id
        Rb = sim.d.xmat[base_id].reshape(3, 3)
        tcp_w = sim.d.xpos[base_id] + Rb @ pos_b
        wh = []
        for wn in ("fr_wheel_link", "fl_wheel_link", "rl_wheel_link", "rr_wheel_link"):
            bid = mj.mj_name2id(sim.m, mj.mjtObj.mjOBJ_BODY, wn)
            if bid >= 0:
                wh.append(float(sim.d.xpos[bid][2]))
        floor_z = float(np.mean(wh) - 0.1531) if wh else 0.0
        tcp_agl = float(tcp_w[2] - floor_z)
        base_xy = (float(sim.d.qpos[0]), float(sim.d.qpos[1]))
        return {
            "t": float(sim.t),
            "tcp_pos_b": pos_b.astype(float).tolist(),
            "tcp_quat_b": quat_b.astype(float).tolist(),
            "tcp_agl_mujoco_m": tcp_agl,
            "base_xy": list(base_xy),
            "arm_q": _arm_q(),
            "ee_pos_err": float(sim.ee.errors(sim.ee_cmd)[0]),
            "ee_ori_err_rad": float(sim.ee.errors(sim.ee_cmd)[1]),
            "path_m": float(sim.path),
        }

    # ################################
    # Ramp toward full EE command (pos hold + target rpy), chassis held.
    # ################################
    target_cmd = ee_command_from_offset(dpos, rpy)
    level_cmd = ee_command_from_offset(dpos, (0.0, 0.0, 0.0))
    for i in range(int(ramp_steps)):
        u = (i + 1) / float(max(1, ramp_steps))
        # Slerp-ish: blend rpy linearly; pos already at hold.
        rpy_u = [rpy[j] * u for j in range(3)]
        sim.set_commands(0.0, 0.0, ee_command_from_offset(dpos, rpy_u))
        sim.step()
        m = _metrics()
        m["phase"] = "ramp"
        m["ee_offset_pos"] = list(dpos)
        m["ee_offset_rpy"] = list(rpy_u)
        log.append(m)

    sim.set_commands(0.0, 0.0, target_cmd)
    for _ in range(int(hold_steps)):
        sim.step()
        m = _metrics()
        m["phase"] = "hold"
        m["ee_offset_pos"] = list(dpos)
        m["ee_offset_rpy"] = list(rpy)
        log.append(m)

    for _ in range(int(settle_steps)):
        sim.step()
        m = _metrics()
        m["phase"] = "settle"
        m["ee_offset_pos"] = list(dpos)
        m["ee_offset_rpy"] = list(rpy)
        log.append(m)

    final = log[-1]
    base0 = log[0]["base_xy"]
    base1 = final["base_xy"]
    drift = float(math.hypot(base1[0] - base0[0], base1[1] - base0[1]))
    rep = {
        "status": "ok",
        "tag": tag,
        "policy": str(ckpt),
        "policy_hz": POLICY_HZ,
        "num_obs": 117,
        "num_actions": 8,
        "obs_history": 3,
        "action_scale": float(ACTION_SCALE),
        "control": {
            "type": "teleop_conditioned_ee_pose",
            "vel_cmd": [0.0, 0.0],
            "ee_offset_pos": list(dpos),
            "ee_offset_rpy": list(rpy),
            "note": (
                "LOOK uses trained teleop-PPO EE orientation; "
                "Z hold keeps raised height. Not gimbal / not IK."
            ),
        },
        "arm_default": [float(x) for x in MJ_ARM_DEFAULT],
        "arm_q_final": final["arm_q"],
        "tcp_agl_mujoco_m": final["tcp_agl_mujoco_m"],
        "tcp_pos_b_final": final["tcp_pos_b"],
        "tcp_quat_b_final": final["tcp_quat_b"],
        "ee_pos_err_final": final["ee_pos_err"],
        "ee_ori_err_deg_final": math.degrees(final["ee_ori_err_rad"]),
        "base_drift_m": drift,
        "path_m": final["path_m"],
        "elapsed_wall_s": time.time() - t0,
        "n_policy_steps": len(log),
        "log_tail": log[-5:],
        "log": log,
        "mujoco_scale": 1.0,
        "habitat_sync": "arm_joints_only",
        "level_ee_cmd_note": "level uses same dpos with rpy=0",
        "level_cmd_dim": int(np.asarray(level_cmd).size),
    }
    return rep


def look_offset_rpy(direction: str, pitch_step_rad: float = LOOK_PITCH_STEP_RAD) -> Tuple[float, float, float]:
    """Map ApexNav LOOK_UP/DOWN to EE pitch offset (roll, pitch, yaw).

    ################################
    Teleop ee_offset pitch sign is opposite Habitat optical +Y-up pitch:
    LOOK_UP (sky / optical+) uses negative ee pitch; LOOK_DOWN uses positive.
    Verified on 0.7× FK: +π/6 ee → optical≈−30°, −π/6 ee → optical≈+30°.
    ################################
    """
    d = str(direction).lower().strip()
    if d in ("up", "look_up", "turn_up"):
        return (0.0, float(-pitch_step_rad), 0.0)
    if d in ("down", "look_down", "turn_down"):
        return (0.0, float(pitch_step_rad), 0.0)
    raise ValueError(f"unknown look direction={direction!r}")


def _mujoco_freejoint_yaw(qpos: np.ndarray) -> float:
    """Yaw about MuJoCo +Z from freejoint quat (wxyz in qpos[3:7])."""
    w, x, y, z = [float(v) for v in qpos[3:7]]
    return float(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


def run_mujoco_chassis_segment(
    *,
    policy: str,
    loco_root: str = LOCOMANIP_REPO,
    vx: float,
    wz: float,
    z_hold: float = Z_OFFSET_MAX,
    target_forward_m: Optional[float] = None,
    target_yaw_rad: Optional[float] = None,
    raise_ramp_steps: int = 20,
    raise_hold_steps: int = 25,
    max_steps: int = 30,
    settle_steps: int = 5,
    tag: str = "chassis_segment",
) -> Dict[str, Any]:
    """Drive teleop-PPO chassis vel_cmd with EE Z hold; return body-frame ΔSE2 samples.

    ################################
    Samples are body-frame relative to segment origin (MuJoCo: +X forward, +Y left):
      d_forward, d_left, d_yaw
    Habitat applies: nx = x + df*sin(yaw) - dl*cos(yaw); nz = z + df*cos(yaw) + dl*sin(yaw).
    Scene collision stays in Habitat probe_base_motion — MuJoCo has no HM3D.
    ################################
    """
    loco = Path(loco_root)
    _ensure_loco_paths(loco)
    import mujoco
    from deploy_mujoco.ranger_cr10.ranger_policy import (  # type: ignore
        ACTION_SCALE,
        ARM_DEFAULT as MJ_ARM_DEFAULT,
        ARM_JOINT_NAMES as MJ_ARM_NAMES,
        STEERING_JOINT_NAMES as MJ_STEER,
        WHEEL_JOINT_NAMES as MJ_WHEEL,
        ee_command_from_offset,
    )
    from deploy_mujoco.ranger_cr10.teleop_eval import Sim  # type: ignore

    ckpt = Path(policy)
    if not ckpt.is_file():
        ckpt = loco / policy
    if not ckpt.is_file():
        raise FileNotFoundError(f"policy missing: {policy}")

    vx = float(vx)
    wz = float(wz)
    z_cmd = float(np.clip(z_hold, 0.0, Z_OFFSET_MAX))
    tgt_fwd = None if target_forward_m is None else float(target_forward_m)
    tgt_yaw = None if target_yaw_rad is None else float(target_yaw_rad)

    filt = _official_base_filter()
    sim = Sim(str(ckpt), filt)
    sim.reset()
    t0 = time.time()
    ee_hold = ee_command_from_offset((0.0, 0.0, z_cmd), (0.0, 0.0, 0.0))

    def _arm_q() -> List[float]:
        q = []
        for name in MJ_ARM_NAMES:
            jid = mujoco.mj_name2id(sim.m, mujoco.mjtObj.mjOBJ_JOINT, name)
            q.append(float(sim.d.qpos[sim.m.jnt_qposadr[jid]]))
        return q

    def _joint_q(names: Sequence[str]) -> List[float]:
        out = []
        for name in names:
            jid = mujoco.mj_name2id(sim.m, mujoco.mjtObj.mjOBJ_JOINT, name)
            out.append(float(sim.d.qpos[sim.m.jnt_qposadr[jid]]) if jid >= 0 else 0.0)
        return out

    def _pose() -> Tuple[float, float, float]:
        return (
            float(sim.d.qpos[0]),
            float(sim.d.qpos[1]),
            _mujoco_freejoint_yaw(sim.d.qpos),
        )

    def _body_delta(x0: float, y0: float, yaw0: float, x: float, y: float, yaw: float) -> Dict[str, float]:
        # MuJoCo world → body at yaw0: +X forward, +Y left
        c, s = math.cos(yaw0), math.sin(yaw0)
        dx, dy = x - x0, y - y0
        d_forward = dx * c + dy * s
        d_left = -dx * s + dy * c
        d_yaw = (yaw - yaw0 + math.pi) % (2.0 * math.pi) - math.pi
        return {
            "d_forward": float(d_forward),
            "d_left": float(d_left),
            "d_yaw": float(d_yaw),
            "path_m": float(math.hypot(dx, dy)),
        }

    # Raise / EE hold with chassis locked (vel_cmd=0).
    for i in range(int(raise_ramp_steps)):
        u = (i + 1) / float(raise_ramp_steps)
        sim.set_commands(0.0, 0.0, ee_command_from_offset((0.0, 0.0, z_cmd * u), (0.0, 0.0, 0.0)))
        sim.step()
    sim.set_commands(0.0, 0.0, ee_hold)
    for _ in range(int(raise_hold_steps)):
        sim.step()

    x0, y0, yaw0 = _pose()
    samples: List[Dict[str, Any]] = []
    stop_reason = "max_steps"
    sim.set_commands(vx, wz, ee_hold)
    for i in range(int(max_steps)):
        sim.step()
        x, y, yaw = _pose()
        delta = _body_delta(x0, y0, yaw0, x, y, yaw)
        samples.append(
            {
                "i": i + 1,
                "t": float(sim.t),
                **delta,
                "arm_q": _arm_q(),
                "steer_q": _joint_q(MJ_STEER),
                "wheel_q": _joint_q(MJ_WHEEL),
            }
        )
        if tgt_fwd is not None and delta["path_m"] >= abs(tgt_fwd):
            stop_reason = "path_target"
            break
        if tgt_yaw is not None and abs(delta["d_yaw"]) >= abs(tgt_yaw):
            stop_reason = "yaw_target"
            break

    # Brake chassis; keep EE hold.
    sim.set_commands(0.0, 0.0, ee_hold)
    for _ in range(int(settle_steps)):
        sim.step()
    x1, y1, yaw1 = _pose()
    final_delta = _body_delta(x0, y0, yaw0, x1, y1, yaw1)
    if samples:
        samples[-1].update(final_delta)
        samples[-1]["arm_q"] = _arm_q()
        samples[-1]["steer_q"] = _joint_q(MJ_STEER)
        samples[-1]["wheel_q"] = _joint_q(MJ_WHEEL)

    rep = {
        "status": "ok",
        "tag": tag,
        "policy": str(ckpt),
        "policy_hz": POLICY_HZ,
        "num_obs": 117,
        "num_actions": 8,
        "action_scale": float(ACTION_SCALE),
        "control": {
            "type": "teleop_conditioned_chassis_vel",
            "vel_cmd": [vx, wz],
            "ee_offset_pos": [0.0, 0.0, z_cmd],
            "ee_offset_rpy": [0.0, 0.0, 0.0],
            "target_forward_m": tgt_fwd,
            "target_yaw_rad": tgt_yaw,
            "stop_reason": stop_reason,
            "note": (
                "Unit chassis segment for ApexNav MOVE/TURN replay; "
                "Habitat applies body-frame delta + probe_base_motion."
            ),
        },
        "frame": {
            "convention": "body_at_segment_origin",
            "mujoco": "+X forward, +Y left, yaw about +Z",
            "habitat_apply": (
                "nx=x+df*sin(yaw)-dl*cos(yaw); "
                "nz=z+df*cos(yaw)+dl*sin(yaw); "
                "nyaw=yaw+d_yaw"
            ),
        },
        "arm_default": [float(x) for x in MJ_ARM_DEFAULT],
        "arm_q_final": _arm_q(),
        "steer_q_final": _joint_q(MJ_STEER),
        "wheel_q_final": _joint_q(MJ_WHEEL),
        "delta_final": final_delta,
        "delta_samples": [
            {k: s[k] for k in ("i", "t", "d_forward", "d_left", "d_yaw", "path_m")}
            for s in samples
        ],
        "path_m": final_delta["path_m"],
        "yaw_delta": final_delta["d_yaw"],
        "n_policy_steps": len(samples),
        "elapsed_wall_s": time.time() - t0,
        "mujoco_scale": 1.0,
        "habitat_sync": "base_delta_se2_plus_arm_wheel",
        "log": samples,
    }
    return rep


def write_orient_report(rep: Dict[str, Any], out: Path) -> Path:
    """Write raise/look JSON + jsonl (log stripped to sidecar)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(rep)
    log = payload.pop("log", [])
    (out.with_suffix(".jsonl")).write_text(
        "\n".join(json.dumps(r) for r in log) + ("\n" if log else "")
    )
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return out


def habitat_tcp_and_camera_metrics(env) -> Dict[str, Any]:
    """FK metrics on Habitat articulations after joint sync."""
    from .initial_camera_pose import optical_metrics

    scale = float(getattr(env, "robot_scale", 1.0))
    floor_y = float(getattr(env, "floor_y", 0.0))
    # TCP: Link6 + scaled offset in link frame
    if TCP_BODY not in env.link_ids:
        raise RuntimeError(f"missing {TCP_BODY}")
    T6 = env.ao.get_link_scene_node(env.link_ids[TCP_BODY]).absolute_transformation()
    # Habitat Y-up; offset is ROS/link local (Z-up URDF). Apply via link rotation.
    import magnum as mn

    off = TCP_OFFSET_POS * scale
    # link local offset expressed in Habitat after URDF→Hab is already in scene node frame
    p6 = np.array([T6.translation.x, T6.translation.y, T6.translation.z], dtype=np.float64)
    R = np.array(T6.rotation(), dtype=np.float64).reshape(3, 3)
    # Magnum Matrix3x3 is column-major list; np reshape matches habitat usage elsewhere
    tcp = p6 + R @ off
    tcp_agl = float(tcp[1] - floor_y)
    cam = optical_metrics(env, env.base_yaw)
    return {
        "tcp_pos_hab": tcp.tolist(),
        "tcp_agl_m": tcp_agl,
        "d455_optical_agl_m": float(cam["height_agl_m"]),
        "d455_pitch_deg": float(cam["pitch_deg"]),
        "d455_yaw_err_deg": float(cam["yaw_err_deg"]),
        "d455_roll_deg": float(cam["roll_deg"]),
        "robot_scale": scale,
        "floor_y": floor_y,
    }


def apply_raise_to_habitat(env, arm_q: Sequence[float]) -> Dict[str, Any]:
    """Handover: set Habitat arm joints from MuJoCo PPO result; freeze chassis."""
    q = np.asarray(arm_q, dtype=np.float64)
    assert q.shape == (6,)
    # ################################
    # Control handoff: PPO done — only write arm; do not touch base SE(2).
    # ################################
    base_before = env.base_xyz.copy()
    yaw_before = float(env.base_yaw)
    env.set_arm_joints(q)
    met = habitat_tcp_and_camera_metrics(env)
    met["base_xyz"] = base_before.tolist()
    met["base_yaw"] = yaw_before
    met["arm_q"] = q.astype(float).tolist()
    met["tcp_target_agl_m"] = EE_TARGET_AGL_M
    met["tcp_tol_m"] = EE_TARGET_TOL_M
    met["tcp_target_ok"] = bool(abs(met["tcp_agl_m"] - EE_TARGET_AGL_M) <= EE_TARGET_TOL_M)
    met["d455_level_ok"] = bool(
        abs(met["d455_pitch_deg"]) <= 5.0
        and abs(met["d455_roll_deg"]) <= 5.0
        and abs(met["d455_yaw_err_deg"]) <= 5.0
    )
    return met


def replay_raise_on_habitat(
    env,
    raise_jsonl: Path,
    *,
    stride: int = 2,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Replay MuJoCo PPO arm trajectory on Habitat (viz + FK); chassis fixed."""
    rows = [json.loads(l) for l in Path(raise_jsonl).read_text().splitlines() if l.strip()]
    if not rows:
        raise RuntimeError(f"empty raise log: {raise_jsonl}")
    out_dir = Path(out_dir) if out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    fk_series = []
    base0 = env.base_xyz.copy()
    for i, r in enumerate(rows[:: max(1, int(stride))]):
        q = r.get("arm_q")
        if not q:
            continue
        env.set_arm_joints(q)
        # ensure base not drifted by wheel viz
        env.base_xyz[:] = base0
        env.base_yaw = float(getattr(env, "base_yaw", 0.0))
        env._apply_state()
        met = habitat_tcp_and_camera_metrics(env)
        met["log_t"] = r.get("t")
        met["phase"] = r.get("phase")
        fk_series.append(met)
        if out_dir is not None and i % 2 == 0:
            try:
                from PIL import Image

                Image.fromarray(env.observe_third_only()[..., :3]).save(
                    out_dir / f"raise_third_{i:04d}.png"
                )
            except Exception:
                pass
    final = apply_raise_to_habitat(env, rows[-1]["arm_q"])
    return {
        "n_replay_frames": len(fk_series),
        "final": final,
        "series_tail": fk_series[-3:],
        "tcp_agl_max_m": max((s["tcp_agl_m"] for s in fk_series), default=None),
        "d455_agl_max_m": max((s["d455_optical_agl_m"] for s in fk_series), default=None),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="MuJoCo teleop-PPO arm raise / LOOK / chassis segments for Habitat sync"
    )
    p.add_argument(
        "--mode",
        choices=(
            "raise",
            "look_up",
            "look_down",
            "look_bundle",
            "chassis_bundle",
            "move_forward",
            "turn_left",
            "turn_right",
        ),
        default="raise",
        help="raise/look_* / chassis unit segments for ApexNav MOVE/TURN",
    )
    p.add_argument("--policy", default=DEFAULT_TELEOP_CKPT)
    p.add_argument("--loco_root", default=LOCOMANIP_REPO)
    p.add_argument("--z_offset", type=float, default=Z_OFFSET_MAX)
    p.add_argument(
        "--z_hold",
        type=float,
        default=Z_OFFSET_MAX,
        help="Z offset held during LOOK/chassis so height stays near raised home",
    )
    p.add_argument("--pitch_step_rad", type=float, default=LOOK_PITCH_STEP_RAD)
    p.add_argument("--hold_steps", type=int, default=40)
    p.add_argument("--ramp_steps", type=int, default=20)
    p.add_argument("--settle_steps", type=int, default=30)
    p.add_argument("--chassis_max_steps", type=int, default=30)
    p.add_argument(
        "--out",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d.json",
    )
    p.add_argument(
        "--out_dir",
        default="",
        help="For look_bundle/chassis_bundle: write segment JSON files here",
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    if args.mode == "raise":
        rep = run_mujoco_raise(
            policy=args.policy,
            loco_root=args.loco_root,
            z_offset=args.z_offset,
            hold_steps=args.hold_steps,
            ramp_steps=args.ramp_steps,
            settle_steps=args.settle_steps,
        )
        write_orient_report(rep, Path(args.out))
        print(json.dumps({k: rep[k] for k in rep if k not in ("log", "log_tail")}, indent=2))
        return 0

    if args.mode == "look_bundle":
        out_dir = Path(args.out_dir or args.out)
        if out_dir.suffix == ".json":
            out_dir = out_dir.parent / "ppo_look_bundle"
        out_dir.mkdir(parents=True, exist_ok=True)
        specs = [
            ("look_level", (0.0, 0.0, 0.0)),
            ("look_up", look_offset_rpy("up", args.pitch_step_rad)),
            ("look_down", look_offset_rpy("down", args.pitch_step_rad)),
        ]
        summary = {"z_hold": float(args.z_hold), "policy": args.policy, "files": {}}
        for name, rpy in specs:
            rep = run_mujoco_ee_orient(
                policy=args.policy,
                loco_root=args.loco_root,
                offset_rpy=rpy,
                z_hold=args.z_hold,
                hold_steps=args.hold_steps,
                ramp_steps=min(args.ramp_steps, 15),
                settle_steps=args.settle_steps,
                tag=name,
            )
            path = write_orient_report(rep, out_dir / f"{name}.json")
            summary["files"][name] = str(path)
            summary[name + "_arm_q"] = rep["arm_q_final"]
            summary[name + "_tcp_agl"] = rep["tcp_agl_mujoco_m"]
        (out_dir / "bundle_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    # ################################
    # Chassis unit segments (ApexNav MOVE/TURN low-level PPO).
    # ################################
    chassis_specs = {
        "move_forward": dict(
            vx=CHASSIS_VX_CMD,
            wz=0.0,
            target_forward_m=CHASSIS_FORWARD_M,
            target_yaw_rad=None,
        ),
        "turn_left": dict(
            vx=0.0,
            wz=CHASSIS_WZ_CMD,
            target_forward_m=None,
            target_yaw_rad=CHASSIS_TURN_RAD,
        ),
        "turn_right": dict(
            vx=0.0,
            wz=-CHASSIS_WZ_CMD,
            target_forward_m=None,
            target_yaw_rad=-CHASSIS_TURN_RAD,
        ),
        # ################################
        # Real reverse unit segment (negative vx). Not negated forward ΔSE2.
        # ################################
        "move_backward": dict(
            vx=-CHASSIS_VX_CMD,
            wz=0.0,
            target_forward_m=CHASSIS_FORWARD_M,
            target_yaw_rad=None,
        ),
    }

    if args.mode == "chassis_bundle":
        out_dir = Path(args.out_dir or args.out)
        if out_dir.suffix == ".json":
            out_dir = out_dir.parent / "ppo_chassis_bundle"
        out_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "z_hold": float(args.z_hold),
            "policy": args.policy,
            "files": {},
            "targets": {
                "forward_m": CHASSIS_FORWARD_M,
                "turn_rad": CHASSIS_TURN_RAD,
                "vx": CHASSIS_VX_CMD,
                "wz": CHASSIS_WZ_CMD,
            },
        }
        for name, kw in chassis_specs.items():
            rep = run_mujoco_chassis_segment(
                policy=args.policy,
                loco_root=args.loco_root,
                z_hold=args.z_hold,
                raise_ramp_steps=min(args.ramp_steps, 20),
                raise_hold_steps=min(args.hold_steps, 25),
                max_steps=args.chassis_max_steps,
                settle_steps=min(args.settle_steps, 5),
                tag=name,
                **kw,
            )
            path = write_orient_report(rep, out_dir / f"{name}.json")
            summary["files"][name] = str(path)
            summary[name + "_path_m"] = rep["path_m"]
            summary[name + "_yaw_delta"] = rep["yaw_delta"]
            summary[name + "_stop"] = rep["control"]["stop_reason"]
        (out_dir / "bundle_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if args.mode in chassis_specs:
        kw = chassis_specs[args.mode]
        rep = run_mujoco_chassis_segment(
            policy=args.policy,
            loco_root=args.loco_root,
            z_hold=args.z_hold,
            raise_ramp_steps=min(args.ramp_steps, 20),
            raise_hold_steps=min(args.hold_steps, 25),
            max_steps=args.chassis_max_steps,
            settle_steps=min(args.settle_steps, 5),
            tag=args.mode,
            **kw,
        )
        write_orient_report(rep, Path(args.out))
        print(json.dumps({k: rep[k] for k in rep if k not in ("log", "log_tail")}, indent=2))
        return 0

    direction = "up" if args.mode == "look_up" else "down"
    rpy = look_offset_rpy(direction, args.pitch_step_rad)
    rep = run_mujoco_ee_orient(
        policy=args.policy,
        loco_root=args.loco_root,
        offset_rpy=rpy,
        z_hold=args.z_hold,
        hold_steps=args.hold_steps,
        ramp_steps=min(args.ramp_steps, 15),
        settle_steps=args.settle_steps,
        tag=args.mode,
    )
    write_orient_report(rep, Path(args.out))
    print(json.dumps({k: rep[k] for k in rep if k not in ("log", "log_tail")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
