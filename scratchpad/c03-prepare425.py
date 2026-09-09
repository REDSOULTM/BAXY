from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=local/'C03-private-product424-private';out=base/'astra-private-product424'
read=lambda p:[json.loads(l) for l in p.open(encoding='utf-8-sig')]
finals=[e for e in read(private/'capture/events.jsonl') if e['type']=='terminal']
previous=[e for e in read(local/'C03-private-product423-private/capture/events.jsonl') if e['type']=='terminal']
assert len(finals)==8 and [e['final'] for e in finals]==[e['final'] for e in previous]
samples=json.loads((private/'memory-samples.json').read_text())
min_free=min(s['available_mib'] for s in samples)
report=f'''# 424 — retirar no-mmap aumenta RAM; ambas medidas son necesarias

Una diferencia funcional frente423: carga vuelve a mmap=true, cache-ram0 sigue.
8/8terminales idénticos a423;4/8útiles y mismos4fallos. Exit0/manifiesto intacto.
RAMárbol5207,203125MiB frente3173,4296875MiB423: +2033,7734375MiB.
GPU3177,5625MiB igual,55,516s frente56s. Sin violaciones, mínimo RAM libre
{min_free:.3f}MiB. Que no corte esta vez no prueba consumo menor: entorno libre
varía. RSS cuenta páginas del archivo mapeado residentes/compartibles; no implica
que todas sean privadas irreclamables. El beneficio no-mmap es residente medido,
no se confunde con private commit.423es mejor perfil de los comparados.

Conclusión conjunta420–424: no-mmap sin limitar cache no basta; cache0 con mmap
completa pero retiene mayor working set. No-mmap+cache0 completa los mismos8,
con~3,10GiB RAM y3,10GiB VRAM. No disminuye contexto/slots/precisión/pesos.
No certifica voz/ASR/wake conjunto ni mínimo global. No nueva fuente424.

425 adoptará cache-ram0 en el perfil del backend local y no-mmap cuando hay GPU.
CPU-only conserva mmap: allí no hay offload y no se demostró mejora retirándolo.
Sin selector nuevo/configflag del producto ni cambio del modelo registrado.
Pruebas dueñas de arranque GPU/CPU y suites planner/transporte/composición;
Fast después. Full al candidato final, no ahora. Hook retirado para confirmar
comando de producción al comprobar producto posterior. Falta arreglar conducta.
'''
cases=json.loads((out/'PREREG.json').read_text())['cases']
for i,e in enumerate(finals,1):report+=f"\n{i}. {cases[i-1]}\n   {e['kind']}: {e['final']}\n"
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','PROCESS.json','EXIT.json','resources.json','RESULT.md']]+[private/n for n in ['memory-samples.json','capture/events.jsonl','server.log','http-posts.jsonl','effective-server-command.json']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
change=base/'astra-host-memory425';change.mkdir(exist_ok=False)
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Adopt only native host-memory settings supported by exact b9980 and measured423/424: cache-ram0, no-mmap only with GPU. No weights/prompt/sampling/context/slot change. Source418 behavior fixes preserved. CPU-only still uses mmap; its optional host cache disabled too, no CPU physical certification claimed.', 'evidence':['astra-private-product420','astra-private-product421','astra-private-product422','astra-private-product423','astra-private-product424'],'sources_before':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/baxy_mind/llm.py','tests/test_planner.py']},'validation':'Extend existing GPU/CPU profile tests; focused then owner suites, Fast. Product confirmation uses production command observer without flag injection. Full only on final C03 candidate.'}
(change/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
p=base/'INVESTIGACION_MODELO_C03.md';text=p.read_text(encoding='utf-8');text+='''
## Actualización 2026-09-08 — RAM del servidor,420–425

Backend exacto b9980 admite --cache-ram (8192MiB por defecto;0desactiva) y
--no-mmap. [PR16391](https://github.com/ggml-org/llama.cpp/pull/16391) distingue
la caché de prefijos en RAM del contexto activo. [PR15293](https://github.com/ggml-org/llama.cpp/pull/15293)
documenta checkpoints aparte; no se desactivaron. No es cambio del modelo.
La ayuda y logs exactos prevalecen sobre defaults actuales de master.

Con Qwen3.5-4B Q4_K_M,4096tokens×3slots,KVq8_0,ngl99, mismas8peticiones:
422no-mmap conserva cache8192 y corta con5303,99MiB RSSárbol;
423no-mmap+cache0 completa con3173,43MiB;
424mmap+cache0 completa con5207,20MiB. GPU3177,56MiB en los tres.
423/424dan8finalesidénticos,4útiles;fallos de conducta siguen abiertos.
No se certifica voz conjunta, mínimo global ni regresión integral.
425propone cache0 y no-mmap con GPU; CPU conserva mmap por falta de beneficio
medido sin offload. No nueva variable de usuario ni promoción del4Bdiagnóstico.
RESULT/PINS en cada carpeta; estado de adopción/validación en astra-host-memory425.
''';p.write_text(text,encoding='utf-8',newline='\n')
print(json.dumps({'424_minimum_free_ram_mib':min_free,'eight_finals_identical':True,'425':'preregistered'}))
