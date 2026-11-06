# BAXY

[English](#english) · [Español](#español)

## English

**BAXY runs your Windows PC with you, by voice or by text.** You ask in Spanish, English or a mix of both; BAXY
works out what to do, does it, checks that it really happened and tells you in a sentence. Its language model runs
on your own graphics card: nothing you say leaves your PC unless you ask for something from the web, or you choose
to connect a model from another company yourself.

- **It checks before it claims.** Every action goes through a typed catalog of operations; a Windows provider
  carries it out and returns a receipt with what it observed. "The command was sent" is not reported as success.
- **It asks first** before anything destructive, anything that sends something, or anything that closes unsaved
  work (you can turn that off).
- **It is still learning** and sometimes gets things wrong. Its voice is synthetic.

### Download

Get the installer from the [releases page](https://github.com/REDSOULTM/BAXY/releases) (the latest is
[BAXY 1.2.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.2.1)): download `BAXY-Instalador.exe` and open it.
It checks your PC, downloads the parts it needs, verifies each one's SHA-256 and leaves BAXY in the Start menu.
The installer is not code-signed, so SmartScreen may warn you.

### What you need to run it

- Windows 10 or 11, 64-bit.
- **A dedicated NVIDIA or AMD graphics card with 4 GB of memory or more.** NVIDIA cards use CUDA; AMD uses Vulkan.
- About 13 GB free while installing.
- Internet to install. BAXY itself works offline, except for what you ask of the web.

### Not tested or not supported

- Integrated graphics (Intel or AMD) and CPU only are not supported.
- A freshly formatted Windows without the Visual C++ runtime or WebView2 was not tested (the installer installs both
  from Microsoft).
- A real AMD or Intel card was not tested for the CUDA/Vulkan split of 1.2.1: it was simulated.
- "Another model" (Settings → Model) is optional and off by default. With a company's API, what you give BAXY goes to
  that company. OpenAI and Google were not tested with a real key; other models do worse than BAXY's own.
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
`pylock.runtime-win-x64.toml` with every hash checked, and that lock includes the sherpa-onnx wheel described below,
so build that wheel first. Then `py -3.12 -m pytest tests` runs its tests. Some tests in
`tests\Baxy.Providers.Windows.Tests` drive the real desktop: run those in a session with nothing else open.

**What is not in this repository, and how to get it:**

- **Model weights** (BAXY's model, the vision projector, speech recognition, the voice and the wake word) and the
  `llama-server` build. They come inside the release package: install BAXY, or unpack the release `.zip` parts, and
  point BAXY at them with `scripts\register_mind_runtime.ps1` (or the `BAXY_MIND_LLM_GGUF` and
  `BAXY_MIND_LLAMA_SERVER` variables). `py -3.12 main.py` then builds what changed and starts the App. Each model
  keeps its own license: see `THIRD_PARTY_NOTICES.md`.
- **The patched sherpa-onnx wheel** used for speech recognition. sherpa-onnx compiles eSpeak NG in, which is
  GPL-3.0-or-later, so its binary is not kept here. Build it with `scripts\build_sherpa_runtime.py` (the recipe and
  its two patches are in `runtime_wheels/`; the complete source is in the `*-source.zip` assets of
  [release 1.2.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.2.1)) and re-lock with
  `scripts\lock_python_dependencies.ps1`, because a rebuild is not byte-identical. The installed release already
  carries a complete Python runtime with this wheel installed (its `python` folder). Neither path was tried from
  this snapshot.
- **Internal notes, benchmarks and measurement data.** They hold personal data and private paths, so they are not
  published. Some code comments cite documents or benchmark scripts that are not here; the code does not need them.

### License

BAXY's own code is under the [MIT license](LICENSE). Third-party components, models and data keep their own licenses:
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (in Spanish) lists them, and [`licenses/`](licenses/README.md)
holds the full texts. The release packages also carry GPL code (eSpeak NG); its source and the written offer are
described in [`licenses/FUENTES_GPL.md`](licenses/FUENTES_GPL.md). This is not legal advice.

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Español

**BAXY maneja tu PC con Windows contigo, por voz o por texto.** Le pides algo en español, en inglés o mezclando los
dos; BAXY entiende qué hacer, lo hace, comprueba que de verdad pasó y te lo cuenta en una frase. Su modelo de lenguaje
corre en tu propia tarjeta gráfica: nada de lo que dices sale de tu PC salvo que pidas algo de la web, o que tú
conectes el modelo de otra empresa.

- **Comprueba antes de afirmar.** Cada acción pasa por un catálogo tipado de operaciones; un proveedor de Windows la
  ejecuta y devuelve un recibo con lo que observó. «Se envió el comando» no se cuenta como éxito.
- **Pregunta primero** antes de lo destructivo, de lo que envía algo o de lo que cierra trabajo sin guardar (se puede
  apagar).
- **Sigue aprendiendo** y a veces se equivoca. Su voz es sintética.

### Descargar

Baja el instalador de la [página de versiones](https://github.com/REDSOULTM/BAXY/releases) (la última es
[BAXY 1.2.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.2.1)): descarga `BAXY-Instalador.exe` y ábrelo.
Revisa tu PC, baja las partes que necesita, comprueba el SHA-256 de cada una y deja a BAXY en el menú Inicio.
El instalador no va firmado, así que SmartScreen puede avisar.

### Qué necesitas para usarlo

- Windows 10 u 11 de 64 bits.
- **Una tarjeta gráfica dedicada NVIDIA o AMD con 4 GB de memoria o más.** Con NVIDIA usa CUDA; con AMD, Vulkan.
- Unos 13 GB libres al instalar.
- Internet para instalar. BAXY funciona sin conexión, salvo lo que le pidas de la web.

### Sin probar o sin soporte

- Los gráficos integrados (Intel o AMD) y la CPU sola no tienen soporte.
- Un Windows recién formateado sin el runtime de Visual C++ ni WebView2 no se probó (el instalador pone los dos desde
  Microsoft).
- El reparto CUDA/Vulkan de 1.2.1 no se probó en una tarjeta AMD o Intel real: se simuló.
- «Otro modelo» (Ajustes → Modelo) es opcional y viene apagado. Con la API de una empresa, lo que le pases a BAXY va a
  esa empresa. OpenAI y Google no se probaron con una clave real; otros modelos rinden peor que el propio de BAXY.
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
`pylock.runtime-win-x64.toml` comprobando cada hash, y ese lock incluye la rueda de sherpa-onnx de abajo, así que
primero hay que compilarla. Después `py -3.12 -m pytest tests` corre sus pruebas. Algunas
pruebas de `tests\Baxy.Providers.Windows.Tests` manejan el escritorio real: córrelas en una sesión sin nada abierto.

**Qué no está en este repositorio y cómo se obtiene:**

- **Los pesos de los modelos** (el modelo de BAXY, el proyector de visión, el reconocimiento de voz, la voz y la
  palabra de activación) y el `llama-server`. Vienen dentro del paquete de la release: instala BAXY, o descomprime las
  partes `.zip` de la release, y apunta BAXY a ellos con `scripts\register_mind_runtime.ps1` (o con las variables
  `BAXY_MIND_LLM_GGUF` y `BAXY_MIND_LLAMA_SERVER`). Luego `py -3.12 main.py` compila lo que cambió y arranca la App.
  Cada modelo conserva su licencia: ver `THIRD_PARTY_NOTICES.md`.
- **La rueda parcheada de sherpa-onnx** del reconocimiento de voz. sherpa-onnx compila dentro eSpeak NG, que es
  GPL-3.0-or-later, así que su binario no se guarda aquí. Se compila con `scripts\build_sherpa_runtime.py` (la receta y
  sus dos parches están en `runtime_wheels/`; el código fuente completo, en los activos `*-source.zip` de la
  [release 1.2.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.2.1)) y se regenera el lock con
  `scripts\lock_python_dependencies.ps1`, porque recompilar no da los mismos bytes. El BAXY instalado ya trae un
  runtime de Python completo con esa rueda instalada (su carpeta `python`). Ninguno de los dos caminos se probó
  desde esta instantánea.
- **Notas internas, bancos y datos de medición.** Llevan datos personales y rutas privadas, por eso no se publican.
  Algunos comentarios del código citan documentos o scripts de medición que no están aquí; el código no los necesita.

### Licencia

El código propio de BAXY va bajo la [licencia MIT](LICENSE). Los componentes, modelos y datos de terceros conservan
sus licencias: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) los enumera y [`licenses/`](licenses/README.md)
guarda los textos completos. Los paquetes de las releases llevan además código GPL (eSpeak NG); su código fuente y la
oferta escrita están en [`licenses/FUENTES_GPL.md`](licenses/FUENTES_GPL.md). Esto no es asesoría legal.

Las contribuciones son bienvenidas: ver [CONTRIBUTING.md](CONTRIBUTING.md).
