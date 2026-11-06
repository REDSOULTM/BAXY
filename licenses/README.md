# Licencias de terceros que van con BAXY

Esta carpeta se copia tal cual a `licenses\` del paquete (`scripts/build_steam.ps1`). `THIRD_PARTY_NOTICES.md` lleva el
inventario completo; aquí están los textos que las licencias piden entregar y que no venían ya dentro de cada pieza.
Las bibliotecas de Python traen además sus propias licencias en `python/Lib/site-packages/*.dist-info/`.

- `ATRIBUCIONES_MODELOS.md`: quién hizo cada modelo y qué cambió BAXY.
- `FUENTES_GPL.md`: dónde está el código fuente de lo que va bajo GPL, con la oferta escrita.

## Textos copiados de su fuente

Bajados el 2026-11-06, sin editar (`SHA-256` del fichero tal como se bajó; el repositorio normaliza los finales de línea). Los
de las piezas que sherpa-onnx compila dentro salen de sus fuentes, cada uno con el SHA-256 que sherpa-onnx fija
(`scripts/build_source_assets.py`); el enlace lleva a ese mismo fichero en la misma versión.

| Fichero | Qué cubre | Fuente | SHA-256 |
|---|---|---|---|
| `Apache-2.0.txt` | Lo que declara Apache-2.0 sin traer el texto: `flatbuffers`, `tokenizers`, `sherpa-onnx-core` | <https://www.apache.org/licenses/LICENSE-2.0.txt> | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `Qwen3.5-4B-LICENSE.txt` | `models/`: el modelo de BAXY y el proyector de visión | <https://huggingface.co/Qwen/Qwen3.5-4B/raw/main/LICENSE> | `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a` |
| `CC-BY-4.0.txt` | `stt/`: Parakeet | <https://creativecommons.org/licenses/by/4.0/legalcode.txt> | `9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411` |
| `CC-BY-SA-4.0.txt` | `wake/`: Kroko, por prudencia (**versión sin confirmar**, ver `ATRIBUCIONES_MODELOS.md`) | <https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt> | `28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5` |
| `OpenRAIL-M-Supertonic-3.txt` | `voice/`: Supertonic 3 | <https://huggingface.co/Supertone/supertonic-3/raw/main/LICENSE> | `0d944a9110fed9a9602d60e0423a272903e7bd21ab060490774efc77c2275e9f` |
| `GPL-3.0.txt` | eSpeak NG dentro de sherpa-onnx, ver `FUENTES_GPL.md` | <https://raw.githubusercontent.com/csukuangfj/espeak-ng/ed530aa113046142eb5115cf2fc9157854d0ffe1/COPYING> | `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903` |
| `Inter-OFL.txt` | `app/FieldUi/assets`: Inter | <https://raw.githubusercontent.com/rsms/inter/master/LICENSE.txt> | `262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a` |
| `JetBrainsMono-OFL.txt` | `app/FieldUi/assets`: JetBrains Mono | <https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/OFL.txt> | `a76abf002c49097d146e86740a3105a5d00450b1592e820a1109a8c5680cd697` |
| `ChakraPetch-OFL.txt` | `app/FieldUi/assets`: Chakra Petch | <https://raw.githubusercontent.com/cadsondemak/Chakra-Petch/master/OFL.txt> | `13831d02389d917d22fcfa6c79f98f8acbf61d230add0e73a4d4dc5f3bfb9e56` |
| `dotnet-LICENSE.txt` | `app/`: .NET 10.0.14 dentro de `Baxy.exe`, `baxy-core.exe` y el instalador | <https://raw.githubusercontent.com/dotnet/dotnet/0427b9abbead3fa64c6655eb4290c537397131fa/src/runtime/LICENSE.TXT> | `cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310` |
| `dotnet-runtime-THIRD-PARTY-NOTICES.txt` | Ídem | <https://raw.githubusercontent.com/dotnet/dotnet/0427b9abbead3fa64c6655eb4290c537397131fa/src/runtime/THIRD-PARTY-NOTICES.TXT> | `66f1d4e44973185519bb4aa8a9718eb22fc7af2cc532e3ae9cfc4c127ee7fc54` |
| `dotnet-wpf-THIRD-PARTY-NOTICES.txt` | `app/`: WPF, dentro de `Baxy.exe` y el instalador | <https://raw.githubusercontent.com/dotnet/dotnet/0427b9abbead3fa64c6655eb4290c537397131fa/src/wpf/THIRD-PARTY-NOTICES.TXT> | `d23dba2fee20c6b59d8f7088ee9ed372459c952a319b7ca90f3eec370cc76eb9` |
| `WebView2-LICENSE.txt` | `app/`: WebView2 1.0.4078.44 | <https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4078.44> | `0af8f1b807512aae39c2ac1aa4d0cae65cabecb6fd554b8439a5162a0d6eca55` |
| `WebView2-NOTICE.txt` | Ídem | <https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4078.44> | `106423785c5b7eba0a8e61d1837f2132e9c828e20ad530f565d981c1df60dd90` |
| `CsWinRT-LICENSE.txt` | `WinRT.Runtime.dll` | <https://raw.githubusercontent.com/microsoft/CsWinRT/master/LICENSE> | `9906940f61b1f0b533fa7d99baf55178b2808fbe113ea51dfbfad8572ccd5f2b` |
| `cpp-httplib-LICENSE.txt` | `llama*/`: compilado dentro de llama-server | <https://raw.githubusercontent.com/ggml-org/llama.cpp/fcac19079/vendor/cpp-httplib/LICENSE> | `4b45cbe16d7b71b89ae6127e26e0d90a029198ca5e958ad8e3d0b8bbed364d8b` |
| `nlohmann-json-LICENSE.txt` | `llama*/`: ídem; también en `sherpa_onnx/lib/` | <https://raw.githubusercontent.com/ggml-org/llama.cpp/fcac19079/licenses/LICENSE-jsonhpp> | `c0d068392ea65358b798b8c165103560f06e9e3b38c4ab4e2d8810a7b931af86` |
| `BoringSSL-LICENSE.txt` | `llama*/`: ídem | <https://raw.githubusercontent.com/google/boringssl/0.20260929.0/LICENSE> | `827c8d8fc207c2392794eef9e00fe246f9f61fdcc132556c275be3dd8c3cd97f` |
| `OpenSSL-LICENSE.txt` | `python/libcrypto-3.dll`, `python/libssl-3.dll` (OpenSSL 3.0.16) | <https://raw.githubusercontent.com/openssl/openssl/openssl-3.0.16/LICENSE.txt> | `7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a` |
| `pybind11-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `_kaldi_native_fbank*.pyd` | <https://raw.githubusercontent.com/pybind/pybind11/v3.0.0/LICENSE> | `83965b843b98f670d3a85bd041ed4b372c8ec50d7b4a5995a83ac697ba675dcb` |
| `Intel-Simplified-Software-License.txt` | Intel oneMKL, compilado dentro de `torch/lib/torch_cpu.dll` (texto de la rueda `mkl` 2026.2.0, `dist-info/LICENSE.txt`) | <https://pypi.org/project/mkl/2026.2.0/> | `7721633d0ddff43fae25ebfd405f8166a0ce730cbcec44f2f3ad9d5eb8ac9a6f` |
| `Intel-EULA-Developer-Tools.txt` | `torch/lib/libiomp5md.dll`, `libiompstubs5md.dll` (texto de la rueda `intel-openmp` 2026.2.0, `dist-info/LICENSE.txt`; **sin confirmar** que sea la de esos ficheros) | <https://pypi.org/project/intel-openmp/2026.2.0/> | `febfb69a5b058f55892dc7f341108a9ca29d50e9fe85723a57eebbb826436958` |
| `Intel-OpenMP-third-party-programs.txt` | Ídem: lo que `libiomp5md.dll` lleva de terceros, como ITT Notify y hwloc | <https://pypi.org/project/intel-openmp/2026.2.0/> | `f8ce918fe7311ce279e68380a2e233f8a42b1cd3dda8f4c48d6de97a0255c1d7` |
| `Intel-oneMKL-third-party-programs.txt` | Intel oneMKL: lo que lleva de terceros (texto de la rueda `onemkl-license`) | <https://pypi.org/project/onemkl-license/2026.2.0/> | `e7dad56601956b5f1fd3317420ad399136a6bfc1c3b9cb6d54eb358a6e1afea2` |
| `piper-phonemize-LICENSE.txt` | `sherpa_onnx/lib/`: piper-phonemize, compilado dentro | <https://raw.githubusercontent.com/csukuangfj/piper-phonemize/f3ff95afc03640bc1399e113e83361192a2fafb4/LICENSE.md> | `13746d509d74e55ea2265fbef204bb7cdbf84a8315b0207e988326cb54387028` |
| `Python-Licenses-and-Acknowledgements.txt` | `python/`: lo que CPython 3.12.10 lleva de terceros (expat, libmpdec, zlib, OpenSSL…), que su `LICENSE.txt` no cita | <https://raw.githubusercontent.com/python/cpython/v3.12.10/Doc/license.rst> | `341832873fd316a37927e79385093fbbfd40a467428480835fe435a80cadf4e5` |
| `LGPL-2.1.txt` | libquadmath, dentro de la OpenBLAS de numpy (`numpy.libs/`) | <https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt> | `20e50fe7aae3e56378ebf0417d9de904f55a0e61e4df315333e632a4d3555d95` |
| `NVIDIA-CUDA-EULA-12.4.1.txt` | `llama/`: `cudart64_12.dll`, `cublas64_12.dll`, `cublasLt64_12.dll` (texto sacado de la página, sin editar) | <https://docs.nvidia.com/cuda/archive/12.4.1/eula/index.html> | `a5a8ab2058e2f92b12008c572bc2abd9fb9e79aeeed168abc4e24221eb0b5750` |
| `Windows-SDK-License.rtf` | `Microsoft.Windows.SDK.NET.dll`, `WinRT.Runtime.dll` | <https://aka.ms/WinSDKLicenseURL> | `dd07eb178e00c6bba4148457fc00ff77cd4887eb521d504186fe59c9ec8bbe62` |
| `espeak-ng-COPYING.BSD2.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: `getopt.c` de eSpeak NG en Windows | <https://github.com/csukuangfj/espeak-ng/blob/ed530aa113046142eb5115cf2fc9157854d0ffe1/COPYING.BSD2> | `a8b0c1c7d7af6c0415c068be8cf373799d1a42b0707b79dc4ccfcaf593cd902d` |
| `espeak-ng-COPYING.UCD.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: datos Unicode de eSpeak NG | <https://github.com/csukuangfj/espeak-ng/blob/ed530aa113046142eb5115cf2fc9157854d0ffe1/COPYING.UCD> | `be029c50df83105a810e391778b6edcb522d6cb4b4e142332aca54437a499bf7` |
| `espeak-ng-COPYING.APACHE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: lo que eSpeak NG marca como Apache-2.0 | <https://github.com/csukuangfj/espeak-ng/blob/ed530aa113046142eb5115cf2fc9157854d0ffe1/COPYING.APACHE> | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `uni-algo-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: uni-algo, dentro de piper-phonemize | <https://github.com/csukuangfj/piper-phonemize/blob/f3ff95afc03640bc1399e113e83361192a2fafb4/licenses/uni-algo/LICENSE.md> | `c55648b02873556d6ab2de14938998101fda3a0f293337542af9196435def318` |
| `kaldi-native-fbank-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll` y la rueda `kaldi-native-fbank` | <https://github.com/csukuangfj/kaldi-native-fbank/blob/v1.22.3/LICENSE> | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `kissfft-COPYING.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: kissfft, dentro de kaldi-native-fbank | <https://github.com/mborgerding/kissfft/blob/febd4caeed32e33ad8b2e0bb5ea77542c40f18ec/COPYING> | `a2840585f8411be8e6826a31ef15ae65c950bd74a2437a73b013398a934ad0c6` |
| `kissfft-BSD-3-Clause.txt` | Ídem: el texto al que remite su `COPYING` | <https://github.com/mborgerding/kissfft/blob/febd4caeed32e33ad8b2e0bb5ea77542c40f18ec/LICENSES/BSD-3-Clause> | `4d6bcab46f27d6d0c878e8305d4bdcfe040d52bf6656b9771f04c9fb9902c0ed` |
| `kaldi-decoder-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll` | <https://github.com/k2-fsa/kaldi-decoder/blob/v0.3.0/LICENSE> | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `kaldifst-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll` | <https://github.com/k2-fsa/kaldifst/blob/v1.8.0/LICENSE> | `a682d6efd1ee5dee08a8e405c233c2c198ea70ae0718129daa83ab58cfe31c5d` |
| `openfst-COPYING.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll` | <https://github.com/csukuangfj/openfst/blob/v1.8.5-2026-04-11/COPYING> | `4300529197035fd3452350718a0b8cee984e9412c9932d7f35fcde849fc97a4b` |
| `simple-sentencepiece-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll` | <https://github.com/pkufool/simple-sentencepiece/blob/v0.7/LICENSE> | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
| `hclust-cpp-LICENSE.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: fastcluster | <https://github.com/csukuangfj/hclust-cpp/blob/2026-02-25/LICENSE> | `e361d842da1d290351860ad6dcce2673a1e42e4f873a3ae1ff4eb92c6adaa882` |
| `eigen-COPYING.MPL2.txt` | `sherpa_onnx/lib/_sherpa_onnx*.pyd`, `sherpa-onnx-c-api.dll`: Eigen, sobre todo MPL-2.0; MPL 3.2 pide decir dónde está su fuente: `FUENTES_GPL.md` | <https://gitlab.com/libeigen/eigen/-/blob/5.0.1/COPYING.MPL2> | `66a3107d5ad6a058aab753eaac2047ccb2ed0e39465dd0fe5844da3e300d5172` |
| `eigen-COPYING.README.txt` | Ídem: qué licencia tiene cada parte de Eigen | <https://gitlab.com/libeigen/eigen/-/blob/5.0.1/COPYING.README> | `db640ff2bd90c6abd6a4d3fbb351e0ee4d555417cf840492054d1cbb2ea85644` |
| `eigen-COPYING.BSD.txt` | Ídem | <https://gitlab.com/libeigen/eigen/-/blob/5.0.1/COPYING.BSD> | `51928dce36213c5333ba3172e847d735d4c6e9b7ff2722a326c49067155b82eb` |
| `eigen-COPYING.MINPACK.txt` | Ídem | <https://gitlab.com/libeigen/eigen/-/blob/5.0.1/COPYING.MINPACK> | `c87b7f8ee88f6195e91743820c00354833583aef091b72e2d4a49c8e28e798a0` |
| `eigen-COPYING.APACHE.txt` | Ídem | <https://gitlab.com/libeigen/eigen/-/blob/5.0.1/COPYING.APACHE> | `03379001a7b12a2ec997a25554247d985270b353c10d5bafee9ac8d6519820b7` |
