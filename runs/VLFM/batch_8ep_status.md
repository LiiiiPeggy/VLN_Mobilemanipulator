# VLFM batch 8 episodes — 2026-11-01

## Verdict

**OK — `BATCH_OK`**（8/8 完成无崩溃；任务成功 2/8）

| Item | Value |
|------|-------|
| Dataset | Habitat ObjectNav HM3D (val iterator) |
| Override | `habitat_baselines.test_episode_count=8` |
| Completed | **8/8** |
| Crash | **0/8** |
| Task success | **2/8** (SR **25.00%**) |
| Mean SPL | **0.1164** |
| Soft SPL | **0.1963** |
| Mean DTG | **5.7643** |
| Peak GPU mem | **19356 MiB** |
| Wall | **257 s** (eval ~4:00 after VLM up) |
| Image | `vln-habitat024:latest` = `fe6b1ca643fd` |

## Metrics

- Summary: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/VLFM/summary.txt`
- CSV: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/VLFM/metrics.csv`
- Detail: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/VLFM/metrics_detail.csv`
- Full log: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/VLFM/batch8.log`

Aggregate (from habitat logger):

```
Average episode success: 0.2500
Average episode spl: 0.1164
Average episode soft_spl: 0.1963
Average episode distance_to_goal: 5.7643
Success rate: 25.00% (2 out of 8)
```

Per-episode CSV: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/VLFM/metrics_per_ep.csv`

| idx | status | episode_id | scene | reason |
|-----|--------|------------|-------|--------|
| 0 | TASK_FAIL | 45 | 5cdEh9F2hJL | false_positive |
| 1 | TASK_FAIL | 42 | 5cdEh9F2hJL | false_positive |
| 2 | TASK_SUCCESS | | | |
| 3 | TASK_FAIL | 91 | 5cdEh9F2hJL | false_positive |
| 4 | TASK_FAIL | 33 | 5cdEh9F2hJL | false_positive |
| 5 | TASK_SUCCESS | | | |
| 6 | TASK_FAIL | 17 | 5cdEh9F2hJL | false_positive |
| 7 | TASK_FAIL | 89 | 5cdEh9F2hJL | false_positive |

## Log index

- Driver: `.../VLFM/batch8_driver.log`
- VLM: `.../VLFM/vlm_servers/{gd,blip,sam,yolo}_batch.log`
- Harness: `baselines/VLFM/run_batch8_inner.sh` via `scripts/run_vlfm_batch8.sh`

## Notes

- Pipeline EXIT 0; low SR is task quality (false_positive stops), not infra crash.
- VLM via `python -m vlfm.vlm.*` ports 12181–12184.
