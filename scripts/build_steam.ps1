# Builds the content folder of BAXY's Steam depot (documentacion/STEAM_PUBLICACION.md): everything BAXY needs in one
# folder, so a clean Windows starts it with no installer of its own:
#   app\        the product build (scripts\build_product.ps1): Baxy.exe and baxy-core.exe, self-contained
#   python\     CPython 3.12 embeddable from python.org, with the runtime lock installed in Lib\site-packages
#   mind\       src\baxy_mind at the build's commit
#   llama\      the registered llama-server (b11609, CUDA): its declared files, CPU and CUDA backends, CUDA runtime
#   llama-vulkan\   -VulkanServer's folder (b11609, Vulkan): its declared files, CPU and Vulkan backends. Two folders,
#               because the mind refuses one with two backends; the App picks one at every start by the GPU's PCI vendor
#   models\     the registered model and vision projector. System One's model stays out: the product does not use it
#               by default (MindRuntimeDiscovery.ApplyPieces)
#   voice\ stt\ the registered voice and recognizer
#   wake\       the wake package (-WakeDirectory), the product's default detector, alone
#   licenses\  BAXY's license and the third parties' notices
#   mind-runtime-v1.json   the registration the App reads beside itself (MindRuntimeDiscovery), paths relative to it
# llama\, llama-vulkan\ and python\ also carry the Visual C++ runtime (-VisualCppRedist): llama-server, ONNX Runtime and
# numpy import it and a clean Windows may not have it. Steam's redistributable installs it centrally, the way Microsoft
# prefers; these copies are for a store with no such option (itch.io) and for a System32 with an older one.
# The pieces are the ones this machine registered (%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json), the ones measured,
# each copied only when it still has its registered SHA-256. -VulkanServer is llama-server.exe unpacked from the official
# llama-b11609-bin-win-vulkan-x64.zip: the mind's declaration (llm_server.declared_build, declared_backend) verifies it.
[CmdletBinding()]
param(
    [string]$ProductBuild,
    [Parameter(Mandatory = $true)][string]$PythonEmbedZip,
    [Parameter(Mandatory = $true)][string]$Output,
    [Parameter(Mandatory = $true)][string]$VulkanServer,
    # Visual Studio's redistributable folder: VC\Redist\MSVC\<version>\x64\Microsoft.VC143.CRT.
    [Parameter(Mandatory = $true)][string]$VisualCppRedist,
    [string]$Registration,
    [Parameter(Mandatory = $true)][string]$WakeDirectory
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'mind_runtime_manifest.ps1')

# python.org's python-3.12.10-embed-amd64.zip (Authenticode: Python Software Foundation), the interpreter's version of
# the runtime venv the lock was measured with.
$PythonEmbedSha256 = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'
# The wake package the owner made the default on 2026-11-05 (WakewordBaxy\models\final\baxy-wake-k6r-v3b2): its folder's hash.
$WakeSha256 = '4003358ca24766cb46d585d96ebd72b6d9cd9ec701c94bcf690751bc804af094'

function Copy-Verified {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Sha256,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if ((Get-BaxySha256 -Path $Source) -ne $Sha256) { throw "steam_build_failed: $Source is not what was registered" }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination
}

function Copy-VerifiedDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Sha256,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if ((Get-BaxyDirectorySha256 -Directory $Source) -ne $Sha256) {
        throw "steam_build_failed: $Source is not what was registered"
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    # The folder's hash is of the files directly in it (Get-BaxyDirectorySha256); a subfolder (__pycache__) stays out.
    foreach ($file in [IO.Directory]::GetFiles($Source)) {
        Copy-Item -LiteralPath $file -Destination $Destination
    }
}

# The folder of $Server is a declared build of the backend of a GPU of this vendor, by the mind's own check (baxy_mind.gpu).
function Assert-ServerBackend {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$Vendor,
        [Parameter(Mandatory = $true)][string]$Server
    )

    # -B: this check would leave .pyc files in the package, each with this machine's folder inside (the embedded interpreter
    # is isolated by its ._pth, so PYTHONDONTWRITEBYTECODE does not reach it).
    Invoke-Checked -FilePath $PythonExe -FailureMessage "$Server is not the declared build for a GPU of vendor $Vendor" -Arguments @(
        '-B', '-X', 'utf8', '-m', 'baxy_mind.gpu', '--pci', "PCI\VEN_$Vendor", $Server)
}

