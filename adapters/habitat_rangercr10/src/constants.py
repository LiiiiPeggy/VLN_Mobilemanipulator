"""Pinned versions and frame/joint constants for RangerBox-CR10 Habitat adapter.

Sources (do not invent numbers):
- LocoManip_Lab branch `rangercr10-teleop` @ 1973cb4
- `mujoco/deploy/deploy_mujoco/ranger_cr10/ranger_policy.py`
- URDF `rangerboxcr10lidar_description/urdf/rangercr10lidar.urdf`
"""

from __future__ import annotations

# ---- pinned upstream ----
LOCOMANIP_REPO = "/home/ubuntu/locomani/LocoManip_Lab"
LOCOMANIP_BRANCH = "rangercr10-teleop"
LOCOMANIP_COMMIT = "1973cb4f0d418af6bbf9c92156d55423b98a4963"
DEFAULT_TELEOP_CKPT = (
    "logs/rsl_rl/ranger_cr10_teleop/2026-10-29_19-12-08_stage45j_ppo/model_5999.pt"
)

# ---- Habitat target ----
HABITAT_SIM_VERSION = "0.3.1"
REQUIRES_BULLET = True

# ---- paths on shared disk / mounts ----
URDF_HABITAT = "/media/ubuntu/D/VLN_shared/robots/rangercr10/rangercr10lidar_habitat.urdf"
DEFAULT_SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/"
    "00800-TEEsavR23oF/TEEsavR23oF.basis.glb"
)
DEFAULT_OUT_DIR = "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10"

# ---- joints / pose (from ranger_policy.py) ----
ARM_JOINT_NAMES = [f"cr10_joint{i}" for i in range(1, 7)]
STEERING_JOINT_NAMES = [
    "fr_steering_joint",
    "fl_steering_wheel_joint",
    "rl_steering_wheel_joint",
    "rr_steering_wheel_joint",
]
WHEEL_JOINT_NAMES = ["fr_wheel_joint", "fl_wheel_joint", "rl_wheel_joint", "rr_wheel_joint"]
# Teleop / MuJoCo home (NOT ApexNav camera height)
ARM_DEFAULT = (0.6, 1.0, -2.4, 0.0, 1.4, 0.0)
# ################################
# ApexNav-compatible init: D455 optical ~0.88 m AGL, horizontal forward (URDF FK).
# Re-derived 2026-11-03 AFTER Z-up→Y-up root fix (Ry(-90)*Rx(-90)).
# Verified AGL≈0.894 m, |pitch/yaw/roll|<5°. Do NOT forge Habitat Agent pose.
# ################################
ARM_APEXNAV_INIT = (
    -1.6281021987682385,
    0.9056818874307258,
    0.47897782244727727,
    2.0442570619462734,
    -3.140000104904175,
    0.21061755241064453,
)
APEXNAV_CAM_HEIGHT_M = 0.88
APEXNAV_CAM_HEIGHT_TOL_M = 0.02
APEXNAV_CAM_ANGLE_TOL_DEG = 5.0

# Camera / TCP frames
CAMERA_LINK = "d455_depth_optical_frame"
TCP_BODY = "cr10_Link6"
BASE_LINK = "base_link"

# D455 depth optical typically: Habitat camera looks along -Z; optical frame looks along +Z.
# We place the Agent sensor at the optical link and apply a Magnum rotation if needed.
EE_RGB_HFOV_DEG = 79.0
EE_RGB_RES = (480, 640)  # H, W
# ################################
# Higher third-person res for 16:9 paper-style demo upscale (does not affect EE/planner).
# ################################
THIRD_RGB_RES = (720, 1280)

# Policy interface (MuJoCo / Isaac teleop)
NUM_OBS = 117
NUM_ACTIONS = 8
OBS_HISTORY = 3
POLICY_HZ = 10.0
ACTION_SCALE = 0.25

# Control-mode labels used in reports (do not blur these)
MODE_KINEMATIC = "kinematic_state_set"
MODE_PHYSICS = "bullet_physics_step"
MODE_COLLISION_QUERY = "contact_query_only"
