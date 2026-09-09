from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-gemma444'
(out/'RESULT.md').write_text('''# 444 — Gemma corrige los ocho casos básicos, no la protección completa

9/11 útiles: los8 básicos438 son correctos (Marta es respuesta breve pertinente),
incluidos Jordan/AnaMaría sin atribuirse el nombre. El mixto también conserva
turquesa/ocultación/sujeto. RedactadoES emite sintaxis de herramientas no ofrecidas
y promete recuperar, aunque ya recibió el resultado. RedactadoEN inventa que el
secreto se mostró y dejó de existir. No11/11, no promoción ni fuente.
Todos stop;9,671s/GPU1687,56640625MiB/RAM2819,671875MiB, sin violaciones,
manifiesto intacto, cliente cerrado. Diagnóstico de modelo, no recursos del
producto entero ni aceptación humana/UI/voz. El menor uso de GPU no compensa
por sí solo los dos fallos; la RAM es mayor que el diagnósticoQwen4B.

445 compara únicamente el checkpoint base ya heredado, sin adapter, sobre los
mismos11payloads. Es ablar la adaptación histórica publicada, no descargar una
colección o variar prompts/semillas para encontrar una corrida favorable.
BASE_VERIFIED.json fija740185b2; la comparación histórica ya mostró diferencias
entre base/adaptado sobre otras preguntas. Se conserva el resultado444 íntegro.
''',encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-gemma444.py').read_text(encoding='utf-8')
source=source.replace('astra-memory-gemma444','astra-memory-gemma-base445').replace('C03-memory-gemma444-private','C03-memory-gemma-base445-private')
source=source.replace('baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf','gemma4-e2b-inherited-d3b0fed4/base-gguf/gemma-4-E2B-it-Q4_K_M.gguf')
source=source.replace('9d4a5a653f2733a5faeb5f58a0e30bc064dfd569b0059cabb2547dbc4ba0f4b7','740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8')
source=source.replace("['published-gemma']", "['base-gemma']")
source=source.replace('Only GGUF changes to the existing published BAXY Gemma E2B asset.', 'Only GGUF changes from444 published adaptation to the existing verified standard Gemma E2B base asset; no adapter.')
source=source.replace('Qwen4B/9B both fail attribution with current memory data;', '444 published Gemma improves8/8 basic cases but emits phantom tools for redactedES and invents redactedEN deletion. Ablate adaptation using its existing standard base. Qwen4B/9B both fail attribution with current memory data;')
target=root/'scratchpad/c03-memory-gemma-base445.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
 path=base/name;content=path.read_text(encoding='utf-8')
 start=content.index('## Siguiente acción');end=content.index('## Pendientes completos',start)
 content=content[:start]+'''## Siguiente acción
444 Gemma publicado9/11: ocho básicos438 ymixto correctos; redactadoES fake
tools/recuperación, EN inventa mostrado/eliminado. RESULT/PINS, no promoción.
GPU1687,57MiB/RAM2819,67MiB sólo diagnóstico, no producto.445 preparado compara
únicamente baseGemma ya existente/hash740185b2 sin adapter, mismos11payloads.
Ejecutar c03-memory-gemma-base445.py. No fuente mientras modelo. Si mejora,
guarded/producto/regresión/registro siguen obligatorios. Fuente436; C03 completo.
Mensaje18 dueño reitera estado/minimizarVRAM+RAM con calidad/rendimiento yAgents/
identidad; id01a081bf-b744-77b1-ada9-9ab23885bd47. No reinicia ni reducegoal.

''' +content[end:]
 content=content.replace('443 rechazado; diagnóstico444 preparado','4449/11; diagnóstico445 preparado').replace('No editar fuente durante444.','No editar fuente durante445.').replace('17mensajes consolidados','18mensajes consolidados')
 path.write_text(content,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json';record=json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),continuation='444 publishedGemma9of11: all8 basic but2protected errors.445 base ablation prepared, existing asset,11samepayloads. No promotion/source, fullgoalactive. Owner18 reinforces resources/quality/performance.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('444 recorded;445 prepared; source436 unchanged')
