# Approach-fix pairing table (`approach_fix_20261122_215609`)

Unique variable: `OBJECT_HOLD_MAX_DIST` (3.0 OFF vs 8.0 ON). Fixed within each pair: spawn, budget, inflation, recovery, nf_look=OFF, no PPO.

## FF_* units
- Counted per **recovery event** in `steps.jsonl` where `exec.blocked_recovery` is set.
- `FF_try`: recovery_kind contains `forced_forward`.
- `FF_exec`: that recovery step not fully blocked.
- `FF_moved`: forward displacement recorded / successful MOVE_FORWARD actual.

| task | fix | hold | profile | recovery | valid | term | STOP | sr_proxy | claimed | dtg | moved | blk/trunc | rec_try/ok | FF_try/exec/moved | OH keep/drop | reused |
|------|-----|------|---------|----------|-------|------|------|----------|---------|-----|-------|-----------|------------|-------------------|--------------|--------|
| hy1 | OFF | 3.0 | legacy018 | v2 | ok | explore_budget_exhausted | budget | False | False | 0.485 | 5.708 | 56/14 | 11/9 | 5/3/3 | 0/1 | True |
| dd4b | OFF | 3.0 | legacy018 | v2 | ok | explore_budget_exhausted | budget | False | False | 3.011 | 2.133 | 69/13 | 12/11 | 5/5/4 | 0/0 | True |
| hy1 | ON | 8.0 | legacy018 | v2 | ok | explore_budget_exhausted | budget | False | False | 0.167 | 9.208 | 39/10 | 6/4 | 3/1/1 | 26/2 | False |
| dd4b | ON | 8.0 | legacy018 | v2 | ok | explore_budget_exhausted | budget | False | False | 3.011 | 2.133 | 69/13 | 12/11 | 5/5/4 | 0/0 | False |
| tee_chair4 | OFF | 3.0 | legacy018 | legacy | invalid_initial_penetration | explore_budget_exhausted | budget | False | False | 0.021 | 1.958 | 106/6 | 24/3 | 0/0/0 | 0/0 | False |
| tee_chair4 | ON | — | — | — | skipped | — | — | — | — | — | — | — | — | — | — | off_not_sr_proxy_regression_gap |
