# SG-Nav ObjectNav — 官方 navmesh 20ep：**18/20 中断**

更新：2026-11-11 13:48（UTC+8）

## 跑次

| 项 | 值 |
|----|-----|
| STAMP | `20261109_230909` |
| 配置 | 20 ep，`SPLIT_L=0 SPLIT_R=1`，官方 `.navmesh`，LLM soft-fail |
| 状态 | **STOPPED at 18/20**（日志止于 11-11 01:07；`vln-sgnav` 容器当前 **not running**） |
| 日志 | `runs/SG-Nav/smoke_20261109_230909/driver.log` |

## 已完成 18 ep 均值

| 指标 | 本地 18ep | 论文 MP3D val |
|------|-----------|---------------|
| SR | **0.50**（9/18） | ≈0.402 |
| SPL | **≈0.131** | ≈0.160 |

单景 `2azQ1b91cZZ`；样本量仍小，且 LLM=luna ≠ 论文 GPT，**不能宣称复现**。

## 成功 ep（success=1）

1, 2, 6, 8, 9, 11, 14, 15, 16（共 9）

## 阻塞

- 评测在 ep18 途中停下；容器已退出，需重启 `vln-sgnav` 后续跑剩余 / 重开完整 20ep。
- model8 仍频繁 timeout（日志约 93 次），靠 soft-fail 撑过大部分。
