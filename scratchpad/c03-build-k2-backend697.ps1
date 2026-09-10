param([string[]]$Targets = @('llama-server', 'llama-cli', 'llama-bench', 'test-chat-auto-parser', 'test-chat-peg-parser'))
$ErrorActionPreference = 'Stop'
$k2Source = 'D:/BAXYRuntime/build/llama-k2-horizon-35999d1'
$k2Build = "$k2Source/build-cuda13-sm86"
$vsRoot = 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools'
Import-Module "$vsRoot/Common7/Tools/Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath $vsRoot -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$cmakePath = "$vsRoot/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
$ninjaPath = "$vsRoot/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe"
& $cmakePath -S $k2Source -B $k2Build -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninjaPath" -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86 -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_OPENSSL=OFF
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $cmakePath --build $k2Build --target @Targets --parallel 3
exit $LASTEXITCODE
