"""Adjudicate source-built CPU and broader conversation; preserve every failure."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


failures = {
    'H0012': 'interpretation_failure_for_identity_question',
    'identity-variant-1': 'interpretation_failure_for_identity_question',
    'identity-variant-2': 'identity_answer_contaminated_by_interpretation_failure',
    'greeting-variant-3': 'unsupported_user_name_attribution',
    'H0241': 'grammar_failure',
    'small-talk-variant-1': 'grammar_failure',
}
reports = {}
for name, expected_count in [('source-adapter-product591', 17), ('conversation-regression592', 35)]:
    private = local / ('C03-' + name)
    private = private.with_name(private.name + '-private')
    out = base / ('astra-' + name)
    assert not (out / 'RESULT.json').exists()
    assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
    panel = read(private / 'panel.json')
    events = rows(private / 'capture/events.jsonl')
    finals = [r for r in events if r.get('type') == 'terminal']
    assert len(panel) == len(finals) == expected_count
    adjudication = []
    report = []
    for index, (case, final) in enumerate(zip(panel, finals), 1):
        verdict = failures.get(case['case_id'], 'correct') if name.endswith('592') else 'correct_with_display_precision'
        assert final['kind'] == 'published_final' and not final['timedOut']
        row = {**case, 'ordinal': index, 'verdict': verdict, 'terminal': final}
        adjudication.append(row)
        report += [f'## {index} · {case["case_id"]}', case['text'], final['final'], verdict]
    audit = rows(private / 'compose-audit.jsonl')
    report += ['## Auditoría de composición del producto', '```json', json.dumps(audit, ensure_ascii=False, indent=2), '```']
    write(private / 'adjudication.json', adjudication)
    (private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
    result = {
        'source': '590 WIP, hashes in PREREG; cross-language Full rerun pending',
        'runtime_manifest_unchanged': True, 'no_hooks': True,
        'finals': expected_count,
        'correct_finals': expected_count if name.endswith('591') else 29,
        'failed_cases': [] if name.endswith('591') else failures,
        'resources': read(out / 'resources.json'),
        'private_report_sha256': sha(private / 'RESULT.md'),
        'private_adjudication_sha256': sha(private / 'adjudication.json'),
        'ui_or_voice_credit': False,
    }
    if name.endswith('591'):
        samples = read(private / 'memory-samples.json')
        commands = {tuple(r['command']) for s in samples for r in s['processes'] if r['name'].lower() == 'llama-server.exe'}
        assert len(commands) == 1
        command = list(next(iter(commands)))
        assert command.count('--lora') == 1 and '--lora-init-without-apply' in command
        peaks, elapsed = [], []
        for sample in samples:
            ids = {r['pid'] for r in sample['processes'] if r['name'].lower() == 'baxy.exe'}
            if not ids:
                continue
            while True:
                expanded = ids | {r['pid'] for r in sample['processes'] if r['parent'] in ids}
                if expanded == ids:
                    break
                ids = expanded
            peaks.append(sum(r['rss_mib'] for r in sample['processes'] if r['pid'] in ids))
            elapsed.append(sample['elapsed'])
        result.update(effective_server_command=command, app_tree_peak_ram_mib=max(peaks),
                      app_first_sample_seconds=elapsed[0], app_last_sample_seconds=elapsed[-1],
                      compose_rejection='15.625% observed; first15% rejected, retry15.6% accepted',
                      telemetry_limit='Built-in compose audit records input context, not final HTTP sampling payload. Actual server argv proves adapter loaded; per-request scale isolation is tested in source590 owners. Do not infer absence of adapter from lora not present in this context audit.')
        note = '''# Producto591: 17 finales correctos desde fuente590

Se ejecuta el producto con el perfil candidato CPU y sin sitecustomize, monkeypatch ni wrapper de observación. Seis preguntas de topología, siete de uso y cuatro controles conservan hechos, sujeto e idioma. Una lectura15,625% produjo inicialmente15%; la guarda de precisión rechazó ese borrador y el reintento publicó15,6%. Los demás usos fueron17,1233→17%,20,6897→21%,18,75%,34,0278→34% y31,25%. Una pregunta inglesa recuperó21% del contexto precedente, sin atribuirle una lectura nueva. Modelo real AMD Ryzen7 5800H,8 físicos/16 lógicos.

El argv real captura una única carga del adaptador e28d7728 sobre Qwen3605803b/b9980. La auditoría incorporada conserva contexto y borradores; no es una captura del payload HTTP final, por lo que no acredita por sí sola cada escala0/1. Eso se comprueba en las pruebas dueñas590. El arranque real pasa la verificación del archivo y escala global0 exigida por el módulo antes de readiness.

GPU3583,559MiB. RAM del árbol completo del lanzador2551,102MiB; árbol de Baxy.exe y sus hijos2427,707MiB. Duración total96,344s, incluida compilación nativa previa; la aplicación aparece entre51,906 y96,203s. No confundir compilación con latencia de respuesta. Sin ventana/voz ni consumo conjunto final. Manifiesto intacto; candidato aún sin registrar, H0065/H0350 pendientes de promoción verificable. C03 abierto.
'''
    else:
        note = '''# Producto592: 29 finales correctos y 6 fallidos

Base registrada, fuente590 sin activar adaptador;35 turnos en orden,21 literales de encuesta y14 variantes ES/EN/mezcla, sin hooks. Las variantes de agradecimiento y los cuatro literales asociados pasan. Las seis identidades españolas restantes pasan, pero no se acredita su grupo: H0012 y What is your name? terminan explicando un fallo de interpretación; Tell me who you are. mezcla la identidad con ese fallo. Hola Atlas atribuye Atlas al usuario sin fundamento. H0241 y Estoy bien, ¿y tú? producen ¿Y tú cómo va hoy?, fallo gramatical conservado. Son29 finales correctos y6 fallidos, no35 aciertos.

Los ocho saludos literales son correctos, incluido Carter sin renombrar BAXY, pero la variante con otro nombre falla; el grupo permanece abierto conforme al panel preregistrado. El grupo de conversación breve tampoco se acredita por su gramática. H0021, antes cubierto, se reabre por el fallo de generalización inglesa de identidad. Se cubren sólo H0115/H0200/H0218/H0298, cada literal y sus tres variantes de agradecimiento leídos individualmente. Encuesta16 cubiertos/726 abiertos/0 no aplicables;742/rev1248 original intacto.

GPU3499,559MiB/RAM2419,531MiB,97,062s. Sin UI/voz ni efectos reales. La primera traza de H0012 muestra decisión nativa knowledge seguida de presentación unsupported y agotamiento de la reparación estructurada; debe localizarse esa transformación antes de tocar el modelo o añadir alias. Los fallos son desarrollo abierto, no fallo de la activación CPU: esta tanda conserva la base sin adaptador.
'''
    write(out / 'RESULT.json', result)
    (out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/astra-{name}/** -text\n')
    with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n\n' + note)
    reports[name] = adjudication

registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
backup = local / 'C03-conversation-regression592-private/requirements-before-adjudication.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = rows(backup)
now = datetime.now(timezone.utc).isoformat()
for row in requirements:
    case_id = row['case_id']
    if case_id in {'H0115', 'H0200', 'H0218', 'H0298'}:
        assert row['verification_status'] == 'open'
        row.update(verification_status='covered', generalization_status='verified_ES_EN_mixed_variants',
                   verification_updated_at=now, verification_reason='592: literal y tres variantes de agradecimiento correctos, sin efectos ni datos inventados; fuente590 con base registrada sin adaptador.')
    elif case_id == 'H0021':
        assert row['verification_status'] == 'covered'
        row.update(verification_status='open', generalization_status='failed_English_identity_in_current_dialogue',
                   verification_updated_at=now, verification_reason='592 contradice la cobertura general anterior: What is your name? y Tell me who you are. terminan en fallo de interpretación pese a ser preguntas válidas de identidad. Conservar evidencia previa y reparar la frontera de presentación.')
    elif case_id in {'H0065', 'H0350'}:
        row.update(verification_updated_at=now, verification_reason='591 verifica los17 finales desde fuente590 sin hooks, incluidos los usos CPU y variantes. Perfil candidato por entorno; falta promoción registrada y consumo conjunto, no acreditar todavía al runtime vigente.')
        row['verification_evidence'].append({'campaign': 'astra-source-adapter-product591', 'source': '590 WIP; hashes in PREREG', 'no_hooks': True, 'registered_promotion': False})
        continue
    else:
        continue
    row['verification_evidence'].append({'campaign': 'astra-conversation-regression592', 'source': '590 WIP; hashes in PREREG', 'private_adjudication': str(local / 'C03-conversation-regression592-private/adjudication.json'), 'ui_or_voice_credit': False})
counts = dict(Counter(row['verification_status'] for row in requirements))
assert counts == {'open': 726, 'covered': 16}, counts
registry.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in requirements), encoding='utf-8', newline='\n')
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), updated_at=now,
               validated_current=16,
               verification_counts={'covered': 16, 'open': 726, 'not_applicable': 0})
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=now, surveyVerificationCounts={'covered': 16, 'open': 726, 'not_applicable': 0},
             checkpoint='590 second Full running session46324 after stale current V8 pin repaired (5pass).59117 correct no-hook CPU finals;59229/35 correct,6 failures, four thanks requirements covered and H0021 reopened. Survey16/726/0.',
             continuation='Collect second Full, seal/publish590. Diagnose592 knowledge-to-unsupported transformation and identity recovery; no source edits during Full. CPU registration and joint UI/voice/resources still pending.')
write(base / 'RELEVO_ACTIVO.json', state)
print('591 and592 adjudicated; survey16covered/726open/0NA; Full rerun in progress.')
