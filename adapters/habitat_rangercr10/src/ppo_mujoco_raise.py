"""MuJoCo-native teleop PPO arm raise, then joint sync for Habitat (adapter-only).

################################
Contract (stage410d, unchanged):
  obs=117 hist=3 @10Hz; act=8 = [vx,wz, j1..j6 raw];
  arm targets = ARM_DEFAULT + ACTION_SCALE * raw[2:];
  teleop commands: vel_cmd=(vx,wz), ee_cmd=ee_command_from_offset(dpos, drpy).

Raise uses vx=wz=0 and +Z EE offset (keyboard box). No IK joint targets.
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
    filt = BaseCommandFilter(0.02, 0.02, False, True)
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
    p = argparse.ArgumentParser(description="MuJoCo teleop-PPO arm raise for Habitat sync")
    p.add_argument("--policy", default=DEFAULT_TELEOP_CKPT)
    p.add_argument("--loco_root", default=LOCOMANIP_REPO)
    p.add_argument("--z_offset", type=float, default=Z_OFFSET_MAX)
    p.add_argument("--hold_steps", type=int, default=40)
    p.add_argument("--ramp_steps", type=int, default=20)
    p.add_argument("--settle_steps", type=int, default=30)
    p.add_argument(
        "--out",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d.json",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    rep = run_mujoco_raise(
        policy=args.policy,
        loco_root=args.loco_root,
        z_offset=args.z_offset,
        hold_steps=args.hold_steps,
        ramp_steps=args.ramp_steps,
        settle_steps=args.settle_steps,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # strip full log to sidecar for size
    log = rep.pop("log")
    (out.with_suffix(".jsonl")).write_text("\n".join(json.dumps(r) for r in log) + "\n")
    out.write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: rep[k] for k in rep if k != "log_tail"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
