# Workspace audit 2026-11-22

## Git tips vs known
- main 2214550 OK
- scale070 66869af OK
- navinf d7926f9 OK
- followup 09fadf4 OK

## Workspaces
| Path | Branch | HEAD | Dirty |
|------|--------|------|-------|
| /home/ubuntu/locomani/VLN_Mobilemanipulator_integrate | cursor/habitat-rangercr10-scale070-integrate | 66869af | 1 files |
| /home/ubuntu/locomani/VLN_Mobilemanipulator | cursor/nav-inflation-halfwidth-softcost | 6ec6b20 | 52 files |
| /home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf | cursor/nav-inflation-halfwidth-softcost | d7926f9 | 2 files |
| /home/ubuntu/locomani/B_VLN_Mobilemanipulator | cursor/ranger-target-discovery-followup | 09fadf4 | 46 files |

## Background (handover-related)
- sim lock: FREE
- containers: vln-rangercr10-agentA-navinf, vln-rangercr10-agentB-nofrontier, vln-rangercr10 (shared) — leave running unless owned by this handover
- LocoManip validate_d455_continuous.py processes are NOT VLN handover — do not kill
- cursor-agent-worker on agentA workspace — do not kill
