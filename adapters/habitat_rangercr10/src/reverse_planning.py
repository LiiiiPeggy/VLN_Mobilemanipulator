"""Path-guided reverse (scheme B) and PPO-primitive Hybrid A* (scheme C).

################################
Adapter-only. Does not change ApexNav A*/Frontier/STOP definitions.
Scheme A = off. Planning collision uses online /grid_map clouds only;
Habitat probe may gate execution candidates (scheme B/C commit).
KinoAstar in-tree uses Dubins + non-negative arcs (car model) — unsuitable
for Ranger in-place turn + PPO primitives; scheme C is a small state lattice.
################################
"""

from __future__ import annotations

import heapq
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .ranger_footprint import CHASSIS_HALF_L, CHASSIS_HALF_W, oriented_rect_corners
from .robot_scale import footprint_at_scale

# ################################
# Modes (env / CLI). Default A preserves formal nav config.
# ################################
MODE_A = "A"
MODE_B = "B"
MODE_C = "C"
MODES = (MODE_A, MODE_B, MODE_C)

ACTION_MOVE_FORWARD = 1
ACTION_TURN_LEFT = 2
ACTION_TURN_RIGHT = 3
ACTION_MOVE_BACKWARD = 6  # adapter-only; never published by ApexNav FSM

ACTION_NAME = {
    ACTION_MOVE_FORWARD: "MOVE_FORWARD",
    ACTION_TURN_LEFT: "TURN_LEFT",
    ACTION_TURN_RIGHT: "TURN_RIGHT",
    ACTION_MOVE_BACKWARD: "MOVE_BACKWARD",
}

SEG_BY_ACTION = {
    ACTION_MOVE_FORWARD: "move_forward",
    ACTION_TURN_LEFT: "turn_left",
    ACTION_TURN_RIGHT: "turn_right",
    ACTION_MOVE_BACKWARD: "move_backward",
}


def wrap_pi(a: float) -> float:
    return (float(a) + math.pi) % (2.0 * math.pi) - math.pi


def hab_to_ros(hx: float, hz: float) -> Tuple[float, float]:
    return (-float(hz), -float(hx))


def ros_to_hab(rx: float, ry: float) -> Tuple[float, float]:
    return (-float(ry), -float(rx))


def body_rel_hab(
    hx: float, hz: float, yaw: float, px: float, pz: float
) -> Tuple[float, float, float]:
    """Body-frame (forward, left, bearing) of Habitat (px,pz) vs pose."""
    dx, dz = float(px) - float(hx), float(pz) - float(hz)
    s, c = math.sin(yaw), math.cos(yaw)
    df = dx * s + dz * c
    dl = -dx * c + dz * s
    return df, dl, math.atan2(dl, df)


def apply_body_delta(
    x: float, z: float, yaw: float, d_forward: float, d_left: float, d_yaw: float
) -> Tuple[float, float, float]:
    nx = float(x + d_forward * math.sin(yaw) - d_left * math.cos(yaw))
    nz = float(z + d_forward * math.cos(yaw) + d_left * math.sin(yaw))
    nyaw = float(yaw + d_yaw)
    return nx, nz, nyaw


