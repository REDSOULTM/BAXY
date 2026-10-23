# Palanca 7.4 (goal "BAXY Renew al maximo"): the live probe of the Settings places that app_places.v1.json declares
# pending it. For each candidate address it opens the address with the shell launch (Start-Process, as app.open does),
# waits until the Settings window settles on a page, and reads by UI Automation the window title, the selected item of
# the navigation and the breadcrumb (the reading of the earlier probes G2/L4 in the _about of Configuracion). One JSON
# line per address (stdout and -Out); at the end it closes Settings. Read only: it clicks, types and changes nothing.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\renew\notebook\sonda_settings.ps1 [-Out <file.jsonl>]
#       [-Only microphone,vpn] [-TimeoutSeconds 15]
#
# "confirmed" is true when the breadcrumb (or, without one, the texts read) contains the expected page and the selected
# navigation item is the expected category, both compared without accents or case. The expected names are those of
# Windows 11 in Spanish; a person reads the line before declaring or removing a place.
param(
    [string]$Out = (Join-Path $env:TEMP ("sonda_settings_{0}.jsonl" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))),
    [string[]]$Only = @(),
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]
$Tree = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]

# key, address, expected navigation item, expected page (last breadcrumb item), ASCII without accents.
$candidates = @(
    @('airplanemode', 'ms-settings:network-airplanemode', 'red e internet', 'modo avion'),
    @('camera', 'ms-settings:privacy-webcam', 'privacidad y seguridad', 'camara'),
    @('captions', 'ms-settings:easeofaccess-closedcaptioning', 'accesibilidad', 'subtitulos'),
    @('clipboard', 'ms-settings:clipboard', 'sistema', 'portapapeles'),
    @('contrast', 'ms-settings:easeofaccess-highcontrast', 'accesibilidad', 'temas de contraste'),
    @('devices', 'ms-settings:connecteddevices', 'bluetooth y dispositivos', 'dispositivos'),
    @('gamemode', 'ms-settings:gaming-gamemode', 'juegos', 'modo de juego'),
    @('hotspot', 'ms-settings:network-mobilehotspot', 'red e internet', 'zona con cobertura inalambrica movil'),
    @('keyboard', 'ms-settings:easeofaccess-keyboard', 'accesibilidad', 'teclado'),
    @('location', 'ms-settings:privacy-location', 'privacidad y seguridad', 'ubicacion'),
    @('magnifier', 'ms-settings:easeofaccess-magnifier', 'accesibilidad', 'lupa'),
    @('microphone', 'ms-settings:privacy-microphone', 'privacidad y seguridad', 'microfono'),
    @('narrator', 'ms-settings:easeofaccess-narrator', 'accesibilidad', 'narrador'),
    @('nightlight', 'ms-settings:nightlight', 'sistema', 'luz nocturna'),
    @('otherusers', 'ms-settings:otherusers', 'cuentas', 'otros usuarios'),
    @('pointer', 'ms-settings:easeofaccess-mousepointer', 'accesibilidad', 'puntero del mouse y entrada tactil'),
    @('recovery', 'ms-settings:recovery', 'sistema', 'recuperacion'),
    @('security', 'ms-settings:windowsdefender', 'privacidad y seguridad', 'seguridad de windows'),
    @('signin', 'ms-settings:signinoptions', 'cuentas', 'opciones de inicio de sesion'),
    @('start', 'ms-settings:personalization-start', 'personalizacion', 'inicio'),
    @('startupapps', 'ms-settings:startupapps', 'aplicaciones', 'inicio'),
    @('textsize', 'ms-settings:easeofaccess-display', 'accesibilidad', 'tamano del texto'),
    @('troubleshoot', 'ms-settings:troubleshoot', 'sistema', 'solucionar problemas'),
    @('volumemixer', 'ms-settings:apps-volume', 'sistema', 'mezclador de volumen'),
    @('vpn', 'ms-settings:network-vpn', 'red e internet', 'vpn')
)
if ($Only.Count -gt 0) { $candidates = @($candidates | Where-Object { $Only -contains $_[0] }) }

function Fold([string]$text) {
    if (-not $text) { return '' }
    $decomposed = $text.Normalize([Text.NormalizationForm]::FormD)
    $kept = $decomposed.ToCharArray() | Where-Object {
        [Globalization.CharUnicodeInfo]::GetUnicodeCategory($_) -ne [Globalization.UnicodeCategory]::NonSpacingMark }
    return ((-join $kept).ToLowerInvariant() -replace '\s+', ' ').Trim()
}

