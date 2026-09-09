"""Documented sampling on the draft-repair task after greedy578 grammar failure."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-cpu-dialogue-repair578.py').read_text(encoding='utf-8')
source = source.replace('astra-cpu-dialogue-repair578', 'astra-cpu-dialogue-sampling579').replace('C03-cpu-dialogue-repair578-private', 'C03-cpu-dialogue-sampling579-private')
source = source.replace("profiles=[('baseline',{'seed':0}),('draft-feedback',{'seed':0})]", "profiles=[('documented-seed0',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':0}),('documented-seed17',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':17})]")
source = source.replace("if profile=='draft-feedback':payload['messages']", "if True:payload['messages']")
source = source.replace('Four consumed actual writer captures: CPU usage ES failure/EN control, CPU model+core ES ownership failure575 and EN core control. Compare exact initial writer with a second dialogue turn carrying its actual captured draft plus explicit subject feedback. Preserve original facts, request, model and sampling. This tests draft-aware correction, not another stateless naming/instruction sweep.', 'Same four consumed draft-feedback payloads578, now Qwen official sampling at seeds0/17. Greedy578 fixed both actors but generated Esto computadora for CPU usage; EN controls stayed correct. Hold feedback, original facts and draft constant, change only documented sampling profile. Eight native samples; no source adoption or global model claim. Official model card checked 2026-09-09: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices recommends temperature0.7/top_p0.8/top_k20/min_p0; presence optional0-2, neutral0 here.')
source = source.replace('8 draft-repair comparisons collected', '8 documented draft-repair samples collected')
exec(compile(source, __file__, 'exec'))
