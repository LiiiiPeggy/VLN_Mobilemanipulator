"""Pinned versions and frame/joint constants for RangerBox-CR10 Habitat adapter.

Sources (do not invent numbers):
- LocoManip_Lab branch `rangercr10-teleop`
- `mujoco/deploy/deploy_mujoco/ranger_cr10/ranger_policy.py`
- URDF `rangerboxcr10lidar_description/urdf/rangercr10lidar.urdf`
"""

from __future__ import annotations

# ---- pinned upstream ----
LOCOMANIP_REPO = "/home/ubuntu/locomani/LocoManip_Lab"
LOCOMANIP_BRANCH = "rangercr10-teleop"
# PPO weight pin remains stage45j (do NOT swap until new PPO validated separately).
LOCOMANIP_COMMIT = "1973cb4f0d418af6bbf9c92156d55423b98a4963"
DEFAULT_TELEOP_CKPT = (
    "logs/rsl_rl/ranger_cr10_teleop/2026-10-29_19-12-08_stage45j_ppo/model_5999.pt"
)
# ################################
# Read-only kinematics snapshot from LocoManip HEAD (arm defaults / stage 4.10 intent).
# Not a weight pin. Training may still be in progress on HEAD.
# ################################
LOCOMANIP_HEAD_READ = "b0a536f60e6a8c1443a3a10bb4efea1505ef810a"
LOCOMANIP_ARM_SOURCE = (
    "ranger_policy.py ARM_DEFAULT + ranger_cr10_articulation_cfg init_state"
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
# ################################
# LocoManip stage-4.10 default (read-only from HEAD @ LOCOMANIP_HEAD_READ).
# Intent: tool/TCP forward along base +X at ~0.88 m AGL. D455 optical is ~7–8 cm
# below Link6 → measured optical AGL ≈0.78 m with near-zero pitch/yaw/roll.
# Prefer this over joint-search poses that meet 0.88 numerically but look unnatural.
# ################################
ARM_DEFAULT = (0.511, 0.494, -2.449, -1.186, -1.060, 0.0)
ARM_APEXNAV_INIT = ARM_DEFAULT
# Kept for regression compare only (pre-4.10 teleop home; optical pitch ~−76°).
ARM_DEFAULT_LEGACY = (0.6, 1.0, -2.4, 0.0, 1.4, 0.0)
# Prior search pose (height-chasing); retained for diagnostics, not episode default.
ARM_APEXNAV_INIT_SEARCH = (
    -1.6281021987682385,
    0.9056818874307258,
    0.47897782244727727,
    2.0442570619462734,
    -3.140000104904175,
    0.21061755241064453,
)
APEXNAV_CAM_HEIGHT_M = 0.88
# Optical vs TCP: allow wider band until mount offset is modeled in acceptance.
APEXNAV_CAM_HEIGHT_TOL_M = 0.12
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