function SettingsWindow {
    $ids = @(Get-Process -Name SystemSettings -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    if ($ids.Count -eq 0) { return $null }
    foreach ($window in $A::RootElement.FindAll($Tree::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
        try {
            $current = $window.Current
            # A packaged app's frame (ApplicationFrameHost) holds the page; its own process is SystemSettings below it.
            if ($ids -contains $current.ProcessId) { return $window }
            if ($current.ClassName -eq 'ApplicationFrameWindow') {
                $inner = $window.FindFirst($Tree::Children, (New-Object System.Windows.Automation.PropertyCondition(
                    $A::ClassNameProperty, 'Windows.UI.Core.CoreWindow')))
                if ($inner -and ($ids -contains $inner.Current.ProcessId)) { return $window }
            }
        } catch { }
    }
    return $null
}

function Names($elements) {
    $names = New-Object System.Collections.Generic.List[string]
    foreach ($element in $elements) {
        try { $name = $element.Current.Name } catch { continue }
        if ($name -and -not $names.Contains($name)) { $names.Add($name) }
    }
    return $names.ToArray()
}

function ReadPage($window) {
    $title = try { $window.Current.Name } catch { '' }
    # The selected items, in tree order: the navigation pane comes before the page, so its item is the first.
    $selectable = New-Object System.Windows.Automation.PropertyCondition(
        $A::IsSelectionItemPatternAvailableProperty, $true)
    $selected = @()
    foreach ($item in $window.FindAll($Tree::Descendants, $selectable)) {
        try {
            $pattern = $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
            if ($pattern.Current.IsSelected -and $item.Current.Name) { $selected += $item.Current.Name }
        } catch { }
    }
    # The breadcrumb: the element whose class or automation id names it, and the names of the items inside it.
    $crumbs = @()
    foreach ($element in $window.FindAll($Tree::Descendants, [System.Windows.Automation.Condition]::TrueCondition)) {
        try {
            $current = $element.Current
            if ($current.ClassName -match 'Breadcrumb' -or $current.AutomationId -match 'Breadcrumb') {
                $crumbs = @(Names ($element.FindAll($Tree::Descendants, [System.Windows.Automation.Condition]::TrueCondition)))
                if ($crumbs.Count -eq 0 -and $current.Name) { $crumbs = @($current.Name) }
                break
            }
        } catch { }
    }
    $texts = @()
    if ($crumbs.Count -eq 0) {
        $isText = New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, $CT::Text)
        $texts = @(@(Names ($window.FindAll($Tree::Descendants, $isText))) | Select-Object -First 8)
    }
    return [ordered]@{ title = $title; selected = @($selected); breadcrumb = @($crumbs); texts = @($texts) }
}

function Signature($page) { return ($page.title + '|' + ($page.selected -join ',') + '|' + ($page.breadcrumb -join '>')) }

$utf8 = New-Object System.Text.UTF8Encoding($false)
$previous = ''
foreach ($candidate in $candidates) {
    $key, $address, $expectedNav, $expectedPage = $candidate
    $began = Get-Date
    $page = $null
    $errorText = $null
    try {
        Start-Process $address
        # Settled: a reading of the Settings window that differs from the previous address's and repeats 400 ms later.
        $last = $null
        while (((Get-Date) - $began).TotalSeconds -lt $TimeoutSeconds) {
            Start-Sleep -Milliseconds 400
            $window = SettingsWindow
            if (-not $window) { continue }
            $read = ReadPage $window
            $signature = Signature $read
            if ($last -and $signature -eq $last -and ($signature -ne $previous -or ((Get-Date) - $began).TotalSeconds -gt 4)) {
                $page = $read
                break
            }
            $last = $signature
            $page = $read
        }
        if ($page) { $previous = Signature $page }
    } catch {
        $errorText = $_.Exception.Message
    }
    $nav = if ($page -and $page.selected.Count -gt 0) { $page.selected[0] } else { $null }
    $seen = if ($page) { Fold (($page.breadcrumb + $page.texts) -join ' > ') } else { '' }
    $leaf = if ($page -and $page.breadcrumb.Count -gt 0) { Fold $page.breadcrumb[-1] } else { $null }
    $pageMatches = if ($leaf) { $leaf -eq $expectedPage } else { $seen.Contains($expectedPage) }
    $line = [ordered]@{
        key = $key
        address = $address
        seconds = [math]::Round(((Get-Date) - $began).TotalSeconds, 1)
        title = if ($page) { $page.title } else { $null }
        nav = $nav
        selected = if ($page) { $page.selected } else { @() }
        breadcrumb = if ($page) { $page.breadcrumb } else { @() }
        texts = if ($page) { $page.texts } else { @() }
        expectedNav = $expectedNav
        expectedPage = $expectedPage
        confirmed = [bool]($page -and (Fold $nav) -eq $expectedNav -and $pageMatches)
        error = $errorText
    }
    $json = $line | ConvertTo-Json -Compress -Depth 4
    [System.IO.File]::AppendAllText($Out, $json + "`n", $utf8)
    $json
}

# Close Settings the way its own close button would (WindowPattern), never by killing a process.
$window = SettingsWindow
if ($window) {
    try { $window.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern).Close() } catch { }
}
Write-Host "sonda_settings: $($candidates.Count) direcciones -> $Out"
