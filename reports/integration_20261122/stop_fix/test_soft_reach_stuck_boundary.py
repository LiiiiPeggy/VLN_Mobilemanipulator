#!/usr/bin/env python3
"""Boundary check mirroring exploration_fsm soft_reach stuck (yaw-aware candidate).

This is NOT a separate planner: thresholds match FSMConstants /
callActionPlanner soft_reach block. Run: python3 test_soft_reach_stuck_boundary.py
"""
import math
import sys

ACTION_ANGLE = math.pi / 6.0
STUCKING_DISTANCE = 0.05
SOFT_REACH_DISTANCE = 0.45
REACH_DISTANCE = 0.20
YAW_STUCK_THRESH = ACTION_ANGLE * 0.5

STOP, MOVE_FORWARD, TURN_LEFT, TURN_RIGHT, TURN_DOWN, TURN_UP = range(6)


def wrap(dyaw: float) -> float:
    while dyaw > math.pi:
        dyaw -= 2 * math.pi
    while dyaw < -math.pi:
        dyaw += 2 * math.pi
    return dyaw


def soft_reach_stuck(last_action, dxy, dyaw, any_stuck: bool) -> bool:
    pose_stuck = abs(dxy) < STUCKING_DISTANCE
    yaw_stuck = abs(wrap(dyaw)) < YAW_STUCK_THRESH
    if last_action == MOVE_FORWARD:
        return pose_stuck
    if any_stuck and last_action in (TURN_LEFT, TURN_RIGHT):
        return yaw_stuck
    return False  # LOOK / other


def soft_reach_fire(search, dist_next, last_action, dxy, dyaw, any_stuck, escape=False):
    if escape or not search:
        return False
    if dist_next >= SOFT_REACH_DISTANCE or dist_next < REACH_DISTANCE:
        # hard reach is separate; soft gate only in [REACH, SOFT)
        # (hard handled elsewhere; soft may also cover <soft including <hard)
        pass
    if dist_next >= SOFT_REACH_DISTANCE:
        return False
    return soft_reach_stuck(last_action, dxy, dyaw, any_stuck)


def main():
    cases = [
        # name, search, dist, action, dxy, dyaw, any, expect
        ("A normal turn done", True, 0.25, TURN_RIGHT, 0.0, -ACTION_ANGLE, True, False),
        ("B normal LOOK XY idle", True, 0.25, TURN_DOWN, 0.0, 0.0, True, False),
        ("C obstructed turn", True, 0.25, TURN_RIGHT, 0.0, 0.0, True, True),
        ("D MOVE XY stuck", True, 0.25, MOVE_FORWARD, 0.0, 0.0, True, True),
        ("E EXPLORE no fire", False, 0.25, TURN_RIGHT, 0.0, 0.0, True, False),
        ("F beyond soft", True, 0.50, TURN_RIGHT, 0.0, 0.0, True, False),
        ("G legacy OFF successful turn", True, 0.25, TURN_RIGHT, 0.0, 0.0, False, False),
        ("H legacy OFF MOVE stuck", True, 0.25, MOVE_FORWARD, 0.0, 0.0, False, True),
        ("I truncated small yaw", True, 0.25, TURN_RIGHT, 0.0, math.radians(5), True, True),
        ("J hy1 published false+ (success turn)", True, 0.25, TURN_RIGHT, 0.0, -ACTION_ANGLE, True, False),
    ]
    failed = []
    for name, search, dist, act, dxy, dyaw, any_stuck, expect in cases:
        got = soft_reach_fire(search, dist, act, dxy, dyaw, any_stuck)
        ok = got == expect
        print(f"{'OK' if ok else 'FAIL'}  {name}: got={got} expect={expect}")
        if not ok:
            failed.append(name)
    if failed:
        print("FAILED:", failed)
        return 1
    print("all boundary cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
