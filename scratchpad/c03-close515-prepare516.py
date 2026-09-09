"""Record the unsuccessful writer view and prepare the actual routing repair."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

campaign = base / 'astra-memory-view515'
results = {}
for mode in ['base', 'view']:
    out = base / f'astra-private-product515-{mode}'
    private = Path(os.environ['LOCALAPPDATA']) / f'BAXY/C03-private-product515-{mode}-private'
    events = list(map(json.loads, (private / 'capture/events.jsonl').open(encoding='utf-8-sig')))
    terminals = [r for r in events if r['type'] == 'terminal']
    assert len(terminals) == 9 and all(not r['timedOut'] for r in terminals)
    changes = [r['changes'] for r in map(json.loads, (private / 'writer-view.jsonl').open(encoding='utf-8-sig')) if r['changes']]
    for i, r in enumerate(terminals, 1):
        r.update(turn=i, useful=i not in (2, 9))
        r['reason'] = {2: 'Internal operation/system narration remains instead of BAXY explaining the saved result naturally.', 9: 'Wrong unsupported-operation rejection: private parser does not recognize the qualified memory target.'}.get(i, 'Useful and grounded final; existing confirmation and stored/conversational names preserved.')
    exit_record = json.loads((out / 'EXIT.json').read_text(encoding='utf-8-sig'))
    resources = json.loads((out / 'resources.json').read_text(encoding='utf-8-sig'))
    assert exit_record['exitCode'] == 0 and exit_record['manifest_unchanged'] and not resources['violations']
    results[mode] = {'useful': 7, 'total': 9, 'terminals': terminals, 'changes': changes, 'resources': resources, 'exit': exit_record}
    write(out / 'ADJUDICATION.json', results[mode])
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
write(campaign / 'RESULT.json', {'utc': datetime.now(timezone.utc).isoformat(), 'arms': results, 'adopted': False, 'view_session': 57540, 'view_session_exit': 0, 'baseline_session': 'Original session result lost at compaction; EXIT.json, resources, completed capture and base.log all attest exit0, no process remaining. Not rerun.', 'limits': 'Disable never reached the private operation in either arm. This does NOT exercise enabled=false filtering. True flags and false enabled remain unproven; no source adoption. Two target payloads changed, seven other finals identical. No fair global model ranking from this source diagnostic.'})
(campaign / 'RESULT.md').write_text('''# Vista del redactor: no adoptada

Ambos brazos dejan 7/9 finales útiles. Retirar estado redundante y tres indicadores falsos elimina esas palabras, pero el guardado sigue narrado como una operación del sistema. No se incorpora el filtro. Habilitar, guardar y recuperar el nombre sintético funcionan; se conserva la distinción entre memoria persistida y nombre conversacional.

El noveno turno, «Desactiva la memoria privada.», falla en ambos: el producto lo envía a la ruta pública y termina fuera de capacidades. El parser privado contiene «desactiva la memoria» y un alias con «local de baxy», pero no compone el verbo con un objetivo de memoria calificado. No es un fallo del modelo al recibir la instrucción final: el redactor recibe ya outside what I do. El control enabled=false no llegó a ejecutarse y no se da por aprobado.

Base: RAM 1577,195 MiB, GPU 3497,559 MiB, 42,984 s. Vista: RAM 1859,461 MiB, GPU 3497,559 MiB, 31,813 s. Sin violaciones y registro intacto. Dos ejecuciones de producto aislado, sin interfaz visible ni voz física; no se infiere una mejora de velocidad de estos tiempos globales. Sesión de vista 57540 recogida con exit0; base verificada por registros y ausencia de proceso, sin repetir.

Siguiente 516: reconocer la gramática acotada de habilitar/deshabilitar la memoria propia con calificadores ES/EN, retirando los alias de configuración que sustituye. Preservar negaciones, composición, otras memorias, confirmación y cifrado. Prosa de resultados y progreso siguen pendientes por separado.
''', encoding='utf-8')
write(campaign / 'PINS.json', {p.name: sha(p) for p in campaign.iterdir() if p.is_file() and p.name != 'PINS.json'})
out = base / 'astra-memory-configuration516'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-memory-configuration516-private'
private.mkdir(exist_ok=False)
for name in ['src/Baxy.App/NaturalMemoryRequestParser.cs', 'tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs']:
    (private / Path(name).name).write_bytes((root / name).read_bytes())
write(out / 'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'cause': '515 T9 loses a supported private memory disable at the exact-alias parser, before model narration. Source Classify and TryParseAuditedLiteral inspected; existing MemoryTurnSession remains owner of protection/confirmation.', 'treatment': 'Replace configuration aliases with one anchored private-memory configuration grammar: explicit enable/disable verbs and on/off constructions, own memory noun optionally qualified private/local/personal ES/EN. No general routing changes or authorization changes.', 'controls': 'Positive current aliases, qualifier combinations, polite envelopes; negative negations, quotes, definitions, capability/status questions, hypothetical requests, unrelated program/computer memories and compound requests. Assert operation and exact enabled flag; no visible answer templates.', 'validation': 'First focal tests on old source for causal red; then same tests and all owner memory integration tests. Fast after integrated source; no Full during repair. No source edit during runtime.', 'inheritance': ['515 exact payloads', 'NaturalMemoryRequestParser configuration aliases and existing owner tests', 'biblioteca/01_INVENTARIO.md memory entries and gemma4-agent/documentacion/08_memoria_jarvis/README.md: older long-term-memory layer is evidence, not authority. Reuse current encrypted private route.'], 'source_before': {str(p.relative_to(root)): sha(p) for p in [root/'src/Baxy.App/NaturalMemoryRequestParser.cs', root/'tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs']}})
note = '\n515 cerrado: ambos brazos 7/9 útiles; no adoptar filtro de metadatos. El control de deshabilitar no alcanza la operación privada: alias de configuración demasiado estrechos. 516 preparado para reparar esa primera pérdida con gramática acotada y controles de negación/otras memorias. Fuente512 sigue intacta, sin procesos de diagnóstico activos.\n'
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    with (base / name).open('a', encoding='utf-8') as stream: stream.write(note)
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='515 cerrado sin adopción; fuente512 validada; 516 preparado.', continuation='516: test causal rojo, gramática de configuración privada y validación dueña. C03 activo completo.')
write(base / 'RELEVO_ACTIVO.json', relay)
print('515 closed; 516 preregistered; source unchanged.')
