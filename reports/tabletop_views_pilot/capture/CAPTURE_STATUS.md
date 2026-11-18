# Capture status (Cursor C)

Updated during batch. Evidence under D-disk captures + this folder.

## Ready for Cursor D (interface locked)

| Item | Value |
|------|-------|
| First pair | `CrMo8WxCyVb_cup_423` |
| Handoff | `handoff_to_D_first_pair.json` |
| Layout | `CAPTURE_LAYOUT.md` (`fixed_base_gimbal` + `arm_ee`≡`arm_view`) |
| Data | `reports/tabletop_views_pilot/captures/<pair_id>/` → D symlink |
| Init MAE | ~0 (identical init frames) |
| Base motion | false during capture |
| GT masks | aligned 480×640; empty mask = invisible (kept) |

## Locked set (12)

See `locked_instances.md`. Categories: cup×3, bowl×3, remote×3, bottle×3.

## Batch

Run: `capture_pair.py` (resume skips completed). Log:  
`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/tabletop_views_pilot/capture_batch.log`
