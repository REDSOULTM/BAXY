"""Freeze exactly one existing BAXY instruction layer for a paired comparison."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json

root=Path(__file__).resolve().parents[1]
source=root/'src/baxy_mind/llm.py'
node=next(n for n in ast.parse(source.read_text(encoding='utf-8-sig')).body
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM_PROMPT' for t in n.targets))
prompt=ast.literal_eval(node.value)
out=root/'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699/PROMPT_LAYERS.json'
assert not out.exists()
data=dict(utc=datetime.now(timezone.utc).isoformat(),source='src/baxy_mind/llm.py',
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_lines=[node.lineno,node.end_lineno],
    layers={'baxy-system':dict(system_prompt=prompt,sha256=hashlib.sha256(prompt.encode()).hexdigest())},
    plan='After native699 baseline, compare complete50 paired tasks for Qwen and strongest feasible K2 profile. Keep weights/backend/sampling/context/KV/output/headroom unchanged within each pair. Prepend only the existing SYSTEM_PROMPT; no other pipeline code, language classifier, guards, tools, kernel or provider. This identifies the effect of that instruction layer only, not all BAXY. A later minimal replacement is warranted only by a measured problem.',
    scoring='Same frozen PANEL.json rubrics and final-answer verification, no relaxed criteria. Record case-level gains/regressions. Identity/style alone is not given a bonus: compare correctness first. Model choice remains provisional until relevant integration is checked.')
out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(layer='baxy-system',characters=len(prompt),sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
