# BAXY

[English](#english) · [Español](#español)

> **This is the `experimental` branch: the source code of BAXY 1.3.3, an early-access pre-release for testing.**
> The recommended version is still [BAXY 1.3.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.1) (branch `main`). What changes in 1.3.3, its known
> problems and what was not tested are in the [1.3.3 release notes](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.3).
>
> **Esta es la rama `experimental`: el código de BAXY 1.3.3, un acceso anticipado para probar.** La versión
> recomendada sigue siendo [BAXY 1.3.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.1) (rama `main`). Qué cambia en la 1.3.3, sus problemas conocidos
> y lo que no se probó están en las [notas de la 1.3.3](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.3).

## English

**BAXY runs your Windows PC with you, by voice or by text.** You ask in Spanish, English or a mix of both; BAXY
works out what to do, does it, checks that it really happened and tells you in a sentence. Its language model runs
on your own graphics card: nothing you say leaves your PC unless you ask for something from the web, or you choose
to connect a model from another company yourself. [`licenses/PRIVACIDAD.md`](licenses/PRIVACIDAD.md) lists what goes
out and to whom; since 1.3.2 the GitHub copy also asks GitHub on every start whether there is a newer version, unless
you turn that off in Settings.

- **It checks before it claims.** Every action goes through a typed catalog of operations; a Windows provider
  carries it out and returns a receipt with what it observed. "The command was sent" is not reported as success.
- **It asks first** before anything destructive, anything that sends something, or anything that closes unsaved
  work (you can turn that off).
- **It is still learning** and sometimes gets things wrong. Its voice is synthetic.

### Download

Get the installer from the [releases page](https://github.com/REDSOULTM/BAXY/releases) (the latest is
[BAXY 1.3.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.1)): download `BAXY-Instalador.exe` and open it.
It checks your PC, downloads the parts it needs, verifies each one's SHA-256 and leaves BAXY in the Start menu.
The installer is not code-signed, so SmartScreen may warn you. BAXY 1.3.3, the version of this branch, is an
early-access pre-release: its installer is on [its own page](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.3), and it is not offered through "Update".

### What you need to run it

- 64-bit Windows 11. Windows 10 has not been tested.
- **A dedicated graphics card: NVIDIA tested with 6 GB or more (4 GB untested); AMD in testing.** NVIDIA cards use
  CUDA; AMD uses Vulkan.
- About 11.1 GB free while installing (the release notes give the measured figures).
- Internet to install. BAXY itself works offline, except for what you ask of the web.

### Not tested or not supported

- Integrated graphics (Intel or AMD) and CPU only are not supported.
- A freshly formatted Windows without the Visual C++ runtime or WebView2 was not tested (the installer installs both
  from Microsoft).
- The 1.3.3 package was not tried installed on a real AMD or Intel card (its release notes say what was measured).
- "Another model" (Settings → Model) is optional and off by default. With a company's API, what you give BAXY goes to
  that company. OpenAI and Google were not tested with a real key; other models were measured against BAXY's tuned model (an
  optional extra since 1.3.2) and did worse.
- Running BAXY from a fresh clone of this repository (below) was built and unit-tested, not tried end to end with
  voice.

### Build from source

What you need: Windows 10/11 x64, the [.NET SDK 10.0.114](https://dotnet.microsoft.com/download/dotnet/10.0) (pinned
by `global.json`) and [Python 3.12](https://www.python.org/downloads/) x64. The interface (`src/Baxy.FieldUi`) is
already built in `src/Baxy.FieldUi/dist`; to change it you also need Node.js and pnpm
(`pnpm install --frozen-lockfile`, `pnpm build`).

```powershell
git clone https://github.com/REDSOULTM/BAXY.git
cd BAXY
dotnet build Baxy.slnx -c Release -warnaserror        # the App, the core, the kernel, the providers, the installer
dotnet test tests\Baxy.Kernel.Tests -c Release        # each tests\Baxy.*.Tests project the same way
```

The Python side (the "mind", `src/baxy_mind`) needs the pinned runtime: `scripts\bootstrap.ps1` creates it from
`pylock.runtime-win-x64.toml` with every hash checked; the wheels BAXY builds itself are in `runtime_wheels/`.
Then `py -3.12 -m pytest tests` runs its tests. Some tests in
`tests\Baxy.Providers.Windows.Tests` drive the real desktop: run those in a session with nothing else open.

**What is not in this repository, and how to get it:**

- **Model weights** (the language model, the vision projector, speech recognition, the voice and the wake word) and the
  `llama-server` build. They come inside the release package: install BAXY, or unpack the release `.zip` parts, and
  point BAXY at them with `scripts\register_mind_runtime.ps1` (or the `BAXY_MIND_LLM_GGUF` and
  `BAXY_MIND_LLAMA_SERVER` variables). `py -3.12 main.py` then builds what changed and starts the App. Each model
  keeps its own license: see `THIRD_PARTY_NOTICES.md`.
- **Internal notes, benchmarks and measurement data.** They hold personal data and private paths, so they are not
  published. Some code comments cite documents or benchmark scripts that are not here; the code does not need them.

### License

BAXY's own code is under the [MIT license](LICENSE). Third-party components, models and data keep their own licenses:
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (in Spanish) lists them, and [`licenses/`](licenses/README.md)
holds the full texts. You may use, copy and redistribute BAXY for any purpose, personal or commercial, as long as
you respect those licenses. What is not permissive: the voice model (BigScience OpenRAIL-M, with use restrictions that
also bind its output and anyone you pass it to), Eigen (MPL-2.0), the CUDA runtime (NVIDIA's EULA, only in the part for
NVIDIA cards), Microsoft's runtime and SDK files, and the avatar's videos and images, generated with Higgsfield and not
under the MIT license. The wake word detector (`baxy-wake-k6r-v7a` since 1.3.2) is BAXY's own network, trained
without the TV series and without the k5 teacher that the detector of 1.3.1 (`k6r-v7b`) had. Its training still raises
questions no lawyer has reviewed: it imitated the Kroko ASR encoder (CC-BY-SA), about half of its training examples
are synthetic audio from Piper voices derived from data licensed only for research or non-commercial use, and it
learned from friends' voices whose written permission is still missing (see
[`licenses/PALABRA_DE_ACTIVACION.md`](licenses/PALABRA_DE_ACTIVACION.md), `THIRD_PARTY_NOTICES.md` and the release
notes).

