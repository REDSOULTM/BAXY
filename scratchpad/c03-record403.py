from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-generic-mind403'
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
rows = [json.loads(line) for line in (out / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 6
report = ['#403 — mente existente para recuerdo de conversación', '',
    '4/6 útiles. Los cuatro recuerdos de nombre son correctos: historial real402bT6→Álvaro, consultaEN→Álvaro, otra declaración→Renata y hermanaCasey no desplaza aPriya. Frente a402bT6 que fuerza la memoriaJordan, la mente existente puede usar el dato humano actual. No se cambia modelo, prompt, historial ni fuente; no efectos, App/UI/voz ni aceptación fresca.', '',
    'Los dos controles nuevos que preguntan la cuenta de Windows ejecutandoBAXY proponen system.status, no system.identity. Son fallos conservados: system.status ofrece recursos, no userName de SystemIdentityHandler. La respuesta en0,03/0,08s señala una ruta determinista a investigar, no atribuirla al modelo. La reparación propuesta se limita a nombres conversacionales ya interceptados por el parser de memoria; no afecta ni declara resueltos esos controles.', '']
for case, row in zip(prereg['cases'], rows):
    report += ['## ' + case['id'], '', '**Entrada:** ' + case['request'], '',
               '**Respuesta:** ' + (row['reply'].get('reply') or row['reply'].get('operation') or '[vacío]'), '',
               f"{row['seconds']}s; {'fallo de operación' if 'account' in case['id'] else 'útil' }.", '']
assert not (out / 'RESULT.md').exists()
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.jsonl', 'EXIT.json']]
paths += [root / 'scratchpad/c03-generic-mind403.py', root / 'scratchpad/c03-generic-mind403-cases.json']
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n', encoding='utf-8')
out = base / 'astra-name-scope404'
out.mkdir(exist_ok=False)
(out / 'PREREG.json').write_text(json.dumps({
    'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': '403 proves actual402bT6 and three name controls are answered correctly by existing full mind. Stop intercepting a generic name recall as a persistent read when bounded current human dialogue contains a self-naming clause. No mutable name cache, extraction of a claimed identity, new prompt, or direct answer. Existing DeclaredNameInputPattern only determines relevant conversation scope; existing name recall pattern marks generic ES/EN alternatives. Explicit stored reads and no-current-name context keep the private route.',
    'owners': ['src/Baxy.App/NaturalMemoryRequestParser.cs', 'src/Baxy.App/MainWindowViewModel.cs', 'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs'],
    'validation': 'Contract-mind App tests before source: current human declaration uses dialogue/no journal read, explicit stored request/third party/assistant-only names retain memory dispatch. Existing new-session persistence and input privacy suites, Fast. Then actual product sequence. Do not claim model answer quality from injected contract fixtures;403 separately measured real mind. No Full yet.',
    'pending': '403 account controls system.status wrongly chosen;402b pending clarification supersedes explicit private read; private compositionES/redaction and declaration still open. No relaxation or closure.',
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
