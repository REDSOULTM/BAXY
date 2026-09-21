# Root fixtures, presets and restores for the typed-tool tandas (opus/typed-tools).
# usage: typed_fixtures.ps1 <cap> before|after [caseProfileDir]
#   cap: textread | explorer_count | wallpaper | airplane | zip | download | meme | pptx | wifi_place | winget | steam | steam_dl | steam_inst | launch | power
# Every step prints one JSON line; "after" never fails the case (restore is best effort, reported).
# Runs OUTSIDE the turn (before the observe, after the collect). Owner rule: never touch the owner's own
# documents; fixtures live under the known folders with distinctive names and are removed afterwards.
param([Parameter(Mandatory)][string]$Cap, [Parameter(Mandatory)][string]$Phase, [string]$Profile = '')
$ErrorActionPreference = 'Stop'
$state = Join-Path $env:LOCALAPPDATA 'BAXY\typed-fixtures-state'
New-Item -ItemType Directory -Force $state | Out-Null
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$documents = [Environment]::GetFolderPath('MyDocuments')
$downloads = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
$pictures = [Environment]::GetFolderPath('MyPictures')
function Out($o) { $o | ConvertTo-Json -Compress -Depth 4 }
# INCIDENTS 2026-09-20 22:42 and 2026-09-21 12:33: fixtures deleted the owner's own folders. Rules: (1) only paths
# under an own «raiz_*» folder are ever removed permanently; (2) anything else (a «Nueva carpeta» the case created)
# is removed ONLY when it did not exist at the `before` step and was created after it, and goes to the Recycle Bin.
function RemoveIf($p) { if ($p -notmatch 'raiz_|\.(png|jpe?g|gif|webp|pdf|html?|pptx)$|wifi-places') { throw "refusing to remove a path outside the fixtures: $p" }; if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue; return $true } return $false }
Add-Type -AssemblyName Microsoft.VisualBasic
function RecycleNewOnly($p, $since, $preexisting) {
  # Sends $p to the Recycle Bin only if it was NOT in $preexisting and its creation time is after $since.
  if (-not (Test-Path -LiteralPath $p)) { return $false }
  if ($preexisting -contains $p) { return $false }
  $item = Get-Item -LiteralPath $p -Force
  if ($item.CreationTime -lt $since) { return $false }
  if ($item.PSIsContainer) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }
  else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }
  return $true
}

