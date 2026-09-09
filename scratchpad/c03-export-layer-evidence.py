from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def link(p,label):return f'[{label}](<{p.as_posix()}>)'
def fence(s):return '\n```text\n'+str(s)+'\n```\n'
sources=[]
for prefix in ['astra-layer-ablation-v2','astra-compositor-ablation','astra-layer-wrapper-fixed','astra-presentation-guards-fixed','astra-unsupported-evidence','astra-unsupported-cause']:
    for model in ['registered','qwen-base']:
        folder=BASE/f'{prefix}-{model}'
        if not (folder/'RESULT.json').exists():continue
        rows=[json.loads(x) for x in (folder/'replies.jsonl').read_text(encoding='utf-8').splitlines()]
        prereg=json.loads((folder/'PREREG.json').read_text(encoding='utf-8'))
        posts=[json.loads(x) for x in (folder/'posts.jsonl').read_text(encoding='utf-8').splitlines()]
        audit=[json.loads(x) for x in (folder/'compose-audit.jsonl').read_text(encoding='utf-8').splitlines()] if (folder/'compose-audit.jsonl').exists() else []
        parts=[f'# Respuestas literales — {folder.name}\n',
               'Diagnóstico por capas, no aceptación C03. Español válido para entradas mixtas; no se exige una definición exhaustiva. Los errores, cortes y respuestas útiles se distinguen en el informe principal.\n',
               link(folder/'PREREG.json','Prompts, hechos, condiciones y hashes')+' · '+link(folder/'posts.jsonl','Todas las llamadas y reintentos')+' · '+link(folder/'RESULT.json','Recursos y cierre')+'\n']
        for c in prereg['cases']:
            parts += [f"## {c['id']}\n",'Entrada literal'+fence(c['request'])]
            if 'facts' in c:parts+=['Hechos sintéticos'+fence(c['facts']['situation'])]
            for row in [r for r in rows if r['id']==c['id']]:
                parts += [f"### {row['stage']}\n",f"Finalización: {row.get('finishReason')}; error: {row['error']}; {row['seconds']} s.\n",fence(row['response'])]
                if row['stage']=='guarded':
                    parts+=['Borradores de ESTA MISMA llamada, antes de validar (no la generación independiente de la etapa anterior):\n']
                    for post in [p for p in posts if p['stage']=='guarded' and p.get('id',p.get('case'))==c['id']]:
                        parts+=[fence(post['response']['choices'][0]['message'].get('content'))]
                    for a in [a for a in audit if a.get('trace')==c['id']]:
                        parts += [f"Auditoría {a.get('stage')}: motivo `{a.get('reason')}`, publicado `{a.get('published')}`.\n"]
        report=folder/'RESPUESTAS.md';report.write_text('\n'.join(parts),encoding='utf-8')
        # Verify every literal independently against the generated fenced blocks.
        text=report.read_text(encoding='utf-8')
        assert all(fence(r['response']) in text and fence(r['request']) in text for r in rows)
        manifest={'rows':len(rows),'verbatimChecked':True,'hashes':{p.name:sha(p) for p in [folder/'PREREG.json',folder/'posts.jsonl',folder/'replies.jsonl',folder/'RESULT.json',report]}}
        (folder/'REPORT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        sources.append({'folder':folder.name,'rows':len(rows),'result':json.loads((folder/'RESULT.json').read_text(encoding='utf-8'))})
print(json.dumps(sources,ensure_ascii=False,indent=2))
