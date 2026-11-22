# Narrow batch — waiting for host lock

- Lock path: `/home/ubuntu/locomani/_sim_host_run.lock`
- Current holder (observed): `owner=agentB_nofrontier` — A will not steal.
- Ready offline: `jobs_narrow.tsv`, `run_narrow_paired_agentA.sh`
- Protocol: 150/100, scale 0.7, fixed_base_gimbal, F0+0.3, ROS 11323, A container only
- Cases: TEEsav toilet_2 + Dd4b toilet_0 × {legacy018, inf020_soft010}
- When lock free: acquire → run 4 episodes → cleanup 11323 → release → report
