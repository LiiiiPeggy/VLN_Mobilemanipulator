# Joint4 protocol (integrate)

- Worktree: `/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`
- Entry: `adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh` + `run_integrate_defaults.env`
- Cases: `hy1_plant_0`, `Dd4b toilet_0` × {legacy018, inf020_soft010} × {recovery legacy/off, v2/on}
- Fixed: scale 0.7, `fixed_base_gimbal`, F0+0.3, denoise=none, budget 150/100, `ENABLE_NO_FRONTIER_LOOK=false`
- Note: B V2 hy1 benefit occurred without re-entering NF look; keep that condition.
- Success: ObjectNav success_distance=1.0; invalid spawn / handshake abort → invalid run