# The server's folder without the other tools of its release: the files the mind's declaration hashes
# (src\baxy_mind\data\llama_server.v1.json), the CPU backends and the ones named.
function Copy-ServerFolder {
    param(
        [Parameter(Mandatory = $true)][string]$Server,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string[]]$Backend
    )

    $folder = Split-Path -Parent $Server
    $declared = Get-Content -LiteralPath (Join-Path $repo 'src\baxy_mind\data\llama_server.v1.json') -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $names = @($declared.files) + $Backend + @('libomp.dll', 'ggml-rpc.dll', 'LICENSE-LLVM-OpenMP') +
        @([IO.Directory]::GetFiles($folder, 'ggml-cpu-*.dll') | ForEach-Object { [IO.Path]::GetFileName($_) })
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($name in ($names | Sort-Object -Unique)) {
        Copy-Item -LiteralPath (Join-Path $folder $name) -Destination $Destination
    }
}

# The Visual C++ runtime beside the executable that loads it (Microsoft's local deployment: only files of the
# redistributable folder, https://learn.microsoft.com/cpp/windows/determining-which-dlls-to-redistribute).
function Copy-VisualCppRuntime {
    param(
        [Parameter(Mandatory = $true)][string]$Redist,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    foreach ($name in 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'msvcp140_atomic_wait.dll') {
        $source = Join-Path $Redist $name
        $signature = Get-AuthenticodeSignature -LiteralPath $source
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
            throw "steam_build_failed: $source does not carry a valid Microsoft signature"
        }
        Copy-Item -LiteralPath $source -Destination $Destination -Force
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "steam_build_failed: $FailureMessage (exit code $LASTEXITCODE)" }
}

if ([string]::IsNullOrWhiteSpace($ProductBuild)) {
    $ProductBuild = Join-Path $repo 'artifacts\product\build\local-win-x64'
}
if ([string]::IsNullOrWhiteSpace($Registration)) {
    $Registration = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'BAXYRuntime\mind-runtime-v1.json'
}
$Output = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw "steam_build_failed: $Output already exists; give a new folder" }
$app = Join-Path $ProductBuild 'app\Baxy.exe'
if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
    throw "steam_build_failed: no product build at $ProductBuild (run scripts\build_product.ps1 first)"
}
$registered = Get-Content -LiteralPath $Registration -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-BaxySha256 -Path $PythonEmbedZip) -ne $PythonEmbedSha256) {
    throw "steam_build_failed: $PythonEmbedZip is not python.org's python-3.12.10-embed-amd64.zip"
}
$VulkanServer = [IO.Path]::GetFullPath($VulkanServer)
$pythonPathBefore = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $repo 'src'
try {
    Assert-ServerBackend -PythonExe $registered.python -Vendor '10DE' -Server $registered.llama_server
    Assert-ServerBackend -PythonExe $registered.python -Vendor '1002' -Server $VulkanServer
} finally {
    $env:PYTHONPATH = $pythonPathBefore
}

New-Item -ItemType Directory -Path $Output | Out-Null

# The App, as scripts\build_product.ps1 published it.
Copy-Item -LiteralPath (Join-Path $ProductBuild 'app') -Destination (Join-Path $Output 'app') -Recurse

# The interpreter. An embeddable Python reads its search path from python312._pth only (PYTHONPATH is ignored): its
# standard library, the installed lock and the mind beside it. No «import site»: site would add the person's own
# %APPDATA%\Python\Python312\site-packages, and a package of theirs could replace one of the lock's (measured
# 2026-11-04). Without site no .pth file of the lock is read; none of its packages needs one to import.
$python = Join-Path $Output 'python'
Expand-Archive -LiteralPath $PythonEmbedZip -DestinationPath $python
$sitePackages = Join-Path $python 'Lib\site-packages'
[IO.File]::WriteAllText(
    (Join-Path $python 'python312._pth'),
    "python312.zip`r`n.`r`nLib\site-packages`r`n..\mind`r`n",
    [Text.UTF8Encoding]::new($false))
