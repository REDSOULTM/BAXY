# Auditoría de los pedidos reales del dueño y arreglo por skills

Eres la sesión del PC (líder) de BAXY Renew, en `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew` (rama
`baxy-renew`, producto de partida `845d652ad`). El notebook es tu apoyo por el buzón (`bash scripts/buzon.sh`).
Lee antes `AGENTS.md`, `artifacts/renew/INFORME_FINAL.md` y, en `artifacts/renew/PROGRESO.md`, las secciones
«Consolidación» y «Producto final». Termina cuando se cumplan los `<criterios_de_termino>`.

<mision>
Saber, pedido por pedido, qué hace BAXY con lo que el dueño pide de verdad, y subir lo que más falla. Los arreglos se
hacen con skills, descripciones y prompts, nunca con reglas en código que interpreten a la persona.
</mision>

<entradas>
- Pedidos reales del dueño: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo\tests\data\historical_missions.jsonl`
  (2.084 misiones canónicas; campos `examples`, `message_count`, `historical_operations`, `expected_state`,
  `denied_operations`, `class`, `languages`, `fallback`). Es privado y lo ignora git. Sólo se lee: el worktree de BAXY
  Definitivo no se toca. Lo copias una vez a `F:\BAXYeval\reales_v1\` y trabajas sobre esa copia.
- Equivalencias de operaciones viejas a las del catálogo actual: `scripts/renew/catalog_equivalence.json`.
- Bancos abiertos para comparar: `F:\BAXYeval\renew_v1\practica\decision2.json` y los `practice.json` de escenas, e2e y
  falsedades.
- No abras nunca un archivo sellado (`sealed.json`, `holdout*.frozen.json`, `renew_v1\holdout\decision.json`, todo lo que
  liste un `SEALED*.md`). Algunos pedidos reales pueden haber alimentado esos holdouts. Por eso el holdout que midas al
  final debe ser nuevo (ver la fase 0).
</entradas>

<reglas>
1. **Ningún arreglo en código que interprete a la persona.** Quedan prohibidos los regex sobre el texto de la persona,
   las reglas semánticas, las listas de palabras, los vetos, las guardias por frase y los pasos dictados en código
   («si dice X, llama a Y»). Un parche así esconde el límite del modelo y se rompe con la siguiente frase distinta.
2. **Los arreglos permitidos son sólo estos:**
   - **Skills nuevas**, como operaciones tipadas del catálogo (`ProductCatalog.cs`, con su handler y su proveedor).
     El proveedor verifica el efecto antes de darlo por hecho, y el kernel pide confirmación según el riesgo. Una
     skill puede hacer de una vez una tarea de varios pasos (como `message.draft` o `game.install.named`), siempre
     que verifique cada efecto.
   - **Descripciones** de herramientas y significados de argumentos (`src/baxy_mind/data/tool_descriptions.en.v1.json`),
     y textos en español del catálogo.
   - **Prompt de sistema y protocolo** de la mente (`src/baxy_mind/mind.py`, `protocol.py`): presentación, orden y
     formato de lo que el modelo ve. Nunca reglas que lean el texto de la persona.
   - **Inferencia**: parámetros de llama-server o de muestreo, dentro de los 4 GB.
3. **Honestidad.** Nada se da por hecho sin ejecutarlo y verificarlo. Ninguna descripción promete lo que el código no
   hace: un «todos/all», un orden, un total, un código de error o un formato falsos. Ningún corte se calla si el recibo
   no lo marca.
4. **Investiga y cita la fuente** (archivo:línea, papers, documentación oficial) antes de afirmar o implementar.
5. **≤4 GB de VRAM y ≤4 GB de RAM, por diseño.** No propongas más VRAM ni un modelo más grande. El modelo es
   Qwen3.5-4B-Q4_K_M con contexto de 49.152 tokens.
6. **Presupuesto del prefijo.** Hoy son 41.268 tokens de herramientas y sistema, medidos en el calentamiento de
   llama-server (`prompt_n`). No puede crecer más de 1.000 tokens en total. Cada skill nueva se paga condensando otra
   descripción o uniéndola a una familia con un argumento, como `web.search` y su `source`. Mide el prefijo tras cada
   cambio.
7. **Seguridad y privacidad.**
   - Nada del dueño sale de la máquina. Sus textos literales no entran en git: el detalle caso por caso vive en
     `F:\BAXYeval\reales_v1\`, y el repo sólo lleva cifras, ids y descripciones genéricas.
   - Sólo se sube a hub; origin necesita la confirmación del dueño.
   - Nunca dos Baxy.exe a la vez.
   - No toques el Discord ni el Spotify del dueño, ni sus apps abiertas.
   - No mandes nada a personas reales, no compres nada y no borres fuera del sandbox.
   - Protege las herramientas del sistema: el incidente de msconfig está en PROGRESO.
   - CryptSvc sigue en Manual.
   - Nadie toca Git LFS.
</reglas>

<fases>
**Fase 0. Separar antes de mirar.**
- Divide las 2.084 misiones, con una semilla fija y estratificando por `class`, en:
  - **ajuste**, el 70 %: se abre y se usa para trabajar;
  - **holdout**, el 30 %.
- Que la división la escriba un subagente aislado. El holdout se sella con sha256 y fecha en `metas.json` y nadie lo
  abre hasta la fase 4.
- Excluye de las dos partes lo que no se puede medir sin efectos reales sobre terceros (enviar a personas, comprar,
  borrar fuera del sandbox). Esas misiones sólo se clasifican por la decisión.

**Fase 1. Clasificar el conjunto de ajuste**, una misión por fila, con un ejemplo o más de cada una.
- Decisión, en las dos GPUs: el arnés de `scripts/renew/bench_decision.py`, con `historical_operations` y
  `expected_state` como oráculo (mapeados con `catalog_equivalence.json`) y tu juicio cuando el oráculo es viejo.
  Apunta tu juicio.
- Ejecución: sólo en el notebook, con el conductor de `bench_e2e.py` y perfiles bajo `%LOCALAPPDATA%\BAXY`. Corre ahí
  las misiones cuya decisión sale bien y que se pueden ejecutar sin riesgo.
- Clases, una por misión:
  - **OK**: decide bien y ejecuta bien.
  - **ELIGE_MAL**: la skill existe, pero el modelo elige otra, se equivoca de argumentos, pregunta sin necesidad o no
    pregunta cuando falta un dato.
  - **EJECUTA_MAL**: decide bien, pero la ejecución falla, se queda a medias o el recibo no verifica.
  - **FALTA_SKILL**: ninguna operación del catálogo lo hace.
  - **FUERA_DE_DISEÑO**: es peligroso, necesita más de 4 GB o el dueño lo descartó. BAXY debe decir que no lo hace.
  - **FALSEDAD**: la respuesta afirma algo no hecho o no leído. Puede ir junto a otra clase.
- Para cada misión que no sea OK, anota: la causa con archivo:línea o la descripción implicada, la frecuencia
  (`message_count`) y una propuesta de arreglo **de las permitidas**.

**Fase 2. Priorizar.**
- Agrupa los fallos por causa común y ordénalos por frecuencia × fallo.
- Entrega un informe corto para el dueño en `artifacts/renew/auditoria_reales.md`: cifras por clase, los 20 grupos
  que más pesan y el arreglo propuesto para cada uno. Ningún texto literal del dueño.
- Avisa al dueño y sigue, sin esperar su respuesta salvo que una decisión sea suya.

**Fase 3. Arreglar de uno en uno, midiendo.**
- Por cada grupo, de mayor a menor peso:
  1. aplica un arreglo permitido;
  2. corre las 4 suites y compila la App;
  3. mide decisión s0-2, escenas (sin tocar más 3 perturbaciones neutras) y e2e s0-2. Compara con la base de
     `845d652ad` (decisión 229,67 ±3; escenas 30,5 ±2; e2e 19,67 ±1), en la GPU que mostró el efecto;
  4. mide la clase de ese grupo en el conjunto de ajuste.
- Se queda sólo lo que no baja ningún banco y sube su grupo. Lo que baja se revierte y se anota.
- Una skill nueva lleva sus pruebas en Providers o Kernel y su descripción con sus topes reales.
- Cada arreglo es un commit con su medida en `PROGRESO.md`.
- El notebook nunca queda sin tarea: una GPU mide mientras la otra prepara.

**Fase 4. Medir una vez.**
- Corre el holdout de la fase 0 una sola vez sobre el HEAD final: decisión en las dos GPUs y ejecución en el
  notebook.
- Anota las cifras por clase y compáralas con las del conjunto de ajuste.
</fases>

<criterios_de_termino>
- La fase 1 está completa: cada misión del conjunto de ajuste tiene su clase, su causa y su arreglo propuesto, y
  `auditoria_reales.md` está entregado.
- Se aplicaron y midieron todos los arreglos permitidos que suben un grupo sin bajar ningún banco. Un grupo que no
  sube con ninguno se cierra como límite honesto, con su evidencia.
- El prefijo no creció más de 1.000 tokens, y los 4 GB se cumplen (medidos).
- El holdout de la fase 0 se corrió una vez sobre el HEAD final, con sus cifras anotadas.
- `PROGRESO.md` y `metas.json` están al día; commit y push a hub; informe final corto para el dueño con lo que mejoró
  (en cifras), lo que no y lo pendiente.
</criterios_de_termino>
