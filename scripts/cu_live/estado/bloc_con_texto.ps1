# State bloc_con_texto:<texto>: Notepad open (by the harness) on an untitled tab whose whole text is <texto>
# (empty argument = an empty tab). Run after bloc_vacio, so no test text comes back from an earlier case.
#  - The text is set with ValuePattern on the document (no keys, no clipboard), then read back.
#  - <texto> must be one of textos_de_prueba.json, so bloc_vacio can empty the tab after the case.
#  - A Notepad the harness did not open is the person's: never touched (ajena_abierta).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E="bloc_con_texto:$Arg"
$textos=@(([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'textos_de_prueba.json'),[Text.Encoding]::UTF8) | ConvertFrom-Json).textos)
if($Arg -and $textos -notcontains $Arg){ Write-Estado $E 'texto_no_listado' @{ verificado=$false; nota='agrega el texto a textos_de_prueba.json' }; return }
$cerradas=@(Close-AppsPropias 'Notepad')
if(@(Get-Process Notepad -ErrorAction SilentlyContinue).Count -gt 0){ Write-Estado $E 'ajena_abierta' @{ verificado=$false; cerradas_antes=$cerradas; nota='hay un Bloc de notas que el arnes no abrio: no se toca' }; return }
$fg=Get-Foreground
$hAntes=@((Get-TopWindows) | ForEach-Object { $_.hwnd })
$pAntes=@(Get-Process | ForEach-Object { $_.Id })
Start-Process notepad.exe
$nuevas=@(Wait-NewWindows $hAntes { $_.app_proceso -eq 'Notepad' } 15)
if($nuevas.Count -eq 0){ Write-Estado $E 'no_abre' @{ verificado=$false }; return }
Add-PropiosApp $nuevas 'Bloc de notas' $pAntes
$w=[Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$nuevas[0].hwnd)
$cDoc=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document)
$cTab=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::TabItem)
$cBtn=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)
function Test-PestanaLibre(){
  # The active tab is untitled (its name has no "file.ext. ") and its document is empty: only then is text set.
  $sel=@($w.FindAll('Descendants',$cTab) | Where-Object { $s=$null; $_.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$s) -and $s.Current.IsSelected })[0]
  $doc=$w.FindFirst('Descendants',$cDoc)
  $script:d=$doc
  ($doc -and [string]::IsNullOrEmpty((Get-Value $doc)) -and -not ($sel -and $sel.Current.Name -match '\.[A-Za-z0-9]{1,5}\.\s'))
}
$d=$null; for($i=0;$i -lt 20 -and -not $d;$i++){ $d=$w.FindFirst('Descendants',$cDoc); if(-not $d){ Start-Sleep -Milliseconds 200 } }
$nueva=$false
if($d -and -not (Test-PestanaLibre)){
  # A restored tab (the person's, or a file) is active: a new tab is added with the tab bar's own add button.
  $add=@($w.FindAll('Descendants',$cBtn) | Where-Object { $_.Current.AutomationId -eq 'AddButton' -or $_.Current.Name -match 'nueva pesta|new tab' })[0]
  if($add){ [void](Invoke-Element $add); Start-Sleep -Milliseconds 600; $nueva=$true }
}
$v=$null
if($d -and (Test-PestanaLibre)){
  $p=$null
  if($d.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$p)){ $p.SetValue($Arg); Start-Sleep -Milliseconds 300; $v=Get-Value $d }
}
$foco=Restore-Foreground $fg @('Notepad')
$ok=($null -ne $v -and $v -ceq $Arg)
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; ventana=$nuevas[0].titulo; pestana_nueva=$nueva; cerradas_antes=$cerradas; foco=$foco }