switch ("$Cap/$Phase") {
  'textread/before' {
    # REGLA (incidente 2026-09-20): los fixtures viven SOLO bajo carpetas propias «raiz_*» creadas aqui; jamas
    # dentro de una ruta real del dueno. La fila H0299 se mide con la ruta del fixture, no con la ruta original.
    $proj = Join-Path $desktop 'raiz_textos\Probando Gemma 4\gemma4_agent'
    foreach ($d in @((Join-Path $desktop 'raiz_textos'), (Join-Path $documents 'raiz_textos'), (Join-Path $downloads 'raiz_textos'))) { if (Test-Path -LiteralPath $d) { Out @{ ok = $false; error = "fixture dir already exists: $d" }; exit 3 } }
    New-Item -ItemType Directory -Force $proj | Out-Null
    New-Item -ItemType Directory -Force (Join-Path $documents 'raiz_textos') | Out-Null
    New-Item -ItemType Directory -Force (Join-Path $downloads 'raiz_textos') | Out-Null
    $roadmap = "# ROADMAP`n`n## Fase 1: agente local`nEl agente corre en la PC y lee el catalogo.`n`n## Fase 2: memoria`nRecuerda lo que la persona le dijo.`n`n## Fase 3: voz`nEscucha y contesta en voz alta.`n"
    [IO.File]::WriteAllText((Join-Path $proj 'ROADMAP.md'), $roadmap, (New-Object Text.UTF8Encoding $true))
    [IO.File]::WriteAllText((Join-Path $documents 'raiz_textos\notas.txt'), "Notas de la raiz para la tanda.`nComprar pan.`nLlamar a Lucas.`n", (New-Object Text.UTF8Encoding $false))
    [IO.File]::WriteAllText((Join-Path $downloads 'raiz_textos\lista.csv'), "nombre,cantidad`nmanzanas,3`nperas,5`n", (New-Object Text.UTF8Encoding $false))
    [IO.File]::WriteAllText((Join-Path $desktop 'raiz_textos\LEEME.md'), "# LEEME`n`nCarpeta de la raiz para las tandas.`n", (New-Object Text.UTF8Encoding $false))
    [IO.File]::WriteAllBytes((Join-Path $downloads 'raiz_textos\setup.exe'), [byte[]](0x4D,0x5A,0,0,0,1,2,3,0,0,0,0,9,9,0,0))
    Out @{ ok = $true; fixtures = @('Desktop\raiz_textos\Probando Gemma 4\gemma4_agent\ROADMAP.md','Documents\raiz_textos\notas.txt','Downloads\raiz_textos\lista.csv','Desktop\raiz_textos\LEEME.md','Downloads\raiz_textos\setup.exe') }
  }
  'textread/after' {
    # Solo se borran las carpetas «raiz_textos» creadas por este script.
    $removed = @()
    foreach ($p in @((Join-Path $desktop 'raiz_textos'), (Join-Path $documents 'raiz_textos'), (Join-Path $downloads 'raiz_textos'))) { if (RemoveIf $p) { $removed += $p } }
    Out @{ ok = $true; removed = $removed }
  }
  'explorer_count/before' {
    $fix = Join-Path $desktop 'raiz_conteo'
    if (Test-Path -LiteralPath $fix) { Out @{ ok = $false; error = 'fixture dir already exists' }; exit 3 }
    New-Item -ItemType Directory -Force (Join-Path $fix 'sub') | Out-Null
    foreach ($n in 'a.py','b.py','c.py','notas.txt') { Set-Content -LiteralPath (Join-Path $fix $n) -Value 'x' -Encoding ascii }
    Set-Content -LiteralPath (Join-Path $fix 'sub\d.py') -Value 'x' -Encoding ascii
    $p = Start-Process explorer.exe -ArgumentList "`"$fix`"" -PassThru
    Start-Sleep -Seconds 2
    $shell = New-Object -ComObject Shell.Application
    $hwnd = 0
    foreach ($w in @($shell.Windows())) { try { if ([string]$w.LocationURL -like "*raiz_conteo*") { $hwnd = [int64]$w.HWND } } catch {} }
    if ($hwnd -ne 0) {
      $sig = '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);'
      Add-Type -MemberDefinition $sig -Name FG -Namespace TypedFix | Out-Null
      [TypedFix.FG]::SetForegroundWindow([IntPtr]$hwnd) | Out-Null
    }
    Set-Content -LiteralPath (Join-Path $state 'explorer_count.json') -Value (@{ hwnd = $hwnd; folder = $fix } | ConvertTo-Json -Compress)
    Out @{ ok = ($hwnd -ne 0); hwnd = $hwnd; folder = 'raiz_conteo'; py = 3; files = 4 }
  }
  'explorer_count/after' {
    $st = Get-Content (Join-Path $state 'explorer_count.json') | ConvertFrom-Json
    $shell = New-Object -ComObject Shell.Application
    $closed = 0
    foreach ($w in @($shell.Windows())) { try { if ([string]$w.LocationURL -like "*raiz_conteo*") { $w.Quit(); $closed++ } } catch {} }
    Start-Sleep -Seconds 1
    $removed = RemoveIf (Join-Path $desktop 'raiz_conteo')
    Out @{ ok = $true; closed = $closed; removed = $removed }
  }
  'wallpaper/before' {
    $wp = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
    $style = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').WallpaperStyle
    $color = (Get-ItemProperty 'HKCU:\Control Panel\Colors').Background
    @{ wallpaper = $wp; style = $style; background = $color } | ConvertTo-Json -Compress | Set-Content (Join-Path $state 'wallpaper.json')
    Out @{ ok = $true; saved = $wp }
  }
  'wallpaper/after' {
    $st = Get-Content (Join-Path $state 'wallpaper.json') | ConvertFrom-Json
    $sig = '[DllImport("user32.dll", SetLastError = true)] public static extern bool SystemParametersInfo(uint a, uint b, string c, uint d);'
    Add-Type -MemberDefinition $sig -Name SPI -Namespace TypedFix | Out-Null
    Set-ItemProperty 'HKCU:\Control Panel\Colors' -Name Background -Value $st.background
    if ($st.wallpaper) { Set-ItemProperty 'HKCU:\Control Panel\Desktop' -Name WallpaperStyle -Value $st.style }
    $ok = [TypedFix.SPI]::SystemParametersInfo(20, 0, [string]$st.wallpaper, 3)
    Out @{ ok = $ok; restored = $st.wallpaper }
  }
  'airplane/before' {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(); $t.Result }
    $null = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $snap = @($radios | ForEach-Object { @{ kind = [string]$_.Kind; name = $_.Name; state = [string]$_.State } })
    $snap | ConvertTo-Json -Compress | Set-Content (Join-Path $state 'radios.json')
    Out @{ ok = $true; radios = $snap }
  }
  'airplane/after' {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(); $t.Result }
    $snap = Get-Content (Join-Path $state 'radios.json') | ConvertFrom-Json
    $null = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $restored = @()
    foreach ($r in $radios) {
      $want = ($snap | Where-Object { $_.name -eq $r.Name } | Select-Object -First 1).state
      if ($want -and ([string]$r.State) -ne $want -and $want -in @('On','Off')) {
        $target = if ($want -eq 'On') { [Windows.Devices.Radios.RadioState]::On } else { [Windows.Devices.Radios.RadioState]::Off }
        $null = Await ($r.SetStateAsync($target)) ([Windows.Devices.Radios.RadioAccessStatus]); $restored += $r.Name
      }
    }
    Out @{ ok = $true; restored = $restored }
  }
  'zip/before' {
    # H0542 creates «Nueva carpeta» + txt + zip on the Desktop. Record what already exists so `after` never touches it.
    $names = @('Nueva carpeta','Nueva carpeta.zip','New folder','New folder.zip')
    $pre = @(); foreach ($n in $names) { $q = Join-Path $desktop $n; if (Test-Path -LiteralPath $q) { $pre += $q } }
    @{ since = (Get-Date).ToString('o'); preexisting = $pre } | ConvertTo-Json -Compress | Set-Content (Join-Path $state 'zip.json')
    Out @{ ok = $true; preexisting = $pre }
  }
  'zip/after' {
    $st = Get-Content (Join-Path $state 'zip.json') | ConvertFrom-Json
    $since = [DateTime]::Parse($st.since); $pre = @($st.preexisting)
    $removed = @()
    foreach ($n in 'Nueva carpeta','Nueva carpeta.zip','New folder','New folder.zip') { $q = Join-Path $desktop $n; if (RecycleNewOnly $q $since $pre) { $removed += $q } }
    $shell = New-Object -ComObject Shell.Application
    foreach ($w in @($shell.Windows())) { try { if ([string]$w.LocationURL -like "*Nueva*carpeta*" -or [string]$w.LocationURL -like "*New*folder*") { $w.Quit() } } catch {} }
    Out @{ ok = $true; recycled = $removed; preexistingKept = $pre }
  }
  'download/before' {
    $roots = @($desktop, $downloads, $pictures)
    $pre = @(); foreach ($r in $roots) { $pre += @(Get-ChildItem -LiteralPath $r -File -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }) }
    @{ since = (Get-Date).ToString('o'); preexisting = $pre } | ConvertTo-Json -Compress -Depth 3 | Set-Content (Join-Path $state 'download.json')
    Out @{ ok = $true; snapshotFiles = $pre.Count }
  }
  'download/after' {
    $st = Get-Content (Join-Path $state 'download.json') | ConvertFrom-Json
    $since = [DateTime]::Parse($st.since); $pre = @($st.preexisting)
    $removed = @()
    foreach ($r in @($desktop, $downloads, $pictures)) { Get-ChildItem -LiteralPath $r -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '\.(png|jpe?g|gif|webp|pdf|html?)$' } | ForEach-Object { if (RecycleNewOnly $_.FullName $since $pre) { $removed += $_.FullName } } }
    Out @{ ok = $true; recycled = $removed }
  }
  'meme/before' {
    $pre = @(Get-ChildItem -LiteralPath $pictures -File -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $pre += @(Get-ChildItem -LiteralPath $desktop -File -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    @{ since = (Get-Date).ToString('o'); preexisting = $pre } | ConvertTo-Json -Compress -Depth 3 | Set-Content (Join-Path $state 'meme.json')
    Out @{ ok = $true; snapshotFiles = $pre.Count }
  }
  'meme/after' {
    Get-Process -Name 'Photos','PhotosApp','Microsoft.Photos','mspaint','PhotoViewer' -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }
    $st = Get-Content (Join-Path $state 'meme.json') | ConvertFrom-Json
    $since = [DateTime]::Parse($st.since); $pre = @($st.preexisting)
    $removed = @()
    foreach ($r in @($pictures, $desktop)) { Get-ChildItem -LiteralPath $r -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '\.(png|jpe?g|gif|webp)$' } | ForEach-Object { if (RecycleNewOnly $_.FullName $since $pre) { $removed += $_.FullName } } }
    Out @{ ok = $true; recycled = $removed }
  }
  'pptx/before' {
    $pre = @(Get-ChildItem -LiteralPath $documents -File -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $pre += @(Get-ChildItem -LiteralPath $desktop -File -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    @{ since = (Get-Date).ToString('o'); preexisting = $pre } | ConvertTo-Json -Compress -Depth 3 | Set-Content (Join-Path $state 'pptx.json')
    Out @{ ok = $true; snapshotFiles = $pre.Count }
  }
  'pptx/after' {
    Get-Process -Name 'POWERPNT' -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 2; if (-not $_.HasExited) { $_.Kill() } }
    $st = Get-Content (Join-Path $state 'pptx.json') | ConvertFrom-Json
    $since = [DateTime]::Parse($st.since); $pre = @($st.preexisting)
    $removed = @()
    foreach ($r in @($documents, $desktop)) { Get-ChildItem -LiteralPath $r -Filter '*.pptx' -File -Force -ErrorAction SilentlyContinue | ForEach-Object { if (RecycleNewOnly $_.FullName $since $pre) { $removed += $_.FullName } } }
    Out @{ ok = $true; recycled = $removed }
  }
  'wifi_place/before' {
    $cur = (netsh wlan show interfaces | Select-String '^\s*Perfil\s*:|^\s*Profile\s*:' | Select-Object -First 1) -replace '.*:\s*',''
    @{ profile = $cur } | ConvertTo-Json -Compress | Set-Content (Join-Path $state 'wifi.json')
    $removed = @()
    if ($Profile) { $f = Join-Path $Profile 'scans\wifi-places.v1.json'; if (RemoveIf $f) { $removed += $f } }
    Out @{ ok = $true; current = $cur; removedAssociations = $removed }
  }
  'wifi_place/after' {
    $st = Get-Content (Join-Path $state 'wifi.json') | ConvertFrom-Json
    $out = if ($st.profile) { netsh wlan connect name="$($st.profile)" 2>&1 | Out-String } else { 'no previous profile' }
    Out @{ ok = $true; reconnected = $st.profile; netsh = $out.Trim() }
  }
  'winget/before' {
    # Mixed panel (install ordinary / uninstall reviewed) on the test package 7zip.7zip only (D13). The first
    # case installs it, so the tanda starts with the package absent; the previous state is restored in after.
    $has = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    @{ installed = [bool]$has } | ConvertTo-Json -Compress | Set-Content (Join-Path $state 'winget.json')
    if ($has) { winget uninstall --id 7zip.7zip --exact --silent | Out-Null }
    $now = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    Out @{ ok = (-not $now); sevenZipWasInstalled = [bool]$has; sevenZipInstalledNow = [bool]$now }
  }
  'winget/ensure-installed' {
    # Per-case precondition for an uninstall case that follows another uninstall (H0089 after H0574).
    $has = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    if (-not $has) { winget install --id 7zip.7zip --exact --silent --accept-package-agreements --accept-source-agreements | Out-Null }
    $now = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    Out @{ ok = [bool]$now; action = $(if ($has) { 'none' } else { 'installed' }) }
  }
  'winget/ensure-absent' {
    # Per-case precondition for an install case that follows another install (dev-02 after dev-01).
    $has = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    if ($has) { winget uninstall --id 7zip.7zip --exact --silent | Out-Null }
    $now = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    Out @{ ok = (-not $now); action = $(if ($has) { 'uninstalled' } else { 'none' }) }
  }
  'winget/after' {
    $st = Get-Content (Join-Path $state 'winget.json') | ConvertFrom-Json
    $has = (winget list --id 7zip.7zip --exact --accept-source-agreements 2>$null | Select-String '7zip.7zip') -ne $null
    $action = 'none'
    if ($st.installed -and -not $has) { winget install --id 7zip.7zip --exact --silent --accept-package-agreements --accept-source-agreements | Out-Null; $action = 'reinstalled' }
    elseif (-not $st.installed -and $has) { winget uninstall --id 7zip.7zip --exact --silent | Out-Null; $action = 'uninstalled' }
    Out @{ ok = $true; action = $action }
  }
  'steam/before' {
    # Plants vs. Zombies GOTY = appid 3590, PICO PARK Classic = 461040; both owned by the owner (2026-09-20).
    # Case order: H0456 installs PvZ (must be absent), H0620 uninstalls it, dev-01 installs it again, rev-01
    # uninstalls PICO PARK (must be present). Steam of the owner stays open (driver steam_owner).
    $m = @(Get-ChildItem 'C:\Program Files (x86)\Steam\steamapps' -Filter 'appmanifest_*.acf' | ForEach-Object { $_.Name })
    @{ manifests = $m } | ConvertTo-Json -Compress | Set-Content (Join-Path $state 'steam.json')
    $pvz = ($m -contains 'appmanifest_3590.acf'); $pico = ($m -contains 'appmanifest_461040.acf')
    $removed = $false
    if ($pvz) { & $PSCommandPath steam uninstall 3590 | Out-Null; $removed = -not (Test-Path 'C:\Program Files (x86)\Steam\steamapps\appmanifest_3590.acf') }
    Out @{ ok = ($pico -and ((-not $pvz) -or $removed)); pvzWasInstalled = $pvz; pvzRemovedForTanda = $removed; picoInstalled = $pico }
  }
  'steam/uninstall' {
    # $Profile = appid. Same route as game.uninstall.named: the Steam console command app_uninstall, verified by
    # the manifest disappearing (no dialog). Refuses anything but the two test titles.
    if ($Profile -notin @('3590', '461040')) { throw "refusing to uninstall appid $Profile (only 3590 / 461040)" }
    $manifest = "C:\Program Files (x86)\Steam\steamapps\appmanifest_$Profile.acf"
    if (-not (Test-Path $manifest)) { Out @{ ok = $true; action = 'already_absent'; appid = $Profile }; break }
    Start-Process 'steam://open/console'; Start-Sleep -Milliseconds 1500
    $shell = New-Object -ComObject WScript.Shell
    $helper = Get-Process steamwebhelper -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    if ($null -eq $helper) { Out @{ ok = $false; error = 'steam window not found' }; break }
    $shell.AppActivate($helper.Id) | Out-Null; Start-Sleep -Milliseconds 300
    $shell.SendKeys("app_uninstall $Profile{ENTER}")
    $deadline = (Get-Date).AddSeconds(90)
    while ((Test-Path $manifest) -and ((Get-Date) -lt $deadline)) { Start-Sleep -Milliseconds 500 }
    Out @{ ok = (-not (Test-Path $manifest)); action = 'app_uninstall'; appid = $Profile }
  }
  'steam/install' {
    # $Profile = appid. steam://install opens the install dialog; Enter accepts the defaults. Verified by manifest.
    if ($Profile -notin @('3590', '461040')) { throw "refusing to install appid $Profile (only 3590 / 461040)" }
    $manifest = "C:\Program Files (x86)\Steam\steamapps\appmanifest_$Profile.acf"
    if (Test-Path $manifest) { Out @{ ok = $true; action = 'already_present'; appid = $Profile }; break }
    Start-Process "steam://install/$Profile"; Start-Sleep -Milliseconds 2500
    $shell = New-Object -ComObject WScript.Shell
    $helper = Get-Process steamwebhelper -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    if ($null -ne $helper) { $shell.AppActivate($helper.Id) | Out-Null; Start-Sleep -Milliseconds 300; $shell.SendKeys('{ENTER}') }
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Path $manifest) -and ((Get-Date) -lt $deadline)) { Start-Sleep -Milliseconds 500 }
    Out @{ ok = (Test-Path $manifest); action = 'steam_install'; appid = $Profile }
  }
  'steam/after' {
    $st = Get-Content (Join-Path $state 'steam.json') | ConvertFrom-Json
    $now = @(Get-ChildItem 'C:\Program Files (x86)\Steam\steamapps' -Filter 'appmanifest_*.acf' | ForEach-Object { $_.Name })
    $missing = @($st.manifests | Where-Object { $now -notcontains $_ })
    $results = @()
    foreach ($mf in $missing) { $id = ($mf -replace 'appmanifest_(\d+)\.acf','$1'); if ($id -in @('3590', '461040')) { $results += (& $PSCommandPath steam install $id) } }
    Out @{ ok = $true; reinstalled = $results; missingAtEnd = $missing }
  }
  'steam/pvz-absent' {
    # Per-case precondition for an install/download case: Plants vs. Zombies (3590) absent.
    $r = & $PSCommandPath steam uninstall 3590; Write-Output $r
  }
  'steam/pvz-present' {
    # Per-case precondition for an uninstall or launch case: Plants vs. Zombies (3590) present.
    $r = & $PSCommandPath steam install 3590; Write-Output $r
  }
  'launch/before' {
    $pvz = Test-Path 'C:\Program Files (x86)\Steam\steamapps\appmanifest_3590.acf'
    $pico = Test-Path 'C:\Program Files (x86)\Steam\steamapps\appmanifest_461040.acf'
    if (-not $pvz) { & $PSCommandPath steam install 3590 | Out-Null }
    if (-not $pico) { & $PSCommandPath steam install 461040 | Out-Null }
    Out @{ ok = ((Test-Path 'C:\Program Files (x86)\Steam\steamapps\appmanifest_3590.acf') -and (Test-Path 'C:\Program Files (x86)\Steam\steamapps\appmanifest_461040.acf')); pvzWasPresent = $pvz; picoWasPresent = $pico }
  }
  'launch/close' {
    # Closes a game launched by the previous case (PvZ GOTY: PlantsVsZombies / popcapgame1; PICO PARK: PICO PARK).
    $names = @('PlantsVsZombies', 'popcapgame1', 'PICO PARK', 'PicoPark')
    $closed = @()
    foreach ($n in $names) { Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { $closed += $_.ProcessName; Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } }
    Start-Sleep -Milliseconds 800
    Out @{ ok = $true; closed = $closed }
  }
  'launch/after' {
    $r = & $PSCommandPath launch close; Write-Output $r
  }
  { $_ -in @('steam_dl/before', 'steam_inst/before') } { $r = & $PSCommandPath steam before; Write-Output $r }
  { $_ -in @('steam_dl/after', 'steam_inst/after') } { $r = & $PSCommandPath steam after; Write-Output $r }
  'power/after' {
    $out = (shutdown /a 2>&1 | Out-String).Trim()
    Out @{ ok = $true; abort = $out }
  }
  default { Out @{ ok = $true; noop = "$Cap/$Phase" } }
}
