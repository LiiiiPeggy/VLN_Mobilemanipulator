# ApexNav HM3D-v2 全量 — 实时失败原因

- 更新: 2026-11-11 01:07:14
- 进度: **1000/1000** (100.0%)
- SR: **74.4%** (论文 76.2%, Δ -1.7999999999999972)
- SPL: **37.65%** (论文 38.0%, Δ -0.3500000000000014)

## 结果分布（含 success）

| 原因 | 次数 | 占全部% | 占失败% |
|------|------|---------|---------|
| `success` | 744 | 74.4 | — |
| `false positive` | 144 | 14.4 | 56.25 |
| `stepout feasible` | 42 | 4.2 | 16.41 |
| `[stepout] false negative` | 26 | 2.6 | 10.16 |
| `stucking` | 22 | 2.2 | 8.59 |
| `no frontier` | 9 | 0.9 | 3.52 |
| `[no frontier] false negative` | 5 | 0.5 | 1.95 |
| `[stucking] false negative` | 5 | 0.5 | 1.95 |
| `infeasible` | 3 | 0.3 | 1.17 |

## Top 失败 × 目标类别

| label::reason | 次数 |
|----------------|------|
| `couch::false positive` | 31 |
| `potted plant::false positive` | 28 |
| `tv::false positive` | 25 |
| `bed::false positive` | 24 |
| `chair::false positive` | 20 |
| `tv::stepout feasible` | 17 |
| `toilet::false positive` | 16 |
| `potted plant::stucking` | 13 |
| `potted plant::[stepout] false negative` | 11 |
| `toilet::stepout feasible` | 10 |
| `tv::[stepout] false negative` | 9 |
| `potted plant::no frontier` | 7 |
| `couch::stepout feasible` | 5 |
| `chair::stepout feasible` | 4 |
| `chair::[stepout] false negative` | 3 |
| `toilet::stucking` | 3 |
| `bed::stepout feasible` | 3 |
| `chair::stucking` | 3 |
| `couch::[stucking] false negative` | 3 |
| `couch::[stepout] false negative` | 3 |
| `potted plant::stepout feasible` | 3 |
| `potted plant::[no frontier] false negative` | 3 |
| `couch::stucking` | 2 |
| `tv::[no frontier] false negative` | 2 |
| `chair::[stucking] false negative` | 2 |
| `tv::no frontier` | 2 |
| `couch::infeasible` | 2 |
| `tv::stucking` | 1 |
| `chair::infeasible` | 1 |
