#!/usr/bin/env bash
OUT=/media/ubuntu/D/VLN_shared/runs/ApexNav/hm3dv2_full_20261109_231528
REPORT=/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/apexnav_hm3dv2_full_20261109_231528
while true; do
python3 - <<'PY'
import json, re, time
from collections import Counter
from pathlib import Path
OUT=Path('/media/ubuntu/D/VLN_shared/runs/ApexNav/hm3dv2_full_20261109_231528')
REPORT=Path('/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/apexnav_hm3dv2_full_20261109_231528')
PAPER_SR, PAPER_SPL, PAPER_N = 76.2, 38.0, 1000
rec=OUT/'videos_hm3dv2_val'/'record.txt'
failures=Counter(); episodes=[]; by_label=Counter(); fail_by_label=Counter()
if rec.is_file():
  blocks=re.split(r'(?=Scene ID: )', rec.read_text(errors='ignore'))
  for b in blocks:
    if 'Scene ID:' not in b: continue
    m_res=re.search(r'success or not:\s*(.+)', b)
    m_lab=re.search(r'target to find is\s*(.+)', b)
    m_no=re.search(r'No\.(\d+) task is finished', b)
    m_sr=re.search(r'Average Success\s+\|\s+([\d.]+)%', b)
    m_spl=re.search(r'Average SPL\s+\|\s+([\d.]+)%', b)
    m_scene=re.search(r'Scene ID:\s*(\S+)', b)
    m_epi=re.search(r'Episode ID:\s*(\d+)', b)
    res=(m_res.group(1).strip() if m_res else 'unknown')
    lab=(m_lab.group(1).strip() if m_lab else None)
    failures[res]+=1
    by_label[lab]+=1
    if res!='success':
      fail_by_label[f'{lab}::{res}']+=1
    episodes.append({
      'n': int(m_no.group(1)) if m_no else None,
      'episode_id': int(m_epi.group(1)) if m_epi else None,
      'scene': m_scene.group(1) if m_scene else None,
      'label': lab, 'result': res,
      'running_sr_pct': float(m_sr.group(1)) if m_sr else None,
      'running_spl_pct': float(m_spl.group(1)) if m_spl else None,
    })
  episodes=list(reversed(episodes))  # record appends newest first
n=len(episodes); ns=failures.get('success',0); nf=n-ns
share_all={k: round(100.0*v/n, 2) for k,v in failures.most_common()} if n else {}
share_fail={k: round(100.0*v/max(1,nf), 2) for k,v in failures.most_common() if k!='success'}
sr=(100.0*ns/n) if n else None
spl=episodes[-1]['running_spl_pct'] if episodes else None
summary={
  'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
  'paper_target': {'dataset':'HM3D-v2 val','n_episodes':PAPER_N,'SR':PAPER_SR,'SPL':PAPER_SPL},
  'n_completed': n, 'n_success': ns, 'n_fail': nf,
  'progress_pct': round(100.0*n/PAPER_N, 2) if n else 0.0,
  'SR_pct': sr, 'final_running_sr_pct': episodes[-1]['running_sr_pct'] if episodes else None,
  'final_running_spl_pct': spl,
  'gap_sr_pp': (sr-PAPER_SR) if sr is not None else None,
  'gap_spl_pp': (spl-PAPER_SPL) if spl is not None else None,
  'failure_hist': dict(failures.most_common()),
  'share_among_all_pct': share_all,
  'share_among_fails_pct': share_fail,
  'top_fail_by_label_reason': fail_by_label.most_common(40),
  'label_counts': dict(by_label.most_common()),
  'out_dir': str(OUT),
}
REPORT.mkdir(parents=True, exist_ok=True)
(REPORT/'live_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
(REPORT/'failure_hist.json').write_text(json.dumps(dict(failures), indent=2, ensure_ascii=False))
# human-readable table
lines=['# ApexNav HM3D-v2 全量 — 实时失败原因', '',
  f'- 更新: {summary["updated_at"]}',
  f'- 进度: **{n}/{PAPER_N}** ({summary["progress_pct"]}%)',
  f'- SR: **{sr if sr is not None else "—"}%** (论文 {PAPER_SR}%, Δ {summary["gap_sr_pp"]})',
  f'- SPL: **{spl if spl is not None else "—"}%** (论文 {PAPER_SPL}%, Δ {summary["gap_spl_pp"]})',
  '', '## 结果分布（含 success）', '',
  '| 原因 | 次数 | 占全部% | 占失败% |',
  '|------|------|---------|---------|']
for k,v in failures.most_common():
  fa=share_all.get(k,'—'); ff=share_fail.get(k,'—') if k!='success' else '—'
  lines.append(f'| `{k}` | {v} | {fa} | {ff} |')
lines += ['', '## Top 失败 × 目标类别', '', '| label::reason | 次数 |', '|----------------|------|']
for k,v in fail_by_label.most_common(30):
  lines.append(f'| `{k}` | {v} |')
if not fail_by_label:
  lines.append('| （尚无失败） | 0 |')
(REPORT/'live_failures.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(json.dumps({'n':n,'SR':sr,'SPL':spl,'fails':dict(failures)}, ensure_ascii=False), flush=True)
PY
  sleep 120
done
