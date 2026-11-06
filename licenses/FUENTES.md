# Dónde está el código fuente / Where the source is

**En los binarios de BAXY 1.3.0 no se halló código GPL ni LGPL** (`scripts/check_package_licenses.py` y una revisión a ciegas, 2026-11-06).
1.2.0 sí lo lleva. / **No GPL or LGPL code was found in the binaries of BAXY 1.3.0.** 1.2.0 does carry it.

## Eigen (MPL-2.0)

Eigen 5.0.1 va compilado, sin cambios, dentro de `python/Lib/site-packages/sherpa_onnx/lib/_sherpa_onnx.cp312-win_amd64.pyd`, que sólo incluye
`Eigen/Dense`. Su texto está en `eigen-COPYING.MPL2.txt`. El apartado 3.2(a) de la MPL 2.0 pide decir cómo obtener su fuente: / Eigen 5.0.1 is
compiled, unchanged, into that file, which only includes `Eigen/Dense`; its text is in `eigen-COPYING.MPL2.txt`. Section 3.2(a) of MPL 2.0 asks to say
how to get its source:

- <https://gitlab.com/libeigen/eigen/-/archive/5.0.1/eigen-5.0.1.tar.gz> (SHA-256 `e9c326dc8c05cd1e044c71f30f1b2e34a6161a3b6ecf445d56b53ff1669e3dec`)
- y en el activo `sherpa-onnx-1.13.4-dependencies-source.zip` de la versión. / and in that asset of the release.

ONNX Runtime 1.27.0 también compila Eigen: `onnxruntime/capi/onnxruntime.dll` y `sherpa_onnx/lib/onnxruntime.dll` llevan su código, y su
`ThirdPartyNotices.txt` lo declara bajo MPL-2.0. La revisión que fija ese proyecto está en
<https://github.com/microsoft/onnxruntime/blob/v1.27.0/cmake/deps.txt>:
<https://github.com/eigen-mirror/eigen/archive/1d8b82b0740839c0de7f1242a3585e3390ff5f33/eigen-1d8b82b0740839c0de7f1242a3585e3390ff5f33.zip> (SHA-1
`05b19b49e6fbb91246be711d801160528c135e34`). Que esos binarios, compilados por terceros, usen exactamente esa revisión es una lectura. / ONNX Runtime
also compiles Eigen; the revision that project pins is that one. That those binaries, built by others, use exactly it is a reading.

## Lo que BAXY cambia y compila / What BAXY changes and builds

Se dan por transparencia: Apache-2.0 y BSD no lo piden. / Given for transparency: Apache-2.0 and BSD do not ask for it.

| Activo o fuente / Asset or source | Qué lleva / What it holds |
|---|---|
| `sherpa-onnx-1.13.4-baxy.3-source.zip` | sherpa-onnx `v1.13.4`, commit `142807252687d81b40d6315f23470a1512a00de3`, y al lado los tres parches de BAXY y el script que compila su extensión. / That tree, BAXY's three patches beside it and the script that builds its extension. |
| `sherpa-onnx-1.13.4-dependencies-source.zip` | Lo que sherpa-onnx compila dentro, con el SHA-256 que fija su CMake (abajo). Son los archivos de cada proyecto enteros: algunos traen ficheros GPL que no se compilan, como `bench/btl` de Eigen y `LICENSES/GPL-3.0-only.txt` de nlohmann/json. / What sherpa-onnx compiles in, with the SHA-256 its CMake pins (below). They are each project's whole archive: some hold GPL files that are not compiled, such as Eigen's `bench/btl` and nlohmann/json's `LICENSES/GPL-3.0-only.txt`. |
| <https://files.pythonhosted.org/packages/65/6e/09db70a523a96d25e115e71cc56a6f9031e7b8cd166c1ac8438307c14058/numpy-1.26.4.tar.gz> | numpy 1.26.4 sin cambios (SHA-256 `2a02aba9ed12e4ac4eb3ea9421c420301a0c6460d9830d74a9df87efa4912010`); `scripts/build_runtime_wheels.py` lo compila sin BLAS. / numpy unchanged; that script builds it with no BLAS. |

ONNX Runtime 1.27.0 (MIT) va precompilado: <https://github.com/microsoft/onnxruntime/tree/v1.27.0>. El `onnxruntime.dll` de `sherpa_onnx/lib` lo
compiló un tercero (`csukuangfj/onnxruntime-libs`). / It comes prebuilt; that DLL was built by a third party.

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