Since 1.3.0 the release packages carry no GPL or LGPL code: the wheels in `runtime_wheels/` are built without eSpeak NG
and without OpenBLAS. Releases 1.2.0 and 1.2.1 (withdrawn on 2026-11-07, with 1.3.0), and this repository's
history before 1.3.0, contain sherpa-onnx wheels with eSpeak NG (GPL-3.0-or-later): their complete source is in the
`*-source.zip` assets of the [`fuentes-terceros`](https://github.com/REDSOULTM/BAXY/releases/tag/fuentes-terceros) release, and the written offer in
[`licenses/FUENTES_GPL.md`](licenses/FUENTES_GPL.md). This is not legal advice.

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Español

**BAXY maneja tu PC con Windows contigo, por voz o por texto.** Le pides algo en español, en inglés o mezclando los
dos; BAXY entiende qué hacer, lo hace, comprueba que de verdad pasó y te lo cuenta en una frase. Su modelo de lenguaje
corre en tu propia tarjeta gráfica: nada de lo que dices sale de tu PC salvo que pidas algo de la web, o que tú
conectes el modelo de otra empresa. [`licenses/PRIVACIDAD.md`](licenses/PRIVACIDAD.md) dice qué sale y a quién; desde
la 1.3.2 la copia de GitHub pregunta además a GitHub en cada arranque si hay una versión nueva, salvo que lo apagues
en Ajustes.

- **Comprueba antes de afirmar.** Cada acción pasa por un catálogo tipado de operaciones; un proveedor de Windows la
  ejecuta y devuelve un recibo con lo que observó. «Se envió el comando» no se cuenta como éxito.
- **Pregunta primero** antes de lo destructivo, de lo que envía algo o de lo que cierra trabajo sin guardar (se puede
  apagar).
- **Sigue aprendiendo** y a veces se equivoca. Su voz es sintética.

### Descargar

Baja el instalador de la [página de versiones](https://github.com/REDSOULTM/BAXY/releases) (la última es
[BAXY 1.3.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.1)): descarga `BAXY-Instalador.exe` y ábrelo.
Revisa tu PC, baja las partes que necesita, comprueba el SHA-256 de cada una y deja a BAXY en el menú Inicio.
El instalador no va firmado, así que SmartScreen puede avisar. BAXY 1.3.3, la versión de esta rama, es un
acceso anticipado: su instalador está en [su propia página](https://github.com/REDSOULTM/BAXY/releases/tag/v1.3.3), y no se ofrece por «Actualizar».

### Qué necesitas para usarlo

- Windows 11 de 64 bits. Windows 10 no se ha probado.
- **Una tarjeta gráfica dedicada: NVIDIA probada con 6 GB o más (4 GB sin probar); AMD en pruebas.** Con NVIDIA usa
  CUDA; con AMD, Vulkan.
- Unos 11,1 GB libres al instalar (las notas de la versión dan las cifras medidas).
- Internet para instalar. BAXY funciona sin conexión, salvo lo que le pidas de la web.

### Sin probar o sin soporte

- Los gráficos integrados (Intel o AMD) y la CPU sola no tienen soporte.
- Un Windows recién formateado sin el runtime de Visual C++ ni WebView2 no se probó (el instalador pone los dos desde
  Microsoft).
- El paquete de la 1.3.3 no se probó instalado en una tarjeta AMD o Intel real (sus notas dicen qué se midió).
- «Otro modelo» (Ajustes → Modelo) es opcional y viene apagado. Con la API de una empresa, lo que le pases a BAXY va a
  esa empresa. OpenAI y Google no se probaron con una clave real; otros modelos se midieron frente al modelo ajustado a BAXY
  (un extra opcional desde la 1.3.2) y rindieron peor.
- Ejecutar BAXY desde un clon de este repositorio (abajo) se compiló y pasó sus pruebas, pero no se probó de punta a
  punta con voz.

### Compilar desde el código

Hace falta Windows 10/11 x64, el [SDK de .NET 10.0.114](https://dotnet.microsoft.com/download/dotnet/10.0) (fijado
en `global.json`) y [Python 3.12](https://www.python.org/downloads/) x64. La interfaz (`src/Baxy.FieldUi`) ya va
compilada en `src/Baxy.FieldUi/dist`; para cambiarla hacen falta además Node.js y pnpm
(`pnpm install --frozen-lockfile`, `pnpm build`).

```powershell
git clone https://github.com/REDSOULTM/BAXY.git
cd BAXY
dotnet build Baxy.slnx -c Release -warnaserror        # la App, el core, el kernel, los proveedores, el instalador
dotnet test tests\Baxy.Kernel.Tests -c Release        # cada proyecto tests\Baxy.*.Tests igual
```

La parte Python (la «mente», `src/baxy_mind`) necesita el runtime fijado: `scripts\bootstrap.ps1` lo crea desde
`pylock.runtime-win-x64.toml` comprobando cada hash; las ruedas que BAXY compila están en `runtime_wheels/`.
Después `py -3.12 -m pytest tests` corre sus pruebas. Algunas
pruebas de `tests\Baxy.Providers.Windows.Tests` manejan el escritorio real: córrelas en una sesión sin nada abierto.

**Qué no está en este repositorio y cómo se obtiene:**

- **Los pesos de los modelos** (el modelo de lenguaje, el proyector de visión, el reconocimiento de voz, la voz y la
  palabra de activación) y el `llama-server`. Vienen dentro del paquete de la release: instala BAXY, o descomprime las
  partes `.zip` de la release, y apunta BAXY a ellos con `scripts\register_mind_runtime.ps1` (o con las variables
  `BAXY_MIND_LLM_GGUF` y `BAXY_MIND_LLAMA_SERVER`). Luego `py -3.12 main.py` compila lo que cambió y arranca la App.
  Cada modelo conserva su licencia: ver `THIRD_PARTY_NOTICES.md`.
- **Notas internas, bancos y datos de medición.** Llevan datos personales y rutas privadas, por eso no se publican.
  Algunos comentarios del código citan documentos o scripts de medición que no están aquí; el código no los necesita.

### Licencia

El código propio de BAXY va bajo la [licencia MIT](LICENSE). Los componentes, modelos y datos de terceros conservan
sus licencias: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) los enumera y [`licenses/`](licenses/README.md)
guarda los textos completos. Puedes usar, copiar y redistribuir BAXY para cualquier fin, personal o comercial,
respetando esas licencias. Lo que no es permisivo: el modelo de voz (BigScience OpenRAIL-M, con restricciones de uso que
alcanzan también a lo que genera y a quien se lo pases), Eigen (MPL-2.0), el runtime de CUDA (EULA de NVIDIA, sólo en la
parte para tarjetas NVIDIA), los ficheros de runtime y SDK de Microsoft, y los vídeos e imágenes del avatar, generados
con Higgsfield y fuera de la licencia MIT. El detector de la palabra de activación (`baxy-wake-k6r-v7a` desde 1.3.2) es una
red propia de BAXY, entrenada sin la serie de TV y sin el maestro k5 que tenía el detector de la 1.3.1 (`k6r-v7b`). Su
entrenamiento sigue dejando dudas que ningún abogado ha revisado: imitó al encoder de Kroko ASR (CC-BY-SA), cerca de la
mitad de sus ejemplos de entrenamiento es audio sintético de voces Piper derivadas de datos con licencia sólo para
investigación o no comercial, y aprendió de voces de amigos cuyo permiso por escrito todavía falta (ver
[`licenses/PALABRA_DE_ACTIVACION.md`](licenses/PALABRA_DE_ACTIVACION.md), `THIRD_PARTY_NOTICES.md` y las notas de la
release).

Desde 1.3.0 los paquetes de las releases no llevan código GPL ni LGPL: las ruedas de `runtime_wheels/` se compilan sin
eSpeak NG y sin OpenBLAS. Las releases 1.2.0 y 1.2.1 (retiradas el 2026-11-07, con 1.3.0), y la historia de este
repositorio anterior a 1.3.0, llevan ruedas de sherpa-onnx con eSpeak NG (GPL-3.0-or-later): su código fuente completo
está en los activos `*-source.zip` de la release [`fuentes-terceros`](https://github.com/REDSOULTM/BAXY/releases/tag/fuentes-terceros), y la oferta escrita en
[`licenses/FUENTES_GPL.md`](licenses/FUENTES_GPL.md). Esto no es asesoría legal.

Las contribuciones son bienvenidas: ver [CONTRIBUTING.md](CONTRIBUTING.md).
