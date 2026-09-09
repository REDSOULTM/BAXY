from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-compositor-ablation.py').read_text(encoding='utf-8')
source = source.replace('astra-compositor-ablation-{key}', 'astra-boundary-composer-{key}')
start = source.index('cases=json.loads(')
end = source.index('os.environ.update', start)
source = source[:start] + '''previous=json.loads((ROOT/'artifacts/comprobaciones/C03/astra-unsupported-evidence-qwen-base/PREREG.json').read_text(encoding='utf-8'))
cases=[{'id':c['id'],'route':'error','request':c['request'],'language':c['language'],'intent':'error',
        'facts':{'situation':json.dumps({'kind':'failure','polarity':'failure','cause':'out_of_catalog'},ensure_ascii=False)},
        'criteria':'State the known capability limit; do not infer absence, installation or an attempted effect. Same nine consumed diagnostic requests.'}
       for c in previous['cases']]
''' + source[end:]
source = source.replace("['plain','prompt','guarded']", "['guarded']")
source = source.replace('synthetic-fact-narration-ablation-not-product-acceptance', 'reuse-existing-error-composer-for-known-boundary-not-acceptance')
source = source.replace('Same literal request and synthetic situation facts. Plain has a short narration instruction and JSON facts; prompt replays the exact composer request; guarded calls the real composer with the same first messages, asserted. First seed preserved from captured product payload; retries retain product seeds. Token budgets are identical per case across stages. No PC effects. Full app must be measured separately.', 'Same nine consumed unsupported diagnostic requests. Replace the separate unsupported conversation redactor with the EXISTING error composer and its existing out_of_catalog situation. No product edit yet; current composer guarded only, first prompt asserted, product seeds and budgets preserved. This does not establish whether the requests ought to be routed unsupported; no PC effects. Full app remains required.')
(root / 'scratchpad/c03-boundary-composer.py').write_text(source, encoding='utf-8')
print('Prepared existing compositor comparison, nine consumed cases, no source edits.')
