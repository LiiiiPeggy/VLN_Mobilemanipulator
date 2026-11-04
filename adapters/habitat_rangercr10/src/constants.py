"""Pinned versions and frame/joint constants for RangerBox-CR10 Habitat adapter.

Sources (do not invent numbers):
- LocoManip_Lab branch `rangercr10-teleop`
- stage 4.10d: commit `ec5fd65`, policy `stage410d_ppo/model_5999.pt`
- URDF `rangerboxcr10lidar_description/urdf/rangercr10lidar.urdf` (D455 top mount)
"""

from __future__ import annotations

# ---- pinned upstream ----
LOCOMANIP_REPO = "/home/ubuntu/locomani/LocoManip_Lab"
LOCOMANIP_BRANCH = "rangercr10-teleop"
# ################################
# Stage 4.10d pin (URDF + ARM_DEFAULT + PPO). Do NOT mix with stage45j side-mount URDF.
# Historical stage45j kept for comparison only (DEFAULT_TELEOP_CKPT_LEGACY).
# ################################
LOCOMANIP_COMMIT = "ec5fd6584bd3d562812c12ef2d8e2f87fba98175"
LOCOMANIP_HEAD_READ = "2d6d1f526c32b0f2965fdf624840155cf96ad586"
LOCOMANIP_ARM_SOURCE = (
    "ranger_policy.py ARM_DEFAULT + ranger_cr10_articulation_cfg init_state (stage 4.10)"
)
DEFAULT_TELEOP_CKPT = (
    "logs/rsl_rl/ranger_cr10_teleop/2026-11-03_16-30-44_stage410d_ppo/model_5999.pt"
)
DEFAULT_TELEOP_CKPT_LEGACY_STAGE45J = (
    "logs/rsl_rl/ranger_cr10_teleop/2026-10-29_19-12-08_stage45j_ppo/model_5999.pt"
)

# ---- Habitat target ----
HABITAT_SIM_VERSION = "0.3.1"
REQUIRES_BULLET = True

# ---- paths on shared disk / mounts ----
# Versioned URDF (absolute mesh paths under D disk); habitat.urdf is a copy of this pin.
URDF_HABITAT = (
    "/media/ubuntu/D/VLN_shared/robots/rangercr10/"
    "rangercr10lidar_habitat_stage410d_ec5fd65.urdf"
)
URDF_HABITAT_PIN = "stage410d_ec5fd65"
DEFAULT_SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/"
    "00800-TEEsavR23oF/TEEsavR23oF.basis.glb"
)
DEFAULT_OUT_DIR = "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10"

# ---- joints / pose (from ranger_policy.py stage 4.10) ----
ARM_JOINT_NAMES = [f"cr10_joint{i}" for i in range(1, 7)]
STEERING_JOINT_NAMES = [
    "fr_steering_joint",
    "fl_steering_wheel_joint",
    "rl_steering_wheel_joint",
    "rr_steering_wheel_joint",
]
WHEEL_JOINT_NAMES = ["fr_wheel_joint", "fl_wheel_joint", "rl_wheel_joint", "rr_wheel_joint"]
# ################################
# Stage 4.10 default: tool along base +X; D455 remounted ON TOP of AG95.
# LocoManip reports D455 centre ~0.88 m AGL with optical along base +X.
# ################################
ARM_DEFAULT = (0.236, 0.086, -2.398, -0.830, -1.335, 0.0)
ARM_APEXNAV_INIT = ARM_DEFAULT
# Pre-4.10 intermediate default (side-mount era); diagnostics only.
ARM_DEFAULT_410_INTERMEDIATE = (0.511, 0.494, -2.449, -1.186, -1.060, 0.0)
# Pre-4.10 teleop home (optical pitch ~−76° with old mount).
ARM_DEFAULT_LEGACY = (0.6, 1.0, -2.4, 0.0, 1.4, 0.0)
# Height-chasing search pose (diagnostics only).
ARM_APEXNAV_INIT_SEARCH = (
    -1.6281021987682385,
    0.9056818874307258,
    0.47897782244727727,
    2.0442570619462734,
    -3.140000104904175,
    0.21061755241064453,
)
APEXNAV_CAM_HEIGHT_M = 0.88
# ################################
# Stage 4.10d: MuJoCo d455_link AGL≈0.880 m; Habitat FK optical AGL≈0.857 m
# (same joints; ~2.3 cm Hab↔MuJoCo floor/base bias). Keep ±2.5 cm so we do NOT
# random-search away from the co-pinned ARM_DEFAULT.
# ################################
APEXNAV_CAM_HEIGHT_TOL_M = 0.025
APEXNAV_CAM_ANGLE_TOL_DEG = 5.0

# Camera / TCP frames
CAMERA_LINK = "d455_depth_optical_frame"
TCP_BODY = "cr10_Link6"
BASE_LINK = "base_link"

# D455 depth optical typically: Habitat camera looks along -Z; optical frame looks along +Z.
EE_RGB_HFOV_DEG = 79.0
EE_RGB_RES = (480, 640)  # H, W
THIRD_RGB_RES = (720, 1280)

# Policy interface (MuJoCo / Isaac teleop) — unchanged dims from stage 4.x
NUM_OBS = 117
NUM_ACTIONS = 8
OBS_HISTORY = 3
POLICY_HZ = 10.0
ACTION_SCALE = 0.25

# Control-mode labels used in reports (do not blur these)
MODE_KINEMATIC = "kinematic_state_set"
MODE_PHYSICS = "bullet_physics_step"
MODE_COLLISION_QUERY = "contact_query_only"
MODE_PPO_MUJOCO = "ppo_mujoco_deploy"
