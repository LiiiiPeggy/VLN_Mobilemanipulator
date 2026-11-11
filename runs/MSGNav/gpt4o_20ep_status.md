# MSGNav GPT-4o 20ep — blocked 2026-11-06

## Verdict
**BLOCKED** — `model8.run` 当前账号组不支持 `gpt-4o` / `gpt-4o-2024-08-06`（404 model_not_found）。

可用模型（节选）：`gpt-5.6-sol` / `gpt-5.6-luna` / `gpt-5.6-terra` / `gpt-6-*` / `gpt-6.1-*`。

## 需要
1. 提供支持 GPT-4o 的 endpoint + key（官方 OpenAI 或其它网关），或  
2. 指定用现有 model8 模型做 20ep 探针（如继续 `gpt-5.6-sol`）。

## 已就绪（待 API）
- 数据：`baselines/MSGNav/data/objectnav_hm3d_20ep`（20 景 × 1 ep）
- 配置：`cfg/eval_hm3d_20ep_gpt4o.yaml`
- 脚本：`scripts/run_msgnav_20ep_gpt4o.sh`（含 token 用量 jsonl）
- `.env` 已设 `GPT_MODEL=gpt-4o`（endpoint 未变）

排队脚本已停，避免 VLFM 结束后自动踩 404。
