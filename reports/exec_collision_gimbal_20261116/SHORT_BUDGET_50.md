# Short-budget batch (MAX_STEPS=50)

- Batches: `ab24b_20261116_224229` + recovery `ab24b_rec_20261117_071620`
- Effective: max_steps=50, max_explore_actions=100 (explore budget never binds)
- After 26-step init lookaround ≈24 explore actions remain
- Aggregate: SR_proxy 0/24, near_goal 5, blocked 681, moved≈14.75m
- Do NOT treat later MAX_STEPS=150 results as same-condition improvement
