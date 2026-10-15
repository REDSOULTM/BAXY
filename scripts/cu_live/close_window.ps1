param([string]$Title,[string]$Antes='',[string]$Libro='')
# Closes the top-level windows whose name is EXACTLY $Title (never a part of it: "Descargas" also named the person's
# Downloads folder and a browser's downloads page, review r10a) and that did not exist before the case: their HWND is
# in neither -Antes ("h1 h2") nor the case photo -Libro (libro_lote.ps1 -Foto, its "ventanas"). One of the two is
# required: without knowing what was there before, nothing is closed. A normal close through UIA WindowPattern (never
# a kill); never VS Code, Opera or a title under 4 characters (Close-WindowExact), whatever the title.
if([string]::IsNullOrWhiteSpace($Title) -or $Title.Length -lt 4){ throw "close_window: a title of 4+ characters is required" }
if(-not $Antes -and -not $Libro){ throw "close_window: -Antes or -Libro (the windows open before the case) is required" }
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
$previas=@($Antes -split '\s+' | Where-Object { $_ } | ForEach-Object { [long]$_ })
if($Libro){
  if(-not (Test-Path -LiteralPath $Libro)){ throw "close_window: no photo at $Libro" }
  $previas+=@(([IO.File]::ReadAllText($Libro,[Text.Encoding]::UTF8) | ConvertFrom-Json).ventanas | ForEach-Object { [long]$_ })
}
$protegidos=@('Code','opera','opera_gx','WindowsTerminal','Claude')
$r=[Windows.Automation.AutomationElement]::RootElement
foreach($w in @($r.FindAll('Children',[Windows.Automation.Condition]::TrueCondition))){
  try{ $c=$w.Current; $n=$c.Name; $h=[long]$c.NativeWindowHandle; $pn=(Get-Process -Id $c.ProcessId -ErrorAction SilentlyContinue).ProcessName }catch{ continue }
  if($n -ne $Title -or $h -eq 0 -or $previas -contains $h -or $protegidos -contains $pn){ continue }
  try{ Close-WindowExact $w; "closed: $n ($h)" }catch{ "could not close: $n ($h)" }
}
