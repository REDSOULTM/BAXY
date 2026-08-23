# Arranque en un PC nuevo — dejar BAXY corriendo en el estado de hoy

Estado que se replica: **goals 01–05 cerrados** (el 05 el 2026-08-21,
`documentacion/base/05_EJECUCION_VERIFICADA.md`). Lo siguiente que se lanza es el
**goal 06**, [`06_VOZ_DEL_PRODUCTO.md`](06_VOZ_DEL_PRODUCTO.md).

Sustituye al procedimiento del [`03B_PROMPT_SOL.md`](03B_PROMPT_SOL.md), que hacía
lo mismo para el goal 03B y quedó como archivo.

## Antes de salir de este PC — dos cosas que no hace el agente

1. **Publicar el estado.** Hecho el 2026-08-23: los 101 commits de los goals
   01–05 ya están en `origin/main`. Si vuelves a trabajar aquí, lo que no se
   empuje no llega, así que antes de salir:

   ```powershell
   git push origin main
   git rev-list --count origin/main..main   # tiene que dar 0
   ```

2. **Copiar los ~4,2 GB que git no lleva.** `assets.manifest.json` lo dice
   explícito: *BAXY no descarga modelos automáticamente*. USB o red:

   | Pieza | Dónde está hoy | Cuánto | SHA-256 |
   |---|---|---|---|
   | `Qwen3-4B-Q4_K_M.gguf` — el decisor | `D:\BAXYRuntime\assets\models\` | 2,4 GB | `7485fe6f…` |
   | `llama-b9980` — llama-server CUDA 12.4 + sus DLL | `…\Programacion\BAXY\legacy\models\artifacts\llama-b9980\` | 1,14 GB | `llama-server.exe` = `38a9d28e…` |
   | `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` — STT | `C:\Users\usuario\.gemma4\models\` | 640 MB | lo recalcula `register_mind_runtime.ps1` |

   Las tres son `required: true`. Wake, TTS neural, visión, OCR, mpv y yt-dlp son
   opcionales: que falten no impide arrancar (los pide el goal 09).

3. Opcional, sólo si el goal en curso hereda de ellas: las pilas vecinas
   `Programacion\BAXY`, `Programacion\FunctionGemma`, `Programacion\Probando Gemma 4`.
   El goal 06 no las necesita — su herencia (`biblioteca/`, 1.350 documentos) sí
   viaja dentro del repositorio.

## El prompt de arranque

Se pega entero en una sesión nueva del agente **en el PC nuevo**. Sólo prepara el
terreno y demuestra que la máquina mide igual; no toca el producto ni lanza ningún
goal.

```
Vas a dejar BAXY Definitivo corriendo en este PC, en el estado en que está hoy en
el PC del dueño. NO toques el producto y NO empieces ningún goal: este trabajo
termina cuando la máquina compila, mide y arranca igual que la de origen, y lo
dices con los números exactos.

Windows, PowerShell. Permisos totales para instalar lo que falte. Si algo no se
puede resolver, PARA y dilo con el error literal — no lo sustituyas por algo
parecido.

PASO 1 — REQUISITOS. Comprueba y, si falta, instala:
  - .NET SDK exactamente 10.0.100 (global.json lleva rollForward: disable; otra
    versión no vale): dotnet --version
  - CPython 3.12 x64: py -3.12 -V
  - git, y Node LTS con pnpm (la compuerta corre ESLint y tsc de src/Baxy.FieldUi)
  - GPU NVIDIA con CUDA 12.x si la hay. Si no hay GPU, se arranca con -Cpu y lo
    dices: los tiempos publicados no serán comparables.

PASO 2 — CLONAR. Rutas largas primero o el clon muere con "Filename too long":

    git config --global core.longpaths true
    git clone https://github.com/REDSOULTM/baxy-definitivo.git "BAXY Definitivo"

  Clónalo en la MISMA ruta que el PC de origen —
  C:\Users\<usuario>\Desktop\ETC\Programacion\BAXY Definitivo — porque los goals
  la citan literal. Son ~130 MB con un JSONL de 70 MB dentro: tarda.
  Después, desde la raíz:

    git log --oneline -1        # el último de origin/main; git ls-remote origin main lo dice
    git status --short          # TIENE que salir vacío

  Si git status marca ficheros modificados nada más clonar, es el final de línea:
  .gitattributes declara eol=lf. No lo "arregles" commiteando — dilo y para.

PASO 3 — LOS ACTIVOS QUE NO VIAJAN. Copia del PC de origen (el dueño te los da
por USB o red) y déjalos en un único raíz, con esta forma exacta:

    <RAIZ>\models\Qwen3-4B-Q4_K_M.gguf
    <RAIZ>\llama-b9980-cuda12.4\llama-server.exe   (con todas sus DLL al lado)
    <RAIZ>\stt\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8\

  Declara el raíz de forma persistente, que es como assets.manifest.json los
  encuentra sin tocar el repositorio:

    [Environment]::SetEnvironmentVariable('BAXY_ASSETS_ROOT','<RAIZ>','User')

  Verifica el decisor por hash antes de seguir — si no coincide, PARA: cambiar el
  modelo invalida toda la comparación con lo publicado:

    (Get-FileHash '<RAIZ>\models\Qwen3-4B-Q4_K_M.gguf' -Algorithm SHA256).Hash
    # 7485FE6F11AF29433BC51CAB58009521F205840F5B4AE3A32FA7F92E8534FDF5

  Y llama-server.exe: 38A9D28EA414442590486459A7D1F5E32655DB83148B7A114B79CD1AD242946E