# The runtime lock with its hashes, installed by the registered runtime's pip (26.1.2) into the embedded interpreter.
Push-Location $repo
try {
    Invoke-Checked -FilePath $registered.python -FailureMessage 'the runtime lock did not install' -Arguments @(
        '-X', 'utf8', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-compile', '--only-binary=:all:',
        '--require-hashes', '--no-deps', '--target', $sitePackages, '-r', (Join-Path $repo 'pylock.runtime-win-x64.toml'))
} finally {
    Pop-Location
}
# pip leaves each package's console launcher in bin, with the path of the Python it ran on (this machine's, with its user's
# name) inside; nothing here starts them, and on another PC that path does not exist.
Remove-Item -LiteralPath (Join-Path $sitePackages 'bin') -Recurse
# sounddevice's PortAudio with Steinberg's ASIO: it only loads with SD_ENABLE_ASIO, which BAXY never sets
# (https://python-sounddevice.readthedocs.io/en/0.5.5/installation.html), and what terms that file goes under is not confirmed.
Remove-Item -LiteralPath (Join-Path $sitePackages '_sounddevice_data\portaudio-binaries\libportaudio64bit-asio.dll')
# protobuf: ONNX Runtime's metadata asks for it, for its model tools; loading and running a model does not import it (measured).
# Its _message.pyd is the one binary here built with GCC, with mingw-w64's runtime inside.
Remove-Item -LiteralPath (Join-Path $sitePackages 'google') -Recurse
Get-ChildItem -LiteralPath $sitePackages -Filter 'protobuf-*.dist-info' | Remove-Item -Recurse

# The mind at the build's commit: the files Git tracks, not the worktree's leftovers.
$mindArchive = Join-Path $Output 'mind.zip'
Invoke-Checked -FilePath 'git' -FailureMessage 'the mind could not be archived' -Arguments @(
    # HEAD:src leaves the root's .gitattributes behind, and Git for Windows' core.autocrlf would then write every text file
    # with CRLF: not the bytes of the commit, nor the ones the suites ran on.
    '-c', 'core.autocrlf=false', '-C', $repo, 'archive', '--format=zip', "--output=$mindArchive", 'HEAD:src', 'baxy_mind')
Expand-Archive -LiteralPath $mindArchive -DestinationPath (Join-Path $Output 'mind')
Remove-Item -LiteralPath $mindArchive

# The two llama-servers: the registered one with CUDA's backend and runtime, -VulkanServer with Vulkan's.
if ((Get-BaxySha256 -Path $registered.llama_server) -ne $registered.llama_server_sha256) {
    throw "steam_build_failed: $($registered.llama_server) is not what was registered"
}
Copy-ServerFolder -Server $registered.llama_server -Destination (Join-Path $Output 'llama') -Backend @(
    'ggml-cuda.dll', 'cudart64_12.dll', 'cublas64_12.dll', 'cublasLt64_12.dll')
Copy-ServerFolder -Server $VulkanServer -Destination (Join-Path $Output 'llama-vulkan') -Backend @('ggml-vulkan.dll')
foreach ($folder in 'llama', 'llama-vulkan', 'python') {
    Copy-VisualCppRuntime -Redist $VisualCppRedist -Destination (Join-Path $Output $folder)
}

# The models and the pieces beside them.
$models = Join-Path $Output 'models'
Copy-Verified -Source $registered.gguf -Sha256 $registered.gguf_sha256 `
    -Destination (Join-Path $models (Split-Path -Leaf $registered.gguf))
Copy-Verified -Source $registered.mmproj -Sha256 $registered.mmproj_sha256 `
    -Destination (Join-Path $models (Split-Path -Leaf $registered.mmproj))
