# UniGoal IIN smoke — SINGLE_EPISODE_OK（弱）

更新：2026-11-07 15:20（UTC+8）

## 证据

- 配置：`configs/config_habitat_luna_smoke120.yaml`（`max_episode_length=120`, `num_eval_episodes=1`）
- 日志：`runs/UniGoal/smoke_launch_20261107_145453_ug120.log`
- 汇总：`runs/UniGoal/luna_smoke120/luna_smoke120/log/total.json` → `{"succ":[0.0],"spl":[0.0]}`
- eval：同目录 `eval.log` 末尾 `Average SR/SPL: 0.00000/0.00000`
- VLM：model8 多次 `HTTP/1.1 200 OK`（`image_url={"url": data:...}` 修复后）

## 本轮修复

1. VLM payload 对齐 MSGNav：`image_url` 必须为 `{"url":"data:image/jpeg;base64,..."}`（原先传字符串 → 502/超时）
2. 外层重试 + `max_retries=0`（避免 SDK 嵌套 60s）+ JPEG 缩小（`VLM_MAX_SIDE=384`）
3. smoke 脚本 `pipefail`

## 备注

- 本烟冒烟步数偏少（日志可见 `update_observation 0` 后很快进入收尾）；**已证明依赖/API/主循环可结束并写出 SR/SPL**，但不足以对照论文 HM3D IIN 60.2/23.7。
- 论文对照需更长 `max_episode_length`（如 500–1000）与批量 episode。

## 论文对照（未宣称复现）

| 协议 | 论文 | 本地 smoke |
|------|------|------------|
| HM3D IIN | SR≈60.2 / SPL≈23.7 | 1ep SR=0 / SPL=0 |
