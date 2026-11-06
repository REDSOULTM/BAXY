# Fin de turno (uso-74): installs the turn model the voice reads (src/baxy_mind/voice_turn.py, default_path):
# Smart Turn v3.2 int8 for CPU, Pipecat by Daily, BSD 2-Clause, from its published Hugging Face file, checked by its
# SHA-256 (MODEL_SHA256). Idempotent: a file already there with the right hash is kept. Nothing else is touched.
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\voice\instalar_fin_de_turno.ps1 [-Destination DIR]
param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'BAXYRuntime\assets\voice\smart-turn')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$name = 'smart-turn-v3.2-cpu.onnx'
$sha256 = '2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f'
$url = "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/$name"
$target = Join-Path $Destination $name

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
if ((Test-Path $target) -and (Get-FileHash -Algorithm SHA256 $target).Hash.ToLowerInvariant() -eq $sha256) {
    Write-Output "turn_model_ready: $target"
} else {
    $partial = "$target.partial"
    Invoke-WebRequest -Uri $url -OutFile $partial -UseBasicParsing
    $got = (Get-FileHash -Algorithm SHA256 $partial).Hash.ToLowerInvariant()
    if ($got -ne $sha256) {
        Remove-Item $partial
        throw "turn_model_hash_mismatch: $got"
    }
    Move-Item -Force $partial $target
    Write-Output "turn_model_installed: $target"
}

@'
smart-turn-v3.2-cpu.onnx: Smart Turn v3.2 (int8, CPU), Pipecat's end-of-turn model, by Daily.
https://huggingface.co/pipecat-ai/smart-turn-v3 - https://github.com/pipecat-ai/smart-turn

BSD 2-Clause License

Copyright (c) 2024-2025, Daily

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'@ | Set-Content -Encoding utf8 (Join-Path $Destination 'LICENSE.txt')
