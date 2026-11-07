# Código bajo GPL y LGPL que lleva BAXY / GPL and LGPL code shipped with BAXY

> **Desde 1.3.0 los paquetes de BAXY no llevan código GPL ni LGPL.** Este fichero vale para lo que ya se distribuyó: BAXY
> 1.2.0 y 1.2.1 y las ruedas `sherpa_onnx` +baxy.1 y +baxy.2 de la historia de este repositorio (commits `aedd12c5b` a
> `45f982789`). / **Since 1.3.0 BAXY's packages carry no GPL or LGPL code.** This file is for what was already
> distributed: BAXY 1.2.0 and 1.2.1 and the `sherpa_onnx` +baxy.1 and +baxy.2 wheels in this repository's history.
> Los textos `GPL-3.0.txt` y `LGPL-2.1.txt` que cita van en `baxy-1.2.1-licenses.zip`, en la release `fuentes-terceros`. /
> The `GPL-3.0.txt` and `LGPL-2.1.txt` texts it cites are in `baxy-1.2.1-licenses.zip`, in the `fuentes-terceros` release.

**eSpeak NG** (GPL-3.0-or-later, texto en `GPL-3.0.txt`) va compilado dentro de sherpa-onnx, la biblioteca con la que
BAXY sintetiza su voz. El proyecto sherpa-onnx lo compila siempre que su opción de voz (`SHERPA_ONNX_ENABLE_TTS`) está
activa.

eSpeak NG (GPL-3.0-or-later, full text in `GPL-3.0.txt`) is compiled into sherpa-onnx, the library BAXY synthesizes its
voice with. The sherpa-onnx project compiles it whenever its voice option (`SHERPA_ONNX_ENABLE_TTS`) is on.

También lleva el runtime de gfortran (GPL-3.0 con excepción de runtime), dentro de las bibliotecas de numpy y scipy: ver la nota de
Python de `THIRD_PARTY_NOTICES.md`. / It also carries the gfortran runtime (GPL-3.0 with the runtime exception), inside the numpy and
scipy libraries: see the Python note in `THIRD_PARTY_NOTICES.md`.

Ficheros del paquete que lo llevan / Files in the package that contain it:

- `python/Lib/site-packages/sherpa_onnx/lib/_sherpa_onnx.cp312-win_amd64.pyd` (compilado con los cambios de BAXY / built
  with BAXY's changes)
- `python/Lib/site-packages/sherpa_onnx/lib/sherpa-onnx-c-api.dll` y su copia idéntica
  `python/Lib/site-packages/Scripts/sherpa-onnx-c-api.dll` (de la rueda oficial `sherpa-onnx-core` 1.13.4 / from the
  official `sherpa-onnx-core` 1.13.4 wheel)

El paquete no lleva los datos de eSpeak NG (`espeak-ng-data`). / The package does not include eSpeak NG's data.

**Esos tres binarios, como obra entera, se distribuyen bajo GPL-3.0-or-later** (apartado 5(c)). Lo demás que llevan dentro conserva
su licencia, compatible con ella: Apache-2.0 lo es con la versión 3 de la GPL
([lista de la FSF](https://www.gnu.org/licenses/license-list.html#apache2), leída el 2026-11-06), y también MIT, BSD y MPL-2.0. La
excepción es el runtime de MSVC, enlazado de forma estática (`Use MSVC CRT: MT` en su configuración), que aquí se trata como biblioteca
de sistema del apartado 1: **es una lectura, no algo confirmado.** Hasta dónde llega la obra más allá de esos binarios **no está
decidido.** La sección 2 del acuerdo del instalador dice que no cambia las licencias de terceros; una cláusula expresa sobre la GPL
todavía no está en él.

**Cambios (5(a)):** el proyecto BAXY modificó `_sherpa_onnx…pyd`, a más tardar el 2026-09-08, con los dos parches de abajo.
`sherpa-onnx-c-api.dll` es el oficial, sin cambios, compilado por el proyecto sherpa-onnx. eSpeak NG y piper-phonemize van sin cambios.

**Those three binaries, as a whole, are conveyed under GPL-3.0-or-later** (section 5(c)). What else they hold keeps its own license,
compatible with it (Apache-2.0, MIT, BSD, MPL-2.0). The exception is the statically linked MSVC runtime, treated here as a System
Library under section 1: **that is a reading, not something confirmed.** How far the work reaches beyond those binaries **is not
decided.** Section 2 of the installer's agreement says it does not change third-party licenses; an express clause about the GPL is not in
it yet.

**Changes (5(a)):** the BAXY project modified `_sherpa_onnx…pyd`, no later than 2026-09-08, with the two patches below.
`sherpa-onnx-c-api.dll` is the official one, unchanged, built by the sherpa-onnx project. eSpeak NG and piper-phonemize are unchanged.

## Dónde está el código fuente / Where the source is

En la release `fuentes-terceros` de GitHub, gratis, como activos (BAXY 1.2.0, 1.2.1 y 1.3.0 se retiraron el 2026-11-07 y
esta release guarda su fuente de terceros) / In the `fuentes-terceros` release on GitHub, at no charge, as assets (BAXY
1.2.0, 1.2.1 and 1.3.0 were withdrawn on 2026-11-07 and this release keeps their third-party source):

<https://github.com/REDSOULTM/BAXY/releases/tag/fuentes-terceros>

| Activo / Asset | Qué lleva / What it holds |
|---|---|
| `espeak-ng-ed530aa-source.zip` | eSpeak NG 1.52.0.1, fork para sherpa-onnx, commit `ed530aa113046142eb5115cf2fc9157854d0ffe1`, tal cual lo baja sherpa-onnx (SHA-256 `e4e262cbe34f7fe21f91f1ba3397f2728e1f30eafbae7853f2b753a9ed13f0dd`). Sin cambios de BAXY. / eSpeak NG, as sherpa-onnx downloads it, unchanged. |
| `piper-phonemize-f3ff95a-source.zip` | piper-phonemize (MIT), fork para sherpa-onnx, commit `f3ff95afc03640bc1399e113e83361192a2fafb4`, tal cual lo baja sherpa-onnx (SHA-256 `d9cca4e2bdc7d6dd8dffb96a4668283dbd3f77a9c194a3e530c1e8eba9406a5d`). Sin cambios de BAXY. / piper-phonemize, as sherpa-onnx downloads it, unchanged. |
| `sherpa-onnx-1.13.4-baxy.2-source.zip` | sherpa-onnx `v1.13.4`, commit `142807252687d81b40d6315f23470a1512a00de3`, y al lado los dos parches de BAXY (`sherpa-nemo-stream-decoder.patch`, `sherpa-nemo-normalization.patch`), el script que compila (`build_sherpa_runtime.py`) y cómo compilar con estos activos (`README-BAXY.txt`). / sherpa-onnx with BAXY's two patches beside it, unapplied, the build script and how to use these assets. |
| `sherpa-onnx-1.13.4-dependencies-source.zip` | Lo que sherpa-onnx compila dentro junto a ellos, con el SHA-256 que fija su CMake (lista abajo). / What sherpa-onnx compiles in with them, with the SHA-256 its CMake pins. |

Los dos parches y el script están también en este repositorio (`runtime_wheels/` y `scripts/build_sherpa_runtime.py`). Hasta el
commit [`45f98278`](https://github.com/REDSOULTM/BAXY/tree/45f9827896b6de16fca4b362d8aa9833080e563d/runtime_wheels) de `main`, esa
carpeta publicaba además las ruedas `sherpa_onnx-1.13.4+baxy.2` y `+baxy.1`, que llevan eSpeak NG; `+baxy.1` es el mismo árbol con sólo
`sherpa-nemo-stream-decoder.patch` (su `baxy_native_build.json`). El árbol actual ya no las lleva, pero siguen en el historial de Git, y
la oferta de abajo las cubre. / The two patches and the script are also in this repository (`runtime_wheels/` and
`scripts/build_sherpa_runtime.py`). Up to commit `45f98278` of `main`, that folder also published the wheels `+baxy.2` and `+baxy.1`,
which carry eSpeak NG; `+baxy.1` is the same tree with only `sherpa-nemo-stream-decoder.patch`. The current tree no longer carries them,
but they remain in the Git history, and the offer below covers them.

Compilar con estos activos se probó el 2026-11-06: salió un `_sherpa_onnx…pyd` que pasa `math-test`, no idéntico byte a byte al del
paquete. `sherpa-onnx-c-api.dll` lo compiló el proyecto sherpa-onnx: que corresponde a esta versión lo dicen su rueda oficial 1.13.4, la
cadena `1.52.0.1` y sus rutas `_deps`, no una recompilación. / Building from these assets was tried on 2026-11-06: it gave a
`_sherpa_onnx…pyd` that passes `math-test`, not identical byte by byte to the package's. `sherpa-onnx-c-api.dll` was built by the
sherpa-onnx project: its official 1.13.4 wheel, the string `1.52.0.1` and its `_deps` paths say it matches this version, not a rebuild.

### Dentro de `sherpa-onnx-1.13.4-dependencies-source.zip`

| Fichero | Origen | SHA-256 |
|---|---|---|
| `pybind11-3.0.0.tar.gz` | <https://github.com/pybind/pybind11/archive/refs/tags/v3.0.0.tar.gz> | `453b1a3e2b266c3ae9da872411cadb6d693ac18063bd73226d96cfb7015a200c` |
| `kaldi-native-fbank-1.22.3.tar.gz` | <https://github.com/csukuangfj/kaldi-native-fbank/archive/refs/tags/v1.22.3.tar.gz> | `9176cc66fc7ce1edf85cf355b06e320c57db6297df74277f575183468893cf61` |
| `kissfft-febd4caeed32e33ad8b2e0bb5ea77542c40f18ec.zip` | <https://github.com/mborgerding/kissfft/archive/febd4caeed32e33ad8b2e0bb5ea77542c40f18ec.zip> | `497103e664168ebe39580b757adbe616f6cf85a16572af581ca7bc42d0ab13fd` |
| `kaldi-decoder-0.3.0.tar.gz` | <https://github.com/k2-fsa/kaldi-decoder/archive/refs/tags/v0.3.0.tar.gz> | `b9f34cfb4fd3b1344100eead79ef4d37aa15962274b9e3056de345021f76a1b0` |
| `kaldifst-1.8.0.tar.gz` | <https://github.com/k2-fsa/kaldifst/archive/refs/tags/v1.8.0.tar.gz> | `3f247b7e5a2409071202f5e2bc6200060f66728c0a3443c03923ad2723e040b3` |
| `openfst-1.8.5-2026-04-11.tar.gz` | <https://github.com/csukuangfj/openfst/archive/refs/tags/v1.8.5-2026-04-11.tar.gz> | `57fbc4b950ae81b1a0e1e298af15652da968a6723a592b7874e9b4027a80a5b4` |
| `eigen-5.0.1.tar.gz` | <https://gitlab.com/libeigen/eigen/-/archive/5.0.1/eigen-5.0.1.tar.gz> | `e9c326dc8c05cd1e044c71f30f1b2e34a6161a3b6ecf445d56b53ff1669e3dec` |
| `simple-sentencepiece-0.7.tar.gz` | <https://github.com/pkufool/simple-sentencepiece/archive/refs/tags/v0.7.tar.gz> | `1748a822060a35baa9f6609f84efc8eb54dc0e74b9ece3d82367b7119fdc75af` |
| `json-3.12.0.tar.gz` | <https://github.com/nlohmann/json/archive/refs/tags/v3.12.0.tar.gz> | `4b92eb0c06d10683f7447ce9406cb97cd4b453be18d7279320f7b2f025c10187` |
| `hclust-cpp-2026-02-25.tar.gz` | <https://github.com/csukuangfj/hclust-cpp/archive/refs/tags/2026-02-25.tar.gz> | `8f14e024c709d73afb40ae69cb22de4b73dba67cbce40f2e518813da8139ab56` |
| `googletest-1.13.0.tar.gz` (sólo para compilar las pruebas del script, no va en los binarios / only to build the script's tests, not in the binaries) | <https://github.com/google/googletest/archive/refs/tags/v1.13.0.tar.gz> | `ad7fdba11ea011c1d925b3289cf4af2c66a352e18d4c7264392fead75e919363` |

ONNX Runtime 1.27.0 (MIT), que sherpa-onnx carga, va precompilado en el paquete: su fuente está en
<https://github.com/microsoft/onnxruntime/tree/v1.27.0>, no en estos activos, y la oferta de abajo no lo cubre. Dejarlo fuera es una lectura, no algo confirmado: los binarios lo cargan como biblioteca dinámica (apartado 1), y el fichero viene compilado por un tercero (`csukuangfj/onnxruntime-libs`). / ONNX Runtime 1.27.0
(MIT), which sherpa-onnx loads, is in the package prebuilt: its source is at that address, not in these assets, and the offer below
does not cover it. Leaving it out is a reading, not something confirmed: the binaries load it as a dynamic library (section 1), and the file
was built by a third party (`csukuangfj/onnxruntime-libs`).

### LGPL

libquadmath: text in `LGPL-2.1.txt`, source at the GCC address below, not in these assets; its version is not confirmed. autocommand: source
and text are in the package itself. / Tabla:

| Pieza | Versión | Código fuente |
|---|---|---|
| libquadmath (LGPL-2.1-or-later), dentro de la OpenBLAS de numpy (`numpy.libs/`). Texto en `LGPL-2.1.txt`; su nota, en `numpy-1.26.4.dist-info/LICENSE.txt` | la de la rueda oficial de numpy 1.26.4: el DLL dice `GCC: (Built by Jeroen for the R-project) 10.3.0`. **Sin confirmar** que ese GCC no lleve cambios | <https://gcc.gnu.org/git/?p=gcc.git;a=tree;f=libquadmath;hb=refs/tags/releases/gcc-10.3.0>; la licencia de numpy da <https://gcc.gnu.org/git/?p=gcc.git;a=tree;f=libquadmath>. No está en estos activos |
| autocommand 2.2.2 (LGPLv3), dentro de setuptools (`setuptools/_vendor/autocommand/`), texto en `setuptools/_vendor/autocommand-2.2.2.dist-info/LICENSE` | la de la rueda oficial de setuptools 83.0.0 | Va en Python en el propio paquete |

## Written offer

The developer of BAXY offers, for at least three years after BAXY 1.2.0 or 1.2.1 was last offered for download, and for as long as
customer support is offered for them, to give anyone who possesses the object code of BAXY 1.2.0 or 1.2.1, or the `sherpa_onnx` wheels of
this repository, the four `*-source.zip` assets listed above (GPL-3.0 section 6): either access to copy them from a network server at no
charge, at <https://github.com/REDSOULTM/BAXY/releases/tag/fuentes-terceros>, or, on request at <https://github.com/REDSOULTM/BAXY/issues>, a copy
on a durable physical medium customarily used for software interchange, for a price no more than the reasonable cost of physically
performing this conveying. ONNX Runtime, libquadmath and autocommand are outside this offer: where they are is said above.

## Oferta escrita

El desarrollador de BAXY ofrece, durante al menos tres años desde la última vez que BAXY 1.2.0 o 1.2.1 se ofrezca para bajar, y mientras
dé soporte a esas versiones, dar a quien tenga el código objeto de BAXY 1.2.0 o 1.2.1, o las ruedas `sherpa_onnx` de este repositorio, los
cuatro activos `*-source.zip` de la lista de arriba (apartado 6 de la GPL-3.0): o bien acceso para copiarlos de un servidor de red sin
coste, en <https://github.com/REDSOULTM/BAXY/releases/tag/fuentes-terceros>, o bien, si lo pide en <https://github.com/REDSOULTM/BAXY/issues>, una
copia en un soporte físico duradero de los que se usan para intercambiar software, por un precio no mayor que el coste razonable de hacer
esa entrega. ONNX Runtime, libquadmath y autocommand quedan fuera de esta oferta: dónde están se dice arriba.
