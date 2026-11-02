# ApexNav batch 8 episodes — 2026-11-01

## Verdict

**OK — `BATCH_OK`**（8/8 完成无崩溃；任务成功 6/8）

| Item | Value |
|------|-------|
| Dataset | HM3D ObjectNav v2 (`--dataset hm3dv2`) |
| Indices | global `test_epi_num=0..7` |
| Completed | **8/8** |
| Crash | **0/8** |
| Task success | **6/8** |
| Task fail | **2/8** (ep2, ep6) |
| Mean SR (episode-level) | **75.00%** |
| Mean SPL (among all 8) | **58.10%** |
| Peak GPU mem | **12912 MiB** |
| Image | `vln-apexnav:single-ep-deps` = `50e76a268b26` |

## Metrics CSV

`/media/ubuntu/D/VLN_shared/runs/batch_20261101/ApexNav/metrics.csv`

| idx | status | success | SPL | soft SPL | DTG | wall_s | peak_MiB |
|-----|--------|---------|-----|----------|-----|--------|----------|
| 0 | TASK_SUCCESS | 100 | 65.82 | 65.40 | 0.0341 | 38 | 12501 |
| 1 | TASK_SUCCESS | 100 | 81.05 | 79.52 | 0.0490 | 24 | 12501 |
| 2 | TASK_FAIL | 0 | 0.00 | 14.60 | 9.9741 | 38 | 12909 |
| 3 | TASK_SUCCESS | 100 | 70.59 | 70.17 | 0.0628 | 49 | 12912 |
| 4 | TASK_SUCCESS | 100 | 81.02 | 80.35 | 0.0306 | 25 | 12905 |
| 5 | TASK_SUCCESS | 100 | 81.53 | 80.65 | 0.0415 | 26 | 12911 |
| 6 | TASK_FAIL | 0 | 0.00 | 57.70 | 1.7080 | 28 | 12905 |
| 7 | TASK_SUCCESS | 100 | 84.77 | 84.45 | 0.0400 | 51 | 12911 |

## Log index

- Driver: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/ApexNav/batch8_driver.log`
- Per-ep: `.../ApexNav/ep_{0..7}.log` + `ep_{i}.mem`
- VLM: `.../ApexNav/vlm_servers/` (`vlm.detector.*` / `vlm.itm.blip2itm` / `vlm.segmentor.sam` — **not** `vlfm.vlm`)
- Harness: `baselines/ApexNav/run_batch8_inner.sh` via `scripts/run_apexnav_batch8.sh`

## Notes

- Ep0 harness re-validated before full batch (SR=100 / SPL≈70).
- ROS Noetic + `exploration_node` + VLM ports 12181–12184.
- Task fails are non-crash evaluation results (pipeline EXIT 0).
