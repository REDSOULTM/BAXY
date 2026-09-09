"""Same35 cases605 with original Gemma and the qualified direct-chat profile."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source=source.replace('592','614').replace('conversation-regression614','gemma-product614')
source=source.replace('Shared source590 product, base registered runtime, built-in diagnostics only.',
                      'Shared source606 product; isolated original Gemma E2B Q4/b10809 override497, direct chat profile qualified613. Classifier/compose parameters remain unchanged to locate integration failures; no global model ranking.')
source=source.replace('No parameter, payload, classification, draft or output replacement. No adapter override.',
                      'Diagnostic hook sets first-chat temperature1 and p.95/k64/min0, preserves the existing reduced retry temperature, and enables measured lazy loading. Native wire inputs/outputs are observed. No prompt, history, classifier result, guard or model-output rewriting. Registered manifest unchanged; this override is not promotion.')
source=source.replace('"str(root/\'src\')"',
                      '"str(root/\'scratchpad/c03-gemma-chat614-hook\')+os.pathsep+str(root/\'src\')"')
needle="exec(compile(source, __file__, 'exec'))"
assert source.count(needle)==1
injection='''
source=source.replace("config=json.loads(manifest.read_text(encoding='utf-8-sig'))", "config=json.loads(manifest.read_text(encoding='utf-8-sig'))" + "\\nconfig.update(gguf='D:/BAXYRuntime/experiments/models/gemma4-e2b-inherited-d3b0fed4/base-gguf/gemma-4-E2B-it-Q4_K_M.gguf', llama_server='D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4/llama-server.exe')")
source=source.replace('3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597','740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8')
source=source.replace("model=Path(config['gguf'])", "assert sha(Path(config['llama_server'])) == 'cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'\\nmodel=Path(config['gguf'])")
'''
source=source.replace(needle,injection+needle)
exec(compile(source,__file__,'exec'))