def path_geometry(
    hx: float,
    hz: float,
    yaw: float,
    selected_path_ros: Sequence[Sequence[float]],
    selected_goal_ros: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Analyze native A* path relative to current Habitat pose."""
    path_hab = [ros_to_hab(float(p[0]), float(p[1])) for p in selected_path_ros if len(p) >= 2]
    look = None
    if len(path_hab) >= 2:
        look = path_hab[1]
    elif path_hab:
        look = path_hab[0]
    goal = None
    if selected_goal_ros is not None and len(selected_goal_ros) >= 2:
        goal = ros_to_hab(float(selected_goal_ros[0]), float(selected_goal_ros[1]))
    elif path_hab:
        goal = path_hab[-1]

    behind = 0
    for ph in path_hab:
        df, _, _ = body_rel_hab(hx, hz, yaw, ph[0], ph[1])
        if df < -0.05:
            behind += 1
    n = max(len(path_hab), 1)
    look_df = look_dl = look_br = None
    if look is not None:
        look_df, look_dl, look_br = body_rel_hab(hx, hz, yaw, look[0], look[1])
    goal_df = goal_dl = goal_br = None
    if goal is not None:
        goal_df, goal_dl, goal_br = body_rel_hab(hx, hz, yaw, goal[0], goal[1])

    path_behind = (behind / float(n)) >= 0.5 or (
        look_df is not None and look_df < 0.05 and abs(look_br or 0.0) > math.radians(70)
    )
    return {
        "n_path": len(path_hab),
        "behind_count": behind,
        "behind_frac": behind / float(n),
        "path_behind": bool(path_behind),
        "look_hab": look,
        "goal_hab": goal,
        "look_df": look_df,
        "look_dl": look_dl,
        "look_bearing_rad": look_br,
        "goal_df": goal_df,
        "goal_dl": goal_dl,
        "goal_bearing_rad": goal_br,
    }


@dataclass
class OnlineOccMap:
    """Occupancy samples from ApexNav /grid_map PointCloud2 (ROS planar)."""

    occ_ros: np.ndarray  # (N,2)
    inflate_ros: np.ndarray
    free_ros: np.ndarray
    robot_scale: float = 0.7
    clearance_m: float = 0.05

    @classmethod
    def from_map_listener(cls, map_listener: Any, robot_scale: float = 0.7) -> "OnlineOccMap":
        from .map_listener import _cloud_xy

        clouds = getattr(map_listener, "clouds", {}) or {}

        def _xy(key: str) -> np.ndarray:
            msg = clouds.get(key)
            if msg is None:
                return np.zeros((0, 2), dtype=np.float64)
            try:
                arr = _cloud_xy(msg)
            except Exception:
                return np.zeros((0, 2), dtype=np.float64)
            if arr is None or len(arr) == 0:
                return np.zeros((0, 2), dtype=np.float64)
            return np.asarray(arr[:, :2], dtype=np.float64)

        return cls(
            occ_ros=_xy("occupied"),
            inflate_ros=_xy("occupied_inflate"),
            free_ros=_xy("free"),
            robot_scale=float(robot_scale),
        )

    def has_data(self) -> bool:
        return int(self.occ_ros.shape[0]) + int(self.inflate_ros.shape[0]) > 0

    def _half(self) -> Tuple[float, float]:
        fp = footprint_at_scale(self.robot_scale)
        return float(fp["chassis_half_length_m"]), float(fp["chassis_half_width_m"])

    def footprint_clear_hab(self, x: float, z: float, yaw: float) -> bool:
        """True if oriented chassis corners are away from online occupied(+inflate)."""
        if not self.has_data():
            # ################################
            # No online map yet: do not invent free space; defer to exec probe.
            # ################################
            return True
        half_l, half_w = self._half()
        corners = oriented_rect_corners(x, z, yaw, half_l=half_l, half_w=half_w)
        # also center + rear/front mid
        samples = [hab_to_ros(float(x), float(z))]
        for cx, cz in corners:
            samples.append(hab_to_ros(float(cx), float(cz)))
        obs = self.inflate_ros if self.inflate_ros.shape[0] else self.occ_ros
        if obs.shape[0] == 0:
            return True
        pts = np.asarray(samples, dtype=np.float64)
        # brute min dist (N small)
        d2 = ((pts[:, None, :] - obs[None, :, :]) ** 2).sum(axis=2)
        min_d = float(np.sqrt(d2.min()))
        return min_d >= float(self.clearance_m)


@dataclass
class ReversePlannerState:
    mode: str = MODE_A
    n_reverse_actions: int = 0
    sum_reverse_m: float = 0.0
    n_gear_switches: int = 0
    n_hybrid_calls: int = 0
    n_hybrid_fail: int = 0
    n_path_guided_reverse: int = 0
    n_recovery_oscillation: int = 0
    last_gear: str = "forward"  # forward|reverse
    consec_reverse: int = 0
    max_reverse_actions: int = 8
    max_sum_reverse_m: float = 1.6
    max_consec_reverse: int = 3
    blocked_turn_streak: int = 0
    last_turn_blocked: bool = False
    pending_hybrid_actions: List[int] = field(default_factory=list)
    planner_paths_log: List[Dict[str, Any]] = field(default_factory=list)

    def can_reverse(self) -> bool:
        return (
            self.n_reverse_actions < self.max_reverse_actions
            and self.sum_reverse_m < self.max_sum_reverse_m
            and self.consec_reverse < self.max_consec_reverse
        )


def segment_delta(seg: Optional[dict]) -> Tuple[float, float, float]:
    if not seg:
        return 0.0, 0.0, 0.0
    d = seg.get("delta_final") or {}
    return (
        float(d.get("d_forward", 0.0)),
        float(d.get("d_left", 0.0)),
        float(d.get("d_yaw", 0.0)),
    )


def predict_pose_after(
    x: float, z: float, yaw: float, action: int, segments: Dict[str, dict]
) -> Tuple[float, float, float]:
    name = SEG_BY_ACTION.get(action)
    df, dl, dy = segment_delta(segments.get(name or "", {}))
    if name == "move_backward" and abs(df) < 1e-6:
        # missing calibrated reverse — refuse prediction
        return x, z, yaw
    return apply_body_delta(x, z, yaw, df, dl, dy)


# ################################
# Scheme B: path-guided reverse decision
# ################################


def scheme_b_should_reverse(
    *,
    state: ReversePlannerState,
    requested_action: int,
    path_geom: Dict[str, Any],
    blocked_turn_streak: int,
    min_blocked_turns: int = 2,
) -> Tuple[bool, str]:
    if state.mode != MODE_B:
        return False, "mode_not_B"
    if not state.can_reverse():
        return False, "reverse_budget_exhausted"
    if ACTION_MOVE_BACKWARD not in (
        ACTION_MOVE_BACKWARD,
    ):
        pass
    turn = requested_action in (ACTION_TURN_LEFT, ACTION_TURN_RIGHT)
    behind = bool(path_geom.get("path_behind"))
    look_df = path_geom.get("look_df")
    if turn and blocked_turn_streak >= min_blocked_turns and behind:
        return True, "blocked_turn_and_path_behind"
    if turn and blocked_turn_streak >= (min_blocked_turns + 1):
        # even without clear behind flag, repeated unexecutable turns near wall
        if look_df is not None and look_df < 0.15:
            return True, "repeated_blocked_turn_near_side_target"
    if behind and requested_action == ACTION_MOVE_FORWARD and blocked_turn_streak >= 1:
        return True, "forward_while_path_behind_after_block"
    return False, "no_trigger"


def scheme_b_decide(
    *,
    state: ReversePlannerState,
    x: float,
    z: float,
    yaw: float,
    requested_action: int,
    path_geom: Dict[str, Any],
    segments: Dict[str, dict],
    occ: Optional[OnlineOccMap],
    blocked_turn_streak: int,
) -> Optional[Dict[str, Any]]:
    ok, reason = scheme_b_should_reverse(
        state=state,
        requested_action=requested_action,
        path_geom=path_geom,
        blocked_turn_streak=blocked_turn_streak,
    )
    if not ok:
        return None
    if "move_backward" not in segments:
        return {
            "override_action": None,
            "accepted": False,
            "reason": "missing_move_backward_segment",
            "trigger": reason,
        }
    nx, nz, nyaw = predict_pose_after(x, z, yaw, ACTION_MOVE_BACKWARD, segments)
    # progress: after reverse, local look should become less extreme or goal closer in body-x
    look = path_geom.get("look_hab")
    progress = True
    if look is not None:
        df0 = path_geom.get("look_df") or 0.0
        df1, _, _ = body_rel_hab(nx, nz, nyaw, look[0], look[1])
        # backing away from wall toward path usually increases |path alignment| or reduces
        # absolute side bearing magnitude — accept if look_df increases (less behind)
        # or distance to look decreases.
        dist0 = math.hypot((look[0] - x), (look[1] - z))
        dist1 = math.hypot((look[0] - nx), (look[1] - nz))
        progress = (df1 > df0 - 0.02) or (dist1 + 0.02 < dist0)
    map_ok = True
    if occ is not None and occ.has_data():
        map_ok = occ.footprint_clear_hab(nx, nz, nyaw)
    if not map_ok or not progress:
        return {
            "override_action": None,
            "accepted": False,
            "reason": "unsafe_or_no_progress",
            "trigger": reason,
            "map_ok": map_ok,
            "progress": progress,
            "pred_pose": {"x": nx, "z": nz, "yaw": nyaw},
        }
    return {
        "override_action": ACTION_MOVE_BACKWARD,
        "accepted": True,
        "reason": "path_guided_reverse",
        "trigger": reason,
        "pred_pose": {"x": nx, "z": nz, "yaw": nyaw},
        "path_geom": {
            k: path_geom[k]
            for k in (
                "path_behind",
                "behind_frac",
                "look_df",
                "look_dl",
                "goal_df",
            )
            if k in path_geom
        },
    }


# ################################
# Scheme C: PPO-primitive Hybrid A* / state lattice
# ################################


@dataclass(order=True)
class _HQ:
    f: float
    idx: int


def hybrid_astar_ppo(
    *,
    start: Tuple[float, float, float],
    goal_xy: Tuple[float, float],
    segments: Dict[str, dict],
    occ: Optional[OnlineOccMap],
    max_expansions: int = 400,
    xy_res: float = 0.15,
    yaw_res: float = math.radians(30),
    reverse_cost: float = 1.15,
    switch_cost: float = 0.40,
    goal_tol_m: float = 0.35,
    turn_penalty: float = 0.0,
    prefer_reverse_first: bool = False,
) -> Dict[str, Any]:
    """Search SE(2) with discrete PPO MOVE/TURN/BACK primitives.

    Returns action sequence (ints) from start toward goal_xy.
    """
    t0 = time.time()
    sx, sz, syaw = start
    gx, gz = goal_xy

    def key(x: float, z: float, yaw: float, gear: int) -> Tuple[int, int, int, int]:
        return (
            int(round(x / xy_res)),
            int(round(z / xy_res)),
            int(round(wrap_pi(yaw) / yaw_res)),
            int(gear),
        )

    actions = [
        ACTION_MOVE_FORWARD,
        ACTION_MOVE_BACKWARD,
        ACTION_TURN_LEFT,
        ACTION_TURN_RIGHT,
    ]
    # require segments
    for a in actions:
        if SEG_BY_ACTION[a] not in segments and a != ACTION_MOVE_BACKWARD:
            return {
                "ok": False,
                "reason": f"missing_segment_{SEG_BY_ACTION[a]}",
                "actions": [],
                "path": [],
                "planning_time_s": time.time() - t0,
            }
    if ACTION_MOVE_BACKWARD in actions and "move_backward" not in segments:
        actions = [a for a in actions if a != ACTION_MOVE_BACKWARD]
    # ################################
    # When turns are known-blocked near wall, expand reverse first.
    # ################################
    if prefer_reverse_first and ACTION_MOVE_BACKWARD in actions:
        actions = [ACTION_MOVE_BACKWARD] + [
            a for a in actions if a != ACTION_MOVE_BACKWARD
        ]

    open_h: List[_HQ] = []
    idx = 0
    start_k = key(sx, sz, syaw, 1)
    g_score = {start_k: 0.0}
    parent: Dict[
        Tuple[int, int, int, int],
        Tuple[Tuple[int, int, int, int], int, Tuple[float, float, float]],
    ] = {}
    pose_of = {start_k: (sx, sz, syaw)}
    heapq.heappush(open_h, _HQ(math.hypot(sx - gx, sz - gz), idx))
    open_keys = {start_k: idx}
    key_by_idx = {idx: start_k}
    idx += 1
    expansions = 0
    best_goal_key = None
    # ################################
    # Do not accept the start pose as a solved goal (would yield empty actions).
    # ################################
    start_dist = math.hypot(sx - gx, sz - gz)

    while open_h and expansions < max_expansions:
        item = heapq.heappop(open_h)
        k = key_by_idx.get(item.idx)
        if k is None:
            continue
        if open_keys.get(k) != item.idx:
            continue
        x, z, yaw = pose_of[k]
        gear = k[3]
        dist_g = math.hypot(x - gx, z - gz)
        if dist_g <= goal_tol_m and k != start_k:
            best_goal_key = k
            break
        # If start already inside tol, still expand at least once for escape.
        if dist_g <= goal_tol_m and k == start_k and expansions > 0:
            pass
        expansions += 1
        for a in actions:
            nx, nz, nyaw = predict_pose_after(x, z, yaw, a, segments)
            if occ is not None and occ.has_data():
                if not occ.footprint_clear_hab(nx, nz, nyaw):
                    continue
            new_gear = -1 if a == ACTION_MOVE_BACKWARD else 1
            # turns keep gear
            if a in (ACTION_TURN_LEFT, ACTION_TURN_RIGHT):
                new_gear = gear
            nk = key(nx, nz, nyaw, new_gear)
            step_cost = 1.0
            df, dl, dy = segment_delta(segments.get(SEG_BY_ACTION[a], {}))
            step_cost = max(0.05, math.hypot(df, dl) + 0.15 * abs(dy))
            if a == ACTION_MOVE_BACKWARD:
                step_cost *= reverse_cost
            if a in (ACTION_TURN_LEFT, ACTION_TURN_RIGHT) and turn_penalty > 0:
                step_cost += float(turn_penalty)
            if new_gear != gear and a in (ACTION_MOVE_FORWARD, ACTION_MOVE_BACKWARD):
                step_cost += switch_cost
            # clearance soft cost via free proximity is omitted (online free sparse)
            tentative = g_score[k] + step_cost
            if nk not in g_score or tentative < g_score[nk] - 1e-9:
                g_score[nk] = tentative
                parent[nk] = (k, a, (nx, nz, nyaw))
                pose_of[nk] = (nx, nz, nyaw)
                f = tentative + math.hypot(nx - gx, nz - gz)
                open_keys[nk] = idx
                key_by_idx[idx] = nk
                heapq.heappush(open_h, _HQ(f, idx))
                idx += 1

    planning_time = time.time() - t0
    if best_goal_key is None:
        # take closest expanded to goal
        if not pose_of:
            return {
                "ok": False,
                "reason": "no_expansion",
                "actions": [],
                "path": [],
                "planning_time_s": planning_time,
                "expansions": expansions,
            }
        best_goal_key = min(
            pose_of.keys(),
            key=lambda kk: math.hypot(pose_of[kk][0] - gx, pose_of[kk][1] - gz),
        )
        px, pz, _ = pose_of[best_goal_key]
        if math.hypot(px - gx, pz - gz) > 2.5:
            return {
                "ok": False,
                "reason": "no_path",
                "actions": [],
                "path": [],
                "planning_time_s": planning_time,
                "expansions": expansions,
            }

    # reconstruct
    acts: List[int] = []
    path: List[Tuple[float, float, float]] = []
    cur = best_goal_key
    while cur in parent:
        pk, a, pose = parent[cur]
        acts.append(a)
        path.append(pose)
        cur = pk
    acts.reverse()
    path.reverse()
    return {
        "ok": bool(acts),
        "reason": "ok" if acts else "empty",
        "actions": acts[:12],  # bounded horizon; replan each step
        "path": [{"x": p[0], "z": p[1], "yaw": p[2]} for p in path[:12]],
        "planning_time_s": planning_time,
        "expansions": expansions,
        "note": "PPO state-lattice Hybrid A*; not Reeds-Shepp / not KinoAstar car model",
    }


def scheme_c_decide(
    *,
    state: ReversePlannerState,
    x: float,
    z: float,
    yaw: float,
    requested_action: int,
    path_geom: Dict[str, Any],
    segments: Dict[str, dict],
    occ: Optional[OnlineOccMap],
    blocked_turn_streak: int,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    if state.mode != MODE_C:
        return None
    # Consume pending hybrid actions first (after previous commit).
    if state.pending_hybrid_actions:
        a = int(state.pending_hybrid_actions.pop(0))
        return {
            "override_action": a,
            "accepted": True,
            "reason": "hybrid_pending",
            "hybrid_queue_left": len(state.pending_hybrid_actions),
        }

    need = force or (
        blocked_turn_streak >= 2
        or bool(path_geom.get("path_behind"))
        or (
            requested_action in (ACTION_TURN_LEFT, ACTION_TURN_RIGHT)
            and blocked_turn_streak >= 1
            and (path_geom.get("look_df") is not None and path_geom["look_df"] < 0.1)
        )
    )
    if not need:
        return None

    # ################################
    # Prefer distant A* goal when local look is beside/behind (stuck near wall).
    # ################################
    goal = path_geom.get("goal_hab") or path_geom.get("look_hab")
    look = path_geom.get("look_hab")
    if goal is None:
        state.n_hybrid_fail += 1
        return {
            "override_action": None,
            "accepted": False,
            "reason": "no_goal_for_hybrid",
        }
    if look is not None and path_geom.get("path_behind"):
        # keep goal at path end; look is only for progress heuristics
        pass

    state.n_hybrid_calls += 1
    turn_pen = 0.0
    prefer_rev = False
    if blocked_turn_streak >= 2 or path_geom.get("path_behind"):
        turn_pen = 1.25 + 0.35 * float(blocked_turn_streak)
        prefer_rev = True
    res = hybrid_astar_ppo(
        start=(x, z, yaw),
        goal_xy=(float(goal[0]), float(goal[1])),
        segments=segments,
        occ=occ,
        goal_tol_m=0.45,
        turn_penalty=turn_pen,
        prefer_reverse_first=prefer_rev,
    )
    # ################################
    # If search collapses (already near subgoal) but path is behind / turns fail,
    # seed a reverse then replan-friendly turn toward goal bearing.
    # ################################
    if (not res.get("ok") or not res.get("actions")) and state.can_reverse():
        if "move_backward" in segments and (
            path_geom.get("path_behind") or blocked_turn_streak >= 2
        ):
            gdf = path_geom.get("goal_df")
            gdl = path_geom.get("goal_dl") or 0.0
            seed = [ACTION_MOVE_BACKWARD]
            # after backing, prefer turn toward goal lateral side
            if gdl is not None and abs(float(gdl)) > 0.05:
                seed.append(
                    ACTION_TURN_LEFT if float(gdl) > 0 else ACTION_TURN_RIGHT
                )
            res = {
                "ok": True,
                "reason": "seed_reverse_escape",
                "actions": seed,
                "path": [],
                "planning_time_s": float(res.get("planning_time_s") or 0.0),
                "expansions": int(res.get("expansions") or 0),
                "note": "fallback seed when lattice returns empty near wall",
            }
    entry = {
        "stamp": time.time(),
        "kind": "hybrid_astar_ppo",
        "ok": res.get("ok"),
        "reason": res.get("reason"),
        "n_actions": len(res.get("actions") or []),
        "planning_time_s": res.get("planning_time_s"),
        "expansions": res.get("expansions"),
        "path": res.get("path"),
        "actions": [ACTION_NAME.get(a, str(a)) for a in (res.get("actions") or [])],
        "start": {"x": x, "z": z, "yaw": yaw},
        "goal_hab": {"x": float(goal[0]), "z": float(goal[1])},
    }
    state.planner_paths_log.append(entry)

    if not res.get("ok") or not res.get("actions"):
        state.n_hybrid_fail += 1
        return {
            "override_action": None,
            "accepted": False,
            "reason": res.get("reason") or "hybrid_fail",
            "planning_time_s": res.get("planning_time_s"),
        }

    acts = [int(a) for a in res["actions"]]
    # ################################
    # Near-wall escape: if lattice still starts with turn/forward while path is
    # behind / turns blocked, prepend a verified reverse primitive.
    # ################################
    if (
        prefer_rev
        and state.can_reverse()
        and "move_backward" in segments
        and acts
        and acts[0] != ACTION_MOVE_BACKWARD
        and (path_geom.get("path_behind") or blocked_turn_streak >= 2)
    ):
        acts = [ACTION_MOVE_BACKWARD] + acts
        res = dict(res)
        res["reason"] = str(res.get("reason")) + "+prepend_reverse"
    first = acts[0]
    state.pending_hybrid_actions = acts[1:]
    return {
        "override_action": first,
        "accepted": True,
        "reason": "hybrid_astar_ppo",
        "planning_time_s": res.get("planning_time_s"),
        "hybrid_path": res.get("path"),
        "hybrid_actions": [ACTION_NAME.get(a, str(a)) for a in acts],
        "note": res.get("note"),
    }


def update_after_exec(
    state: ReversePlannerState,
    *,
    actual_action: str,
    moved_m: Optional[float],
    ppo_delta: Optional[Dict[str, Any]],
) -> None:
    name = (actual_action or "").upper()
    is_rev = "BACKWARD" in name or (
        ppo_delta is not None and float(ppo_delta.get("d_forward") or 0.0) < -0.05
    )
    is_fwd = name.startswith("MOVE_FORWARD") or (
        ppo_delta is not None and float(ppo_delta.get("d_forward") or 0.0) > 0.05
    )
    if is_rev:
        df = abs(float((ppo_delta or {}).get("d_forward") or moved_m or 0.0))
        state.n_reverse_actions += 1
        state.sum_reverse_m += df
        state.consec_reverse += 1
        state.n_path_guided_reverse += 1
        if state.last_gear == "forward":
            state.n_gear_switches += 1
        state.last_gear = "reverse"
    else:
        state.consec_reverse = 0
        if is_fwd:
            if state.last_gear == "reverse":
                state.n_gear_switches += 1
            state.last_gear = "forward"

    # oscillation: reverse then immediate opposite reverse request patterns tracked externally


def write_planner_paths_jsonl(path: Path, state: ReversePlannerState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in state.planner_paths_log:
            f.write(json.dumps(row) + "\n")
    state.planner_paths_log.clear()
