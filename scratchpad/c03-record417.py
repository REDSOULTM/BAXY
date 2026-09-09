from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-os-product417'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-os-product417-private'
raw = json.loads((private / 'adjudication-input.json').read_text(encoding='utf-8'))
exit_result = json.loads((out / 'EXIT.json').read_text())
assert exit_result['exitCode'] == 0 and exit_result['manifest_unchanged']
assert len(raw['turns']) == len(raw['terminal']) == 9
assert all(x['admissionStatus'] == 200 and not x['timedOut'] and x['kind'] == 'published_final' for x in raw['terminal'])
names = {v for r in raw['reads'] if r['operation'] == 'system.identity' for v in r['response']['result'].values() if isinstance(v, str) and v}
def sanitize(s):
    for name in sorted(names, key=len, reverse=True):
        s = s.replace(name, '[WINDOWS_IDENTITY]')
    return s
reasons = ['Cuenta efectiva leída y explicada; frío conserva411.', 'Cuenta efectiva leída en español.', 'Sigue aclarando si debe hacer la lectura ya solicitada; no corregido por416.', 'Cuenta efectiva leída en español.', 'Nombre y edición reales de Windows 11 coinciden con CIM independiente; build 26200 conservado.', 'Explicación conceptual útil sin nueva operación.', 'Windows 11 y edición correctos; llama versión a la compilación, imprecisión terminológica sin cambiar el dato.', 'Memoria total observada 16539508736 bytes, respuesta redondeada 16 GB útil.', 'Modelo AMD Ryzen 7 5800H with Radeon Graphics observado y explicado en español.']
report = ['# 417 — producto: 8/9 útiles; Windows corregido, aclaración de cuenta pendiente', '',
    'Mismos seis turnos411 en orden: 4/6→5/6 útiles. Tres controles añadidos OS ES/RAM EN/CPU ES pasan. Nueve admisiones200 y finales, sin timeout ni silencio; exit0, manifiesto intacto, todos los procesos del diagnóstico cerrados.', '',
    'Tres lecturas system.identity y cuatro system.status verificadas. Dos OS incluyen Caption igual al observado por CIM416; no se inyectaron hechos ni respuestas. El proveedor y su transporte corregidos están en fuente416. Se conserva la bienvenida y el flujo real. T3 sigue en aclaración innecesaria; 413/414 no se adoptan.', '',
    'No VRAM medida en esta tanda, ni UI visible/voz física/aceptación humana. El snapshot RAM de T8 muestra sólo 216190976 bytes disponibles en ese momento; la respuesta informa capacidad total correctamente, pero esta corrida no acredita margen de RAM conjunto. No extrapolar recursos de composición415 al producto completo.', '',
    'Identidad Windows oculta únicamente en este informe; originales privados intactos. Desarrollo sintético, no suma a los cien frescos. Siguiente bloqueo: precedencia de la aclaración pública sobre una ruta privada de memoria ya reconocida por su parser. Pruebas nuevas antes de editar ese owner.', '']
for number, (turn, reason) in enumerate(zip(raw['turns'], reasons, strict=True), 1):
    report += [f"## {number} — {'fallo' if number == 3 else 'útil'}", '', turn['request'], '']
    for reply in turn['answers']:
        report += ['> ' + sanitize(reply['text']).replace('\n', '\n> '), '', 'Ruta: ' + str(reply['route']), '']
    report += [reason, '']
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8', newline='\n')
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'EXIT.json', 'PROCESS.json']]
paths += [private / n for n in ['capture/events.jsonl', 'http-posts.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl', 'adjudication-input.json']]
paths += [private.parent / 'C03-os-profile417/journal/missions.jsonl']
(out / 'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+'\n', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    p = base / name
    s = p.read_text(encoding='utf-8').replace('416 implementado y validado; producto417 preparado', '416 validado; producto417 8/9; memoria418 en diagnóstico')
    start = s.index('RESULT/PINS en astra-os-provider416.')
    end = s.index('\n\nPendiente:', start)
    s = s[:start] + '''RESULT/PINS en astra-os-provider416. Producto417 cerrado y documentado: 8/9
útiles, mismos seis411 4/6→5/6 más tres controles correctos. Windows 11 ES/EN,
RAM y CPU bien. Account T3 sigue aclarando innecesariamente. 9 finales/admisiones
200, sin timeout/silencio. No UI/voz ni VRAM medida; RAM libre T8 sólo206 MiB,
comprobar memoria disponible antes del próximo modelo. Manifiesto intacto.
Siguiente418: MindShellEndToEndTests.ExplicitPrivateMemoryRequestSupersedesMindClarification
añade cuatro casos ES/EN para reproducir cómo la aclaración pública intercepta
memory.recall/status. Aún no editado MainWindowViewModel para esta causa. Heredar
el flujo privado existente y la distinción de solicitud completa/fragmento.
''' + s[end:]
    p.write_text(s, encoding='utf-8', newline='\n')
p = base / 'RELEVO_ACTIVO.json'
relay = json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='416 validated;417 product 8/9, OS fixed, account redundant clarification open. Models closed.', continuation='418 baseline four private-memory requests after pending public clarification; fix owner precedence only if reproduced, preserve cancellation/fragment/private authorization. Full C03 active.')
p.write_text(json.dumps(relay, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print('417 recorded;418 baseline next')
