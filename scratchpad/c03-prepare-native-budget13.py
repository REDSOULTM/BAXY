import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
old = 'astra-native-primary13'
name = 'astra-native-budget13'
out = base / name
out.mkdir(exist_ok=False)
(out / 'CASES.json').write_bytes((base / old / 'CASES.json').read_bytes())
(base / f'{name}.turns.jsonl').write_bytes((base / f'{old}.turns.jsonl').read_bytes())
script = (root / 'scratchpad/c03-native-primary13.py').read_text(encoding='utf-8')
script = script.replace(old, name).replace('c03-native-primary13', 'c03-native-budget13')
script = script.replace('Thirteen development controls:', 'Paired budget diagnostic: native selection budget 96 to 256 and brief no-tool selector prose; otherwise same source, registration and ordered inputs as native-primary13. Thirteen development controls:')
(root / 'scratchpad/c03-native-budget13.py').write_text(script, encoding='utf-8')
checkpoint = base / 'CHECKPOINT.md'
previous = checkpoint.read_text(encoding='utf-8')
header = '''# C03 — CHECKPOINT — tramo41 en curso

La última respuesta al dueño confirmó una regla ya existente: no produjo progreso
de producto. Se revalida ahora la fuente y se continúa; no hay bloqueo externo.

La candidata nativa AUTO es el valor por defecto en llm.py; evita el clasificador
de tipo secundario, mantiene catálogo y grounding de argumentos. NO está aceptada.
astra-native-primary13 terminó exit0,117,22s,GPU3499,56MiB,RAM5340,90MiB,
registro intacto. Agua/aire/audio y dos horas simples funcionan. Steam y hora EN
fallan composición; negación social ES falla contrato; no-abras-Steam publica
hora inventada; detalle se corta y SSID añade analogía falsa. No reserva100.
Pruebas dueñas:1056pass,7,49s,0skip en c03-native-primary-owner2.log.
No Full ni UI41. Previo a reanudar no había procesos python/Baxy/llama-server.

Cambio posterior aún sin prueba integrada: selector nativo max_tokens96→256 y
una frase breve si se abstiene. Se prepara astra-native-budget13: mismos13casos,
fuente congelada y runtime registrado. No sobrescribir native-primary13.
Backup exacto anterior a la candidata: scratchpad/c03-native-primary-before/
llm.py y test_turn_policy.py. No revertir otros cambios acumulados.
Pendientes: alcance de negación/contrato compuesto, conocimiento, limpieza de
ramas nativas ya inalcanzables si se adopta candidata, pruebas de fronteras,
desarrollo/reserva100/ocho rutas/averías/UI/recursos/Full/publicación propios.

### Registro anterior conservado

'''
checkpoint.write_text(header + previous, encoding='utf-8')