Copy-VerifiedDirectory -Source $registered.renew_tts_dir -Sha256 $registered.renew_tts_sha256 `
    -Destination (Join-Path $Output 'voice')
# This machine's registration may not name the default wake package.
Copy-VerifiedDirectory -Source $WakeDirectory -Sha256 $WakeSha256 `
    -Destination (Join-Path $Output 'wake')
Copy-VerifiedDirectory -Source $registered.renew_stt_dir -Sha256 $registered.renew_stt_sha256 `
    -Destination (Join-Path $Output 'stt')

# The licenses: BAXY's, the third parties' inventory, and those that came with a piece.
$licenses = Join-Path $Output 'licenses'
New-Item -ItemType Directory -Path $licenses | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'LICENSE') -Destination (Join-Path $licenses 'BAXY-LICENSE.txt')
Copy-Item -LiteralPath (Join-Path $repo 'THIRD_PARTY_NOTICES.md') -Destination $licenses
Copy-Item -LiteralPath (Join-Path $python 'LICENSE.txt') -Destination (Join-Path $licenses 'Python-LICENSE.txt')
Copy-Item -LiteralPath (Join-Path $repo 'scripts\llama\LICENSE-llama.cpp.txt') -Destination $licenses
Copy-Item -Path (Join-Path $repo 'licenses\*') -Destination $licenses

# The registration the App reads beside itself, every path relative to this folder.
$python312 = Join-Path $python 'python.exe'
$document = [ordered]@{
    schema = $script:BaxyMindRuntimeSchema
    python = 'python\python.exe'
    python_sha256 = Get-BaxySha256 -Path $python312
    python_path = 'mind'
    gguf = "models\$(Split-Path -Leaf $registered.gguf)"
    gguf_sha256 = $registered.gguf_sha256
    llama_server = 'llama\llama-server.exe'
    llama_server_sha256 = $registered.llama_server_sha256
    llama_server_vulkan = 'llama-vulkan\llama-server.exe'
    llama_server_vulkan_sha256 = Get-BaxySha256 -Path (Join-Path $Output 'llama-vulkan\llama-server.exe')
    ngl = [int]$registered.ngl
    renew_tts_dir = 'voice'
    renew_tts_sha256 = Get-BaxyDirectorySha256 -Directory (Join-Path $Output 'voice')
    renew_wake_dir = 'wake'
    renew_wake_sha256 = Get-BaxyDirectorySha256 -Directory (Join-Path $Output 'wake')
    renew_stt_dir = 'stt'
    renew_stt_sha256 = Get-BaxyDirectorySha256 -Directory (Join-Path $Output 'stt')
    mmproj = "models\$(Split-Path -Leaf $registered.mmproj)"
    mmproj_sha256 = $registered.mmproj_sha256
}
[IO.File]::WriteAllText(
    (Join-Path $Output 'mind-runtime-v1.json'),
    ($document | ConvertTo-Json),
    [Text.UTF8Encoding]::new($false))

# What was copied is what the mind will accept, by the package's own interpreter and mind.
Assert-ServerBackend -PythonExe $python312 -Vendor '10DE' -Server (Join-Path $Output 'llama\llama-server.exe')
Assert-ServerBackend -PythonExe $python312 -Vendor '1002' -Server (Join-Path $Output 'llama-vulkan\llama-server.exe')
# Nothing the licenses of 1.3.0 left out came back with a package of the lock.
Invoke-Checked -FilePath $python312 -FailureMessage 'the package carries what its notices say it does not' -Arguments @(
    '-B', '-X', 'utf8', (Join-Path $repo 'scripts\check_package_licenses.py'), '--depot', $Output,
    '--lock', (Join-Path $repo 'pylock.runtime-win-x64.toml'))

$files = @(Get-ChildItem -LiteralPath $Output -Recurse -File)
[ordered]@{
    output = $Output
    commit = ([string](& git -C $repo rev-parse HEAD)).Trim()
    files = $files.Count
    bytes = ($files | Measure-Object -Property Length -Sum).Sum
} | ConvertTo-Json -Compress
