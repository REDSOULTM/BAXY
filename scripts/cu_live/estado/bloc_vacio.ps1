# State bloc_vacio: the next Notepad a case opens shows no test text.
# Windows 11 Notepad restores its tabs from TabState, so a test text left in an untitled tab comes back in the next case.
#  - A Notepad already running was not opened by the harness: it is never touched (bloc_ajeno_abierto).
#  - Notepad closed and every saved tab empty (20-byte untitled tab, measured): nothing to do.
#  - Otherwise the harness opens Notepad, and for each restored untitled tab whose whole text is made of the bank's
#    test texts (textos_de_prueba.json) empties it with ValuePattern; any other tab is the person's and stays as is.
#    The harness then closes the window it opened (WindowPattern, exact process id). No tab text is ever printed.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='bloc_vacio'
$TabState=Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsNotepad_8wekyb3d8bbwe\LocalState\TabState'
$Vacia=20

function Get-TabFiles(){ @(Get-ChildItem $TabState -Filter *.bin -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^[0-9a-fA-F-]{36}\.bin$' }) }

$textos=@(([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'textos_de_prueba.json'),[Text.Encoding]::UTF8) | ConvertFrom-Json).textos | Sort-Object Length -Descending)
function Test-TextoDePrueba([string]$T){
  $n=($T -replace '\s+',' ').Trim().ToLowerInvariant()
  if(-not $n){ return $false }
  foreach($x in $textos){ $n=$n.Replace($x.ToLowerInvariant(),' ') }
  return (($n -replace '[\s\p{P}]','') -eq '')
}

# Inside a batch, a Notepad an earlier case left (born in the batch) is not the person's: it exits first.
if($env:CU_LIBRO){ . (Join-Path $PSScriptRoot 'apps_comun.ps1'); $lote=@(Close-ProcesosDelLote 'Notepad') }
$abiertos=@(Get-Process Notepad -ErrorAction SilentlyContinue)
if($abiertos.Count -gt 0){ Write-Estado $E 'bloc_ajeno_abierto' @{ verificado=$false; procesos=$abiertos.Count; nota='hay un Bloc de notas que el arnes no abrio: no se toca' }; return }
$tabs=Get-TabFiles
$grandes=@($tabs | Where-Object { $_.Length -gt $Vacia })
if($grandes.Count -eq 0){ Write-Estado $E 'ok' @{ verificado=$true; pestanas_guardadas=$tabs.Count; pestanas_con_texto=0 }; return }

$fg=Get-Foreground
Start-Process notepad.exe
$p=$null
for($i=0;$i -lt 50 -and -not $p;$i++){ Start-Sleep -Milliseconds 200; $p=@(Get-Process Notepad -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })[0] }
if(-not $p){ Write-Estado $E 'no_abre' @{ verificado=$false }; return }
Start-Sleep -Milliseconds 800
$vaciadas=0; $ajenas=0; $vacias=0
$cPid=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$p.Id)
$cTab=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::TabItem)
$cDoc=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document)
$wins=@([Windows.Automation.AutomationElement]::RootElement.FindAll('Children',$cPid))
foreach($w in $wins){
  foreach($tab in @($w.FindAll('Descendants',$cTab))){
    # An untitled tab is named after its first line ("hola BAXY. Modificado."); a file tab after the file
    # ("notas.txt. No modificado."). File tabs are never emptied.
    $sin=-not ($tab.Current.Name -match '\.[A-Za-z0-9]{1,5}\.\s')
    $s=$null; if($tab.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$s)){ $s.Select(); Start-Sleep -Milliseconds 300 }
    $d=$w.FindFirst('Descendants',$cDoc)
    $v=Get-Value $d
    if([string]::IsNullOrEmpty($v)){ $vacias++ }
    elseif($sin -and (Test-TextoDePrueba $v)){ $d.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue(''); Start-Sleep -Milliseconds 200; if([string]::IsNullOrEmpty((Get-Value $d))){ $vaciadas++ } }
    else{ $ajenas++ }
  }
}
foreach($w in $wins){ try{ $w.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close() }catch{} }
$cerrado=$p.WaitForExit(6000)
$foco=Restore-Foreground $fg @('Notepad')
$despues=@(Get-TabFiles | Where-Object { $_.Length -gt $Vacia }).Count
$ok=($cerrado -and $ajenas -eq 0 -and $despues -eq 0)
$r=if(-not $cerrado){ 'cierre_pendiente' }elseif($ajenas -gt 0){ 'pestanas_ajenas' }elseif($ok){ 'corregido' }else{ 'no_verificado' }
Write-Estado $E $r @{ verificado=$ok; pestanas_con_texto_antes=$grandes.Count; vaciadas=$vaciadas; vacias=$vacias; ajenas=$ajenas; pestanas_con_texto=$despues; cerrado=$cerrado; foco=$foco }