PASO 4 — RUNTIME. Diagnostica antes de mutar la máquina:

    .\scripts\bootstrap.ps1 -CheckOnly

  Lista qué activos resuelven. Sólo tres tienen que salir encontrados:
  conversation_model, llama_server y stt_parakeet. Los demás, opcionales.
  Cuando esos tres estén, ejecútalo de verdad:

    .\scripts\bootstrap.ps1          # añade -Cpu si no hay GPU

  Crea el Python 3.12 aislado en %LOCALAPPDATA%\BAXYRuntime\python, instala las
  dependencias bloqueadas por hash y escribe el manifiesto
  %LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json. Ábrelo y comprueba una cosa
  concreta: python_path apunta al src DE ESTE CLON. Si apunta a otro sitio, cada
  medición ejecutará el baxy_mind del repositorio vecino — es un fallo que ya
  costó una campaña entera y está en documentacion/base/03_COMPRENSION.md §3.

PASO 5 — LAS DOS CADENAS QUE LA COMPUERTA EXIGE Y EL BOOTSTRAP NO PONE:

    Push-Location .\src\Baxy.FieldUi ; pnpm install --frozen-lockfile ; Pop-Location
    # no ejecutes pnpm build: dist/ está sellado y no se toca

    py -3.12 -m venv "$env:LOCALAPPDATA\BAXYQuality\source-quality-v1"
    & "$env:LOCALAPPDATA\BAXYQuality\source-quality-v1\Scripts\python.exe" -m pip install -r .\requirements-quality-win-x64.lock.txt
    # ruff 0.15.22 exacto; la compuerta compara la versión y falla si no cuadra

  Si pnpm install cambia pnpm-lock.yaml, revierte el lock y dilo: el árbol tiene
  que quedar limpio.

PASO 6 — LA COMPUERTA ENTERA. En segundo plano, tarda:

    .\scripts\test_source_quality.ps1 -Mode Full

  Sirve si: imprime source_quality_gate_passed con exit 0, cero fallos en .NET y
  en pytest, y las únicas omitidas dicen "environment" en su mensaje. Un skip no
  es un pass: repórtalo como «suite X: N pass, M skips ambientales». git status
  --short tiene que seguir vacío después.
  Referencia histórica del goal 02 (2026-08-16, hoy serán más): .NET 3.864 pasan
  / 0 fallan / 1 omitida; pytest 8.503 pasan / 11 omitidas en clon limpio.
  Publica los números REALES de esta máquina: son la línea base de este PC.

PASO 7 — QUE LA MENTE MIDE IGUAL. Compila y corre la medición de referencia:

    dotnet build Baxy.slnx -c Release --nologo -v:minimal
    py -m experiments.mind_router_spike.run_goal03_comprehension --label arranque

  Una corrida son ~7 minutos y NO se corren dos a la vez (se pisan el fichero de
  audit y el síntoma es un JSONDecodeError, no un error de recursos).
  Lo publicado por el goal 03C el 2026-08-21 son tres corridas de 116, 114 y 113
  sobre 124 dentro de catálogo — mediana 114 — con 0, 1 y 1 de 36 fuera de
  catálogo `acted`. Si esta máquina da 113–116, mide igual. Si da mucho menos,
  algo del paso 3 o del paso 4 apunta a donde no es: no sigas, arréglalo.

PASO 8 — EL PRODUCTO ARRANCA:

    py main.py

  Es el único arranque de desarrollo. Escríbele una petición sencilla, comprueba
  que contesta y que hace lo que dice, y ciérralo.

PASO 9 — LA HERRAMIENTA CON LA QUE SE LANZAN LOS SPRINTS. Instala el CLI de grok
(los goals se lanzan con Grok 4.6, esfuerzo high) y deja instalado el bloque de
skills de este repositorio:

    .\.grok\install-config.ps1
    grok inspect          # las skills ajenas al proyecto salen [disabled]

  El porqué y cómo se mide está en .grok/README.md. Si el dueño trabaja con otro
  agente, dilo y no instales nada.

PASO 10 — INFORME Y PARA. Una tabla con: commit en el que quedó el clon, versión
de .NET y de Python, ruta de BAXY_ASSETS_ROOT, ruta del manifiesto de runtime,
resultado literal de la compuerta con sus números, cifra de la corrida de
arranque, y si `py main.py` levantó. Después PARA. No empieces ningún goal: eso lo
lanza el dueño en una sesión nueva y limpia, una por goal.

LO QUE NO PUEDES HACER
- Sustituir el modelo, el llama-server o el STT por otra versión "equivalente".
- Cerrar un rojo con skip, xfail, umbral relajado o fallback.
- Commitear nada que no sea, como mucho, el informe: el árbol se queda limpio.
- Trabajar en la carpeta Programacion\BAXY a secas — ése es el intento anterior,
  fuente de herencia y no sitio de trabajo.
```

## Cuando el informe cuadre — lanzar los sprints

Una sesión nueva y limpia **por goal**, no una por día:

```powershell
grok
/effort high
/goal <el contenido íntegro de documentacion/sprints/06_VOZ_DEL_PRODUCTO.md>
```

`/goal status` para ver dónde está. El goal no se da por cumplido hasta que una
revisión de evidencia independiente reproduce el resultado — es el invariante 2
aplicado al agente. Detalle en [`00_INDICE.md`](00_INDICE.md) y en
[`../../.grok/README.md`](../../.grok/README.md).

Orden de lo que queda: **06** → 07 → 08 → 09 → 10 → 11.
