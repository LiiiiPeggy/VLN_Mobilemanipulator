# MSGNav batch 8 episodes — 2026-11-01

## Verdict

**OK — `BATCH_OK`**（8/8 完成无崩溃；任务成功 3/8）

| Item | Value |
|------|-------|
| Config | `cfg/eval_hm3d_batch8.yaml` |
| Data | `data/objectnav_hm3d_batch8` (`00_`…`07_` scene JSONs, 1 ep each) |
| Completed | **8/8** |
| Crash | **0/8** |
| Task success | **3/8** (SR **37.50%** by distance) |
| Mean SPL (by distance) | **20.70%** |
| Peak GPU mem | **16507 MiB** |
| Image | `vln-habitat025:msgnav-deps` |
| API | `gpt-5.6-sol` via `model8.run`（中后期多次 502/timeout，重试后仍跑完） |

## Metrics CSV

`/media/ubuntu/D/VLN_shared/runs/batch_20261101/MSGNav/metrics.csv`

| idx | scene | status | SR_dist | SPL_dist | wall_s | peak_MiB |
|-----|-------|--------|---------|----------|--------|----------|
| 0 | 00_4ok3usBNeis | TASK_SUCCESS | 100 | 33.62 | 1353 | 16310 |
| 1 | 01_5cdEh9F2hJL | TASK_FAIL | 0 | 0.00 | 467 | 16439 |
| 2 | 02_6s7QHgap2fW | TASK_SUCCESS | 100 | 79.55 | 259 | 15414 |
| 3 | 03_DYehNKdT76V | TASK_FAIL | 0 | 0.00 | 324 | 15319 |
| 4 | 04_Dd4bFSTQ8gi | TASK_FAIL | 0 | 0.00 | 445 | 16410 |
| 5 | 05_Nfvxx8J5NCo | TASK_FAIL | 0 | 0.00 | 1765 | 15304 |
| 6 | 06_QaLdnwvtxbs | TASK_FAIL | 0 | 0.00 | 724 | 16278 |
| 7 | 07_TEEsavR23oF | TASK_SUCCESS | 100 | 52.42 | 846 | 16507 |

## Log index

- Driver: `/media/ubuntu/D/VLN_shared/runs/batch_20261101/MSGNav/batch8_driver.log`
- Per-ep: `.../MSGNav/ep_{0..7}.log` + `.mem`
- Algorithm outputs: `.../MSGNav/mini_batch_8ep_20261101/`
- Prior crash attempt (bad `NN_` scene prefix): `.../MSGNav/_crash_attempt1/`
- Harness: `baselines/MSGNav/run_batch8_inner.sh` via `scripts/run_msgnav_batch8.sh`

## Fixes applied for this batch

1. `run_hm3d_evaluation.py`: `--specific` 时跳过 `random.shuffle`；`sorted(listdir)`；支持 `NN_<scene>.json` 前缀解析。
2. Success CSV 判定改为匹配日志 `Success rate by distance: 100.00`（旧正则 `success_by_distance:\s*1` 误标失败）。
