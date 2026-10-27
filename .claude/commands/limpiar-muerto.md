---
description: Busca y borra código muerto en BAXY de uno en uno, con la prueba dueña antes y después de cada borrado (ley 5, cero código muerto). Uso /limpiar-muerto [ruta o pieza].
argument-hint: "[ruta o pieza]"
---

<!-- Adaptado de commands/refactor-clean.md de everything-claude-code (MIT) 25278e7d7. -->

Ámbito: `$ARGUMENTS` (por defecto, pregunta qué pieza; no barras el repositorio entero de golpe).

1. **Detecta** sin descargar herramientas (nada de `npx knip`, `depcheck`, `ts-prune` ni `vulture`):
   - Python: `ruff check` (regla `F`: imports y locales sin usar) con el Python del runtime, y para cada
     función o clase sospechosa, `grep` de su nombre en `src tests scripts main.py`.
   - .NET: el build Release ya falla con avisos; para miembros públicos, `grep` del nombre en `src tests`.
   - FieldUi: `eslint` y `grep` de cada export.
   - Cuidado con lo que se usa por nombre: operaciones del catálogo (`"operacion.exacta"`), datos JSON,
     reflexión, scripts de PowerShell, el protocolo mente↔App. Si se nombra en un string, no está muerto.
2. **Clasifica:** seguro (helper interno sin referencias), cuidado (lo nombra un dato o un script),
   peligro (entrada, contrato, configuración: no se toca sin el dueño).
3. **Borra de uno en uno:** test dueño en verde → borra → test dueño otra vez. Si falla, deshaz sólo ese
   fichero con Edit (no `git checkout -- .`) y apúntalo como saltado.
4. **No refactorices mientras limpias.** Dos implementaciones vivas de lo mismo sí se consolidan, pero en
   un cambio aparte y con su medición si la pieza es una costura (`documentacion/03_COSTURAS.md`).
5. Informe: borrado (rutas y líneas), saltado y por qué, y la verificación final con su resultado exacto.
