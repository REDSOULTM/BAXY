Add-Type -AssemblyName System.Speech

$root = "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\samples"

$samples = @(
    @{File="audio_01_hora.wav";       Text="¿qué hora es?"},
    @{File="audio_02_negation.wav";   Text="no abras Spotify, solo decime si está instalado"},
    @{File="audio_03_multistep.wav";  Text="abrí Notepad y escribí hola mundo"},
    @{File="audio_04_phonetic.wav";   Text="abrí stim"},
    @{File="audio_05_codeswitch.wav"; Text="dame el time y abrí Spotify por favor"}
)

foreach ($s in $samples) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $synth.SelectVoice("Microsoft Sabina Desktop")
    } catch {
        Write-Host "Sabina not found, using default voice"
    }
    $out = Join-Path $root $s.File
    # 16kHz mono 16-bit PCM (Gemma 4 audio expects 16kHz)
    $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToWaveFile($out, $fmt)
    $synth.Speak($s.Text)
    $synth.Dispose()
    Write-Host "Generated: $($s.File)"
}

Get-ChildItem $root -Filter *.wav | Select-Object Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}}
