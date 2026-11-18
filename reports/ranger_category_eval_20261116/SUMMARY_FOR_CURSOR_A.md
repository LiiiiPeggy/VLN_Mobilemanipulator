# 给 Cursor A（评测侧 — 主批已完成）

## 正式批结果（冻结 150/100）

- Batch `formal150_full_20261117_190344`：**109/109 完成**
- micro SR_proxy=**0.3056**（33/108；1×empty_run 不计）
- macro SR_proxy=**0.3204**
- 详见 `formal_fixed_gimbal_v1/FORMAL_RESULT_v1.md` 与 `accounting_formal150_full_20261117_190344.md`

## 仍缺

本批 `git_sha_vln` 仍全为 null（启动早于你的写入）。后续 run 请确认非空。

## Recovery

`svBbv1Pavdk_bed_0` empty_run 正在补跑（`formal150_recovery_empty_20261118c`，带 `recovery_of`）；不挑成功覆盖。
