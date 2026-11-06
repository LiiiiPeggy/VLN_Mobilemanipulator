# Camera coord / intrinsics validation

all_pass: **True**

| test | pass |
|---|---|
| intrinsics | True |
| optical_rot_map | True |
| render_rx | True |
| project_roundtrip | True |
| agl | True |
| ray_hfov | True |

Note: prior FOV reports that called launch fy=422 (VFOV≈59.25°) 'measured D455 FOV' are **downgraded** — that fy used HFOV×H/W.
