from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
panel = base / 'astra-files75-http'
lines = ['# C03 — causa HTTP y compatibilidad de template — tramos75–76', '',
    '75 mantiene6/10 útiles,122,16s,GPU3177,56MiB,RAM7313,58MiB,exit0,registro intacto. '
    'Misma fuente74 y override Qwen3.5. Hook75 captura los errores antes ausentes, sin consumir el body '
    'BytesIO. Nueve peticiones reciben HTTP400: el template sólo permite un mensaje system al inicio. '
    'Todos estos paquetes tienen un prefijo de dos o tres system; no son errores de razonamiento del modelo.', '',
    'El [template oficial Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja), '
    'consultado2026-09-07, rechaza explícitamente un system cuyo índice no sea el primero. '
    'La restricción coincide con el backend/GGUF local medido. No se aplica como inferencia a toda la familia: '
    'Qwen3-2507 acepta los paquetes capturados, como muestran las comparaciones76.', '',
    '76 cambia sólo la serialización del prefijo: todos los textos system unidos con dos saltos de línea, '
    'en orden original, antes del mismo diálogo. Los nueve paquetes dejan de fallar en Qwen3.5. '
    'Las respuestas principales de porqué/definición/nivel son útiles; las preguntas de recuperación '
    'forzada siguen siendo innecesarias o incorrectas y no se cuentan como aceptación semántica. '
    'Selector de control conserva read.text. No se ejecutan funciones.', '',
    'Registrado2507: las respuestas principales se mantienen con/sin agrupación; una aclaración de '
    'recuperación sobre checksum cambia texto y añade reasoning_content. No declarar equivalencia '
    'de todos los tokens ni aceptación general. Recursos nativos: Qwen3.5 12,17s/GPU3175,56MiB/RAM4714,94MiB; '
    'registrado12,16s/GPU3497,56MiB/RAM2996,58MiB. Ambos manifiestos intactos. '
    'Promoción de modelo y cierre de producto siguen pendientes.', '']
paired = json.loads((panel / 'paired.json').read_text(encoding='utf-8'))
for turn in paired:
    lines += [f'## 75 / {turn["turnId"]}', '', f'Entrada: {turn["request"]}', '',
              f'Final literal: {turn["final"]}', '']
wire = [json.loads(s) for s in (panel / 'wire-36724.jsonl').read_text(encoding='utf-8').splitlines()]
for index, row in enumerate([r for r in wire if r.get('httpError')], 1):
    lines += [f'### Rechazo HTTP75 / {index}', '',
              f'Roles: {", ".join(m["role"] for m in row["payload"]["messages"])}', '',
              f'Error: {row["httpError"]["body"]}', '']
files = [panel / name for name in ('PREREG.json', 'RESULT.json', 'paired.json', 'wire-36724.jsonl')]
for model in ('qwen35', 'registered'):
    folder = base / ('astra-template76-' + model)
    files += [folder / name for name in ('PREREG.json', 'RESULT.json', 'posts.jsonl', 'llama-command.json')]
    for row in [json.loads(s) for s in (folder / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]:
        choice = row.get('response', {}).get('choices', [{}])[0]
        lines += [f'## 76 / {model} / {row["id"]} / {row["variant"]}', '',
                  f'Último mensaje: {row["payload"]["messages"][-1]["content"]}', '',
                  f'Error HTTP: {row.get("httpError", {}).get("code")}; fin: {choice.get("finish_reason")}.', '',
                  f'Respuesta bruta: {json.dumps(choice.get("message"), ensure_ascii=False)}', '']
report = base / 'PRUEBAS_TEMPLATE75_76.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files.append(report)
(base / 'TRAMO75_76_PINS.json').write_text(json.dumps({'scope': 'HTTP diagnostic and native template comparison; no model promotion',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
