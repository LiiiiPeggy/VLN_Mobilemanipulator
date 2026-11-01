# ApexNav single episode — 2026-11-01

## Verdict

**OK — `SINGLE_EPISODE_OK`**

| Item | Value |
|------|-------|
| Dataset | HM3D ObjectNav v2 (`--dataset hm3dv2`) |
| Override | `test_epi_num=0 need_video=false` |
| Target | `bed` (LLM answer room=`bedroom`) |
| Result | **success** |
| Success | **100.00%** (1/1) |
| SPL | **70.06%** |
| Soft SPL | **69.35%** |
| Distance to goal | **0.0556** |
| Steps | ~97 (final action STOP=0) |

## Evidence

- Log (success metrics): `/media/ubuntu/D/VLN_shared/runs/ApexNav/single_episode_20261101_retry4.log`  
  (repo copy: `runs/ApexNav/single_episode_20261101_retry4.log`)
- Longer run log (same episode handshake + steps): `.../single_episode_20261101_retry3.log`
- VLM server logs: `/media/ubuntu/D/VLN_shared/runs/ApexNav/vlm_servers/`
  - GDINO `:12181`, BLIP2 `:12182`, MobileSAM `:12183`, YOLOv7 `:12184` — all `Model loaded!`
- Catkin build log: `vlm_servers/catkin_make12.log` (exploration_node built)
- Image after runtime deps commit: `vln-apexnav:latest` = `vln-apexnav:single-ep-deps` = **`50e76a268b26`** (28.2GB)  
  Prior formal build tag kept as `vln-apexnav:build` = `118284656358`

## Runtime stack used

1. Compose mount added: `/media/ubuntu/D/VLN_shared:/media/ubuntu/D/VLN_shared` (absolute data symlinks).
2. ROS Noetic copied from image `nbv-fkie:noetic` (**image only**, running `nbv_fkie` untouched) + focal shared libs.
3. `catkin_make` of `src/planner/*` → `devel/lib/exploration_manager/exploration_node`.
4. `roscore` + `roslaunch exploration_manager exploration.launch` + four VLM Flask servers.
5. `python habitat_evaluation.py --dataset hm3dv2 test_epi_num=0 need_video=false`.

## Local adaptation (adapter only)

`habitat2ros/habitat_publisher.py`: avoid Noetic `cv_bridge` (needs `libboost_python38`) by building `sensor_msgs/Image` from numpy; local `quaternion_from_euler` (no `tf`).

## Notes

- `flag_once` path prints metrics then `break` before `write_record`; success is in the evaluation log table.
- numpy kept at **1.23.5**; OpenCV pin **4.8.1.78** (OpenCV 5.x broke habitat maps import).
- LAVIS needs `transformers==4.26.1` + offline HF bert cache under `/shared/cache/huggingface`.
