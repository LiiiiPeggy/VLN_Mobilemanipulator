# Tabletop views pilot — capture (Cursor C)

**Baseline**: `492f53f` (branch `cursor/habitat-rangercr10-scale070`)  
**Platform**: Habitat + RangerBox-CR10 `robot_scale=0.7`, gripper fixed, executor `kinematic_collision_v1.2`

## Layout for Cursor D

- Index / freeze: `reports/tabletop_views_pilot/capture/`
- Pair folders (RGB / depth / GT masks):  
  `reports/tabletop_views_pilot/captures/<pair_id>/`  
  → symlink to `/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/tabletop_views_pilot/captures/`
- On-disk camera modes: `fixed_base_gimbal/`, `arm_ee/` (alias **arm_view**)
- Schema: `adapters/habitat_rangercr10/evaluation/tabletop_views/CAPTURE_LAYOUT.md`

## Reconstruct

```bash
docker exec vln-rangercr10 bash -lc '
cd /workspace/VLN_Mobilemanipulator
export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:adapters/habitat_rangercr10/experiments/tabletop_views
# 1) catalog (optional if locked exists)
python3 adapters/habitat_rangercr10/experiments/tabletop_views/catalog.py --gpu 0
# 2) verify + lock
python3 adapters/habitat_rangercr10/experiments/tabletop_views/verify_and_select.py --gpu 0
# 3) capture all locked pairs
python3 adapters/habitat_rangercr10/experiments/tabletop_views/capture_pair.py --gpu 0 --force
'
```

## Frozen parameters

See `handoff_to_D_first_pair.json` → `frozen` (arm init, gimbal sequence, arm deltas, 480×640, hfov 79°).

## Selection

`locked_instances.json` / `.md` — scene-fact only; ≤3 / category; cup seeds include `CrMo8WxCyVb`.
