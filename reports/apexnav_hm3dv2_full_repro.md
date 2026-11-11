# ApexNav HM3D-v2 全量复现（已完成）

## 论文 vs 本机

| 项 | 论文 (Table I) | 本机 `hm3dv2_full_20261109_231528` | Δ |
|----|----------------|-------------------------------------|---|
| Dataset | HM3D-v2 val | 同左 | — |
| N | 1000 | **1000** | 0 |
| SR | 76.2% | **74.4%** | **-1.8 pp** |
| SPL | 38.0% | **37.65%** | **-0.35 pp** |
| Soft SPL | — | 40.31% | — |
| Avg DTG | — | 1.414 | — |
| 墙钟 | — | ~13.1 h（`47276 s`） | — |

结论：**基本复现成功**（SR/SPL 均在论文 ±2 pp 内；SPL 几乎贴合）。

## 失败原因（`check_failure` / `RESULT_TYPES`）

| 原因 | 次数 | 占全部% | 占失败% |
|------|------|---------|---------|
| success | 744 | 74.4 | — |
| **false positive** | **144** | **14.4** | **56.3** |
| stepout feasible | 42 | 4.2 | 16.4 |
| [stepout] false negative | 26 | 2.6 | 10.2 |
| stucking | 22 | 2.2 | 8.6 |
| no frontier | 9 | 0.9 | 3.5 |
| [no frontier] false negative | 5 | 0.5 | 2.0 |
| [stucking] false negative | 5 | 0.5 | 2.0 |
| infeasible | 3 | 0.3 | 1.2 |

主因：**误认目标并 STOP（false positive）占失败一半以上**；其次步数耗尽 / 漏检 / 卡住。

Top 失败 × 类别：`couch|potted plant|tv|bed|chair::false positive`；`tv|toilet::stepout feasible`；`potted plant::stucking`。

## 运行配置

- 容器：`vln-apexnav`；ROS `:11313`
- 入口：`habitat_evaluation.py --dataset hm3dv2 test_epi_num=-1 need_video=false`
- 输出：`/media/ubuntu/D/VLN_shared/runs/ApexNav/hm3dv2_full_20261109_231528`
- 汇总：`reports/apexnav_hm3dv2_full_20261109_231528/{final_summary,live_failures,summary}.json`
- 注：进程在 1000/1000 写完后出现 `Unexpected error` / `exit_code=1`，**指标与 record 已完整**，不影响结论。

## 失败口径

见 `basic_utils/failure_check/failure_check.py`（`success` / `infeasible` / `false positive` / `no frontier` / `stucking` / `stepout*` / `*false negative`）。
