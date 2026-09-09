"""Same effective597 requests and backend, only official2507 template changes."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-language-backend598.py').read_text(encoding='utf-8')
source = source.replace('598', '599').replace('language-backend599', 'language-template599')
lines = source.splitlines()
index = next(index for index, line in enumerate(lines) if line.startswith('source = source.replace(needle, needle +'))
lines[index] = '''source = source.replace(needle, needle + "\\ncommand.extend(['--chat-template-file', str(root/'artifacts/comprobaciones/C03/astra-qwen-documented-profile/official-template.jinja')])")'''
source = '\n'.join(lines) + '\n'
source = source.replace("old = 'b9980/8014d2cf9'", "old = 'embedded GGUF template with reasoning-history support'")
source = source.replace("new = 'b10865/5266f24da, all request bytes and other server settings unchanged'", "new = 'official Qwen2507 template, same b9980 and all effective597 payloads'")
source = source.replace('Only replace llama.cpp b9980 by previously verified b10865/5266f24da.', 'Only replace the embedded template by the official2507 template already archived and compared. Keep b9980. The two templates differ in reasoning-history support even when these rendered messages are identical; parser/grammar capability is a separate hypothesis.')
source = source.replace('Test whether the newer parser/backend changes this specific symptom; prior456/481 comparisons concerned different cases and do not settle it.', '598 did not repair it on b10865. Test whether the embedded reasoning-history capability changes structured generation compared with the official non-thinking template, without changing the actual instructions or raising the output budget.')
source = source.replace('12 identical wire requests collected on newer backend; adjudication pending.', '12 identical wire requests collected with official template; adjudication pending.')
exec(compile(source, __file__, 'exec'))
